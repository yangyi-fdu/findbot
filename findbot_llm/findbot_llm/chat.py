"""Talk to the robot in natural language.

  ros2 run findbot_llm chat                      # interactive
  ros2 run findbot_llm chat "帮我找红色的消防栓"    # one request

Needs ANTHROPIC_API_KEY (or an `ant auth login` profile) and the running system
(ros2 launch findbot_bringup system.launch.py).
"""
import os
import sys

# The Anthropic SDK lives in the project venv (see README). It needs newer pydantic /
# typing_extensions than Ubuntu ships, so the venv goes first for this process only
# (nothing here uses cv_bridge or other numpy-compiled ROS packages).
_VENV = os.path.expanduser('~/findbot_venv/lib/python3.12/site-packages')
if os.path.isdir(_VENV) and _VENV not in sys.path:
    sys.path.insert(0, _VENV)

import anthropic  # noqa: E402
import rclpy  # noqa: E402
import yaml  # noqa: E402
from ament_index_python.packages import get_package_share_directory  # noqa: E402

from findbot_llm.agent import RobotAgent  # noqa: E402
from findbot_llm.ros_bridge import RosRobot  # noqa: E402
from findbot_llm.tools import SYSTEM_PROMPT, build_tools  # noqa: E402


def load_places():
    path = os.path.join(get_package_share_directory('findbot_behaviors'), 'config', 'places.yaml')
    with open(path) as f:
        return {k: (float(v['x']), float(v['y']), float(v.get('yaw', 0.0)))
                for k, v in yaml.safe_load(f)['places'].items()}


def has_credentials():
    """The SDK reads ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile."""
    return bool(os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN')
                or os.path.isdir(os.path.expanduser('~/.config/anthropic')))


def main():
    args = rclpy.utilities.remove_ros_args(sys.argv)[1:]
    if not has_credentials():
        print('❌ 没找到 Claude API 凭证。请运行 bash ~/ros2_setup/set_api_key.sh 保存你的 key，'
              '然后重新打开终端。', flush=True)
        return 1
    rclpy.init()
    places = load_places()
    robot = RosRobot(places)
    agent = RobotAgent(anthropic.Anthropic(), robot, build_tools(places), SYSTEM_PROMPT)

    def handle(text):
        try:
            print(f'🤖 {agent.ask(text)}\n', flush=True)
        except anthropic.AuthenticationError:
            print('❌ Claude API 认证失败：请检查 ANTHROPIC_API_KEY。', file=sys.stderr)
            raise SystemExit(1)
        except anthropic.APIConnectionError:
            print('❌ 连不上 Claude API：请检查网络（VPN）。', file=sys.stderr)
        except anthropic.APIStatusError as e:
            print(f'❌ Claude API 错误 {e.status_code}: {e.message}', file=sys.stderr)

    try:
        if args:
            handle(' '.join(args))
        else:
            print('和机器人说话吧（Ctrl+C 退出）。例如：你都看到过什么？/ 帮我找红色的消防栓\n')
            while True:
                text = input('你：').strip()
                if text:
                    handle(text)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        robot.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    sys.exit(main())
