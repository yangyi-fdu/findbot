"""Send the robot to a named place, or to raw map coordinates, through Nav2.

  ros2 run findbot_behaviors go_to north
  ros2 run findbot_behaviors go_to 1.5 -0.5 90      # x y [yaw_deg]
  ros2 run findbot_behaviors go_to --list

Under the hood this is a client of Nav2's `navigate_to_pose` action:
goal -> periodic feedback (distance remaining) -> result.
"""
import argparse
import math
import os
import sys

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.parameter import Parameter


def default_places_file() -> str:
    return os.path.join(get_package_share_directory('findbot_behaviors'), 'config', 'places.yaml')


def load_places(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)['places']


def resolve_target(target: list, places: dict) -> tuple:
    """['north'] -> place lookup; ['1.5', '-0.5', '90'] -> (1.5, -0.5, 90.0)."""
    if len(target) == 1 and target[0] in places:
        p = places[target[0]]
        return float(p['x']), float(p['y']), float(p.get('yaw', 0.0))
    try:
        nums = [float(v) for v in target]
    except ValueError:
        raise ValueError(f'unknown place {" ".join(target)!r}; known: {", ".join(places)}')
    if len(nums) not in (2, 3):
        raise ValueError('expected a place name or "x y [yaw_deg]"')
    return nums[0], nums[1], nums[2] if len(nums) == 3 else 0.0


def make_pose(nav: BasicNavigator, x: float, y: float, yaw_deg: float) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = nav.get_clock().now().to_msg()
    pose.pose.position.x = x
    pose.pose.position.y = y
    # A planar heading as a quaternion: rotation of yaw around the z axis.
    yaw = math.radians(yaw_deg)
    pose.pose.orientation.z = math.sin(yaw / 2.0)
    pose.pose.orientation.w = math.cos(yaw / 2.0)
    return pose


def main(argv=None):
    argv = rclpy.utilities.remove_ros_args(sys.argv if argv is None else argv)[1:]
    parser = argparse.ArgumentParser(description='Navigate to a named place or x y [yaw_deg].')
    parser.add_argument('target', nargs='*', help='place name, or x y [yaw_deg] in the map frame')
    parser.add_argument('--places', default=default_places_file(), help='YAML file with named places')
    parser.add_argument('--list', action='store_true', help='list known places and exit')
    args = parser.parse_args(argv)

    places = load_places(args.places)
    if args.list or not args.target:
        for name, p in places.items():
            print(f'  {name:<10} x={p["x"]:>5}  y={p["y"]:>5}  yaw={p.get("yaw", 0)}')
        return 0
    try:
        x, y, yaw = resolve_target(args.target, places)
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
        return 2

    rclpy.init()
    nav = BasicNavigator(node_name='go_to')
    nav.set_parameters([Parameter('use_sim_time', value=True)])
    try:
        # Wait for the navigator only. With localizer='amcl', BasicNavigator keeps
        # publishing /initialpose (at the map origin) until it hears /amcl_pose,
        # which silently teleports AMCL's estimate back to home if the robot is
        # elsewhere. 'robot_localization' skips that handshake.
        nav.waitUntilNav2Active(localizer='robot_localization')
        nav.info(f'going to ({x:.2f}, {y:.2f}), facing {yaw:.0f} deg')
        nav.goToPose(make_pose(nav, x, y, yaw))

        last_print = None
        while not nav.isTaskComplete():
            fb = nav.getFeedback()
            if fb is None:
                continue
            remaining = round(fb.distance_remaining, 1)
            if remaining != last_print:  # print only when it changes by >= 0.1 m
                nav.info(f'distance remaining: {remaining:.1f} m, recoveries: {fb.number_of_recoveries}')
                last_print = remaining

        result = nav.getResult()
        if result == TaskResult.SUCCEEDED:
            nav.info('arrived')
            return 0
        nav.error(f'navigation ended with {result.name}')
        return 1
    except KeyboardInterrupt:
        nav.cancelTask()  # Ctrl+C cancels the goal so the robot stops
        nav.warn('cancelled')
        return 130
    finally:
        nav.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    sys.exit(main())
