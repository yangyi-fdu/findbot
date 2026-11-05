"""Robot side of the agent's tools: thin ROS clients that return plain-text results."""
import math
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node

from findbot_interfaces.action import FindObject
from findbot_interfaces.srv import QueryObjects

STATE_CN = {'QUERYING': '查记忆', 'EXPLORING': '去别处找', 'LOOKING': '原地张望', 'APPROACHING': '靠近物体'}


class RosRobot(Node):

    def __init__(self, places, log=print):
        super().__init__('findbot_llm')
        self.places = places            # {name: (x, y, yaw_deg)}
        self.log = log
        self.find_client = ActionClient(self, FindObject, 'find_object')
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.query_client = self.create_client(QueryObjects, 'semantic_map/query')

    # ---- tools ------------------------------------------------------------
    def find_object(self, label, color):
        if not self.find_client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError('find_object action server is not running')
        goal = FindObject.Goal(label=label, color=color, explore=True)

        def on_feedback(msg):
            fb = msg.feedback
            self.log(f'    [{STATE_CN.get(fb.state, fb.state)}] {fb.detail}')

        res = self.run_action(self.find_client, goal, on_feedback).result
        o = res.object
        if not res.success:
            return f'not found: {res.message} (after {res.elapsed:.0f} s)'
        return (f'found: {o.color} {o.label} at map ({o.position.x:.2f}, {o.position.y:.2f}), '
                f'seen {o.observations} times; the robot drove up to it and stopped in front of it '
                f'({res.elapsed:.0f} s).')

    def list_known_objects(self):
        if not self.query_client.wait_for_service(timeout_sec=10.0):
            raise RuntimeError('semantic map is not running')
        fut = self.query_client.call_async(QueryObjects.Request())
        rclpy.spin_until_future_complete(self, fut, timeout_sec=10.0)
        objs = fut.result().objects if fut.result() else []
        if not objs:
            return 'The robot does not remember any objects yet.'
        return '\n'.join(f'- {o.color} {o.label} at map ({o.position.x:.2f}, {o.position.y:.2f}), '
                         f'seen {o.observations} times' for o in objs)

    def go_to(self, place):
        x, y, yaw = self.places[place]
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            raise RuntimeError('Nav2 is not running')
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x, pose.pose.position.y = x, y
        pose.pose.orientation.z, pose.pose.orientation.w = math.sin(math.radians(yaw) / 2), math.cos(math.radians(yaw) / 2)
        self.log(f'    [导航] 去 {place} ({x:.1f}, {y:.1f})')
        t0 = time.monotonic()
        wrapped = self.run_action(self.nav_client, NavigateToPose.Goal(pose=pose), None)
        ok = wrapped.status == 4  # action_msgs/GoalStatus.STATUS_SUCCEEDED
        return f'{"arrived at" if ok else "failed to reach"} {place} ({time.monotonic() - t0:.0f} s)'

    # ---- helpers ----------------------------------------------------------
    def run_action(self, client, goal, on_feedback):
        """Send a goal and block until it finishes; Ctrl+C cancels the goal on the robot."""
        send = client.send_goal_async(goal, feedback_callback=on_feedback)
        rclpy.spin_until_future_complete(self, send)
        handle = send.result()
        if not handle.accepted:
            raise RuntimeError('goal rejected (is the robot busy with another search?)')
        result = handle.get_result_async()
        try:
            rclpy.spin_until_future_complete(self, result)
        except KeyboardInterrupt:
            rclpy.spin_until_future_complete(self, handle.cancel_goal_async(), timeout_sec=5.0)
            raise
        return result.result()
