"""FindObject action server: remembered -> approach; unknown -> explore named places.

  memory hit  : QUERYING -> APPROACHING -> success
  memory miss : QUERYING -> EXPLORING (place 1) -> LOOKING (spin) -> ... -> APPROACHING
The semantic map is queried while driving and while looking around, so an object
noticed on the way ends the search early.
"""
import math
import os
import threading
import time

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from tf2_ros import Buffer, TransformException, TransformListener

from findbot_behaviors.find_logic import approach_candidates, describe, visit_order
from findbot_interfaces.action import FindObject
from findbot_interfaces.srv import QueryObjects
from findbot_perception.geometry import near_occupied

CANCELED = object()   # sentinel returned by the drive/look helpers


class FindObjectServer(Node):

    def __init__(self):
        super().__init__('find_object_server')
        self.declare_parameter('places_file', os.path.join(
            get_package_share_directory('findbot_behaviors'), 'config', 'places.yaml'))
        self.declare_parameter('approach_distance', 0.7)   # stop this far from the object centre
        self.declare_parameter('robot_clearance', 0.3)     # approach poses need this much free space
        self.declare_parameter('query_period', 2.0)        # s between memory checks while moving

        with open(self.get_parameter('places_file').value) as f:
            self.places = {k: (float(v['x']), float(v['y'])) for k, v in yaml.safe_load(f)['places'].items()}

        self.cb = ReentrantCallbackGroup()
        self.query_cli = self.create_client(QueryObjects, 'semantic_map/query', callback_group=self.cb)
        self.map = None
        self.create_subscription(
            OccupancyGrid, 'map', lambda m: setattr(self, 'map', m),
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE),
            callback_group=self.cb)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # BasicNavigator is its own node and spins itself; keep it out of our executor.
        self.nav = BasicNavigator(node_name='find_object_navigator')
        self.nav.set_parameters([Parameter('use_sim_time', value=True)])
        self.busy = threading.Lock()

        ActionServer(self, FindObject, 'find_object', self.execute,
                     goal_callback=self.on_goal, cancel_callback=lambda _: CancelResponse.ACCEPT,
                     callback_group=self.cb)
        self.get_logger().info(f'find_object ready; places: {", ".join(self.places)}')

    # ---------------------------------------------------------------- action
    def on_goal(self, goal):
        if self.busy.locked():
            self.get_logger().warn('rejecting goal: already searching')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def execute(self, gh):
        with self.busy:
            return self.search(gh)

    def search(self, gh):
        g, t0 = gh.request, time.monotonic()
        what = describe(g.label, g.color)

        def finish(success, message, obj=None):
            res = FindObject.Result(success=success, message=message, elapsed=float(time.monotonic() - t0))
            if obj is not None:
                res.object = obj
            if gh.is_cancel_requested:
                gh.canceled()
            elif success:
                gh.succeed()
            else:
                gh.abort()
            self.get_logger().info(f'[{"OK" if success else "FAIL"}] {message} ({res.elapsed:.0f} s)')
            return res

        self.feedback(gh, 'QUERYING', f'do I remember a {what}?')
        obj = self.query(g.label, g.color)
        if obj is not None:
            return self.approach(gh, obj, what, 'remembered it', finish)
        if not g.explore:
            return finish(False, f'no {what} in memory (exploration disabled)')

        order = visit_order(self.robot_xy() or (0.0, 0.0), self.places)
        for i, name in enumerate(order, 1):
            self.feedback(gh, 'EXPLORING', f'not in memory; searching {name} ({i}/{len(order)})')
            obj = self.drive(gh, *self.places[name], None, watch=(g.label, g.color))
            if obj is None:
                self.feedback(gh, 'LOOKING', f'looking around at {name}')
                obj = self.look_around(gh, watch=(g.label, g.color))
            if obj is CANCELED:
                return finish(False, 'canceled')
            if obj is not None:
                return self.approach(gh, obj, what, f'spotted it while searching {name}', finish)
        return finish(False, f'searched {len(order)} places, no {what} found')

    def approach(self, gh, obj, what, how, finish):
        p = obj.position
        self.feedback(gh, 'APPROACHING', f'{how}: {what} at ({p.x:.2f}, {p.y:.2f}); driving to it')
        robot = self.robot_xy() or (p.x - 1.0, p.y)
        for x, y, yaw in self.free_candidates((p.x, p.y), robot):
            r = self.drive(gh, x, y, yaw)
            if r is CANCELED:
                return finish(False, 'canceled')
            if r == TaskResult.SUCCEEDED:
                return finish(True, f'found the {what} ({how}) and stopped in front of it', obj)
            self.get_logger().warn(f'approach pose ({x:.2f}, {y:.2f}) failed, trying another side')
        return finish(False, f'saw the {what} at ({p.x:.2f}, {p.y:.2f}) but could not reach it', obj)

    # --------------------------------------------------------------- helpers
    def feedback(self, gh, state, detail):
        self.get_logger().info(f'{state}: {detail}')
        gh.publish_feedback(FindObject.Feedback(state=state, detail=detail))

    def query(self, label, color, timeout=5.0):
        """Best remembered match, or None."""
        if not self.query_cli.wait_for_service(timeout_sec=timeout):
            self.get_logger().warn('semantic_map/query not available')
            return None
        fut = self.query_cli.call_async(QueryObjects.Request(label=label, color=color))
        end = time.monotonic() + timeout
        while not fut.done() and time.monotonic() < end:
            time.sleep(0.05)
        res = fut.result() if fut.done() else None
        return res.objects[0] if res and res.objects else None

    def robot_xy(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            return (t.transform.translation.x, t.transform.translation.y)
        except TransformException:
            return None

    def free_candidates(self, obj_xy, robot_xy):
        """Approach poses whose surroundings are free in the static map."""
        cands = approach_candidates(obj_xy, robot_xy, self.get_parameter('approach_distance').value)
        if self.map is None:
            return cands
        info, r = self.map.info, self.get_parameter('robot_clearance').value
        return [c for c in cands
                if not near_occupied(self.map.data, info.width, info.height, info.resolution,
                                     info.origin.position.x, info.origin.position.y, c[0], c[1], r)]

    def make_pose(self, x, y, yaw):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.nav.get_clock().now().to_msg()
        pose.pose.position.x, pose.pose.position.y = x, y
        pose.pose.orientation.z, pose.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        return pose

    def drive(self, gh, x, y, yaw, watch=None):
        """Navigate to (x, y[, yaw]). With `watch`, returns the object as soon as memory knows it.

        Returns CANCELED, a SemanticObject (watch hit), or the Nav2 TaskResult.
        """
        if yaw is None:   # keep heading towards the place
            here = self.robot_xy() or (x, y)
            yaw = math.atan2(y - here[1], x - here[0])
        self.nav.goToPose(self.make_pose(x, y, yaw))
        return self.wait_task(gh, watch)

    def look_around(self, gh, watch):
        self.nav.spin(spin_dist=2 * math.pi, time_allowance=120)
        r = self.wait_task(gh, watch)
        if r is not None:           # canceled, or spotted during the turn
            return r
        return self.query(*watch)   # one last look after the full turn

    def wait_task(self, gh, watch):
        last_q = time.monotonic()
        while not self.nav.isTaskComplete():
            if gh.is_cancel_requested:
                self.nav.cancelTask()
                return CANCELED
            if watch and time.monotonic() - last_q > self.get_parameter('query_period').value:
                last_q = time.monotonic()
                obj = self.query(*watch)
                if obj is not None:
                    self.nav.cancelTask()
                    return obj
        return None if watch else self.nav.getResult()


def main(args=None):
    rclpy.init(args=args)
    node = FindObjectServer()
    node.nav.waitUntilNav2Active(localizer='robot_localization')  # see go_to.py for why not 'amcl'
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.nav.destroy_node()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
