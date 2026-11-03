"""Command-line client for the find_object action.

  ros2 run findbot_behaviors find "fire hydrant" --color red
  ros2 run findbot_behaviors find chair --no-explore
Ctrl+C cancels the search.
"""
import argparse
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from findbot_interfaces.action import FindObject


def main(argv=None):
    argv = rclpy.utilities.remove_ros_args(sys.argv if argv is None else argv)[1:]
    ap = argparse.ArgumentParser(description='Ask the robot to find an object.')
    ap.add_argument('label', help='object class, e.g. "fire hydrant", chair, person')
    ap.add_argument('--color', default='', help='optional colour, e.g. red')
    ap.add_argument('--no-explore', action='store_true', help='only use what the robot already remembers')
    args = ap.parse_args(argv)

    rclpy.init()
    node = Node('find_cli')
    client = ActionClient(node, FindObject, 'find_object')
    if not client.wait_for_server(timeout_sec=30.0):
        print('find_object server not available', file=sys.stderr)
        return 1

    goal = FindObject.Goal(label=args.label, color=args.color, explore=not args.no_explore)
    send = client.send_goal_async(goal, feedback_callback=lambda f: print(
        f'  [{f.feedback.state:<11}] {f.feedback.detail}', flush=True))
    rclpy.spin_until_future_complete(node, send)
    handle = send.result()
    if not handle.accepted:
        print('goal rejected (is another search running?)')
        return 1
    try:
        res_future = handle.get_result_async()
        rclpy.spin_until_future_complete(node, res_future)
    except KeyboardInterrupt:
        cancel = handle.cancel_goal_async()
        rclpy.spin_until_future_complete(node, cancel, timeout_sec=5.0)
        print('canceled')
        return 130
    res = res_future.result().result
    o = res.object
    print(f'{"✅" if res.success else "❌"} {res.message}  ({res.elapsed:.0f} s)')
    if res.success:
        print(f'   {o.color} {o.label} at ({o.position.x:.2f}, {o.position.y:.2f}), '
              f'seen {o.observations} times')
    node.destroy_node()
    rclpy.try_shutdown()
    return 0 if res.success else 2


if __name__ == '__main__':
    sys.exit(main())
