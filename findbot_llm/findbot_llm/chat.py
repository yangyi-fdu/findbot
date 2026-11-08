"""Talk to the robot in natural language.

  ros2 run findbot_llm chat                                  # interactive, Zhipu GLM (free model)
  ros2 run findbot_llm chat "find the red fire hydrant"       # one request (any language)
  ros2 run findbot_llm chat --model glm-5.3                   # Zhipu flagship model
  ros2 run findbot_llm chat --backend claude                  # Claude instead

Needs an API key (scripts/set_api_key.sh zhipu|claude) and the running
system (ros2 launch findbot_bringup system.launch.py).
"""
import argparse
import os
import sys

# The LLM SDKs live in the project venv (see README). They need newer pydantic /
# typing_extensions than Ubuntu ships, so the venv goes first for this process only
# (nothing here uses cv_bridge or other numpy-compiled ROS packages).
_VENV = os.path.expanduser('~/findbot_venv/lib/python3.12/site-packages')
if os.path.isdir(_VENV) and _VENV not in sys.path:
    sys.path.insert(0, _VENV)

import rclpy  # noqa: E402
import yaml  # noqa: E402
from ament_index_python.packages import get_package_share_directory  # noqa: E402

from findbot_llm.agent import ClaudeBackend, RobotAgent, ZhipuBackend  # noqa: E402
from findbot_llm.ros_bridge import RosRobot  # noqa: E402
from findbot_llm.tools import SYSTEM_PROMPT  # noqa: E402

KEY_ENV = {'zhipu': 'ZAI_API_KEY', 'claude': 'ANTHROPIC_API_KEY'}
DEFAULT_MODEL = {'zhipu': 'glm-4.7-flash', 'claude': 'claude-opus-5-5'}


def load_places():
    path = os.path.join(get_package_share_directory('findbot_behaviors'), 'config', 'places.yaml')
    with open(path) as f:
        return {k: (float(v['x']), float(v['y']), float(v.get('yaw', 0.0)))
                for k, v in yaml.safe_load(f)['places'].items()}


def make_backend(name, model, places):
    """Build the LLM backend and the exception types that mean 'bad key' / 'API error'."""
    if name == 'zhipu':
        import zai
        from zai import ZhipuAiClient
        client = ZhipuAiClient(api_key=os.environ['ZAI_API_KEY'])
        # zai-sdk has no separate connection-error class; ZaiError is its base class,
        # so it is checked last (see handle()).
        errors = (zai.core.APIAuthenticationError, zai.core.APIStatusError, zai.core.ZaiError)
        return ZhipuBackend(client, places, SYSTEM_PROMPT, model,
                            busy_errors=(zai.core.APIReachLimitError,)), errors
    import anthropic
    errors = (anthropic.AuthenticationError, anthropic.APIStatusError, anthropic.APIConnectionError)
    return ClaudeBackend(anthropic.Anthropic(), places, SYSTEM_PROMPT, model), errors


def main():
    argv = rclpy.utilities.remove_ros_args(sys.argv)[1:]
    ap = argparse.ArgumentParser(description='Talk to findbot in natural language.')
    ap.add_argument('request', nargs='*', help='one request; omit for an interactive chat')
    ap.add_argument('--backend', choices=sorted(KEY_ENV), default='zhipu')
    ap.add_argument('--model', default=None, help='model id (default depends on the backend)')
    args = ap.parse_args(argv)

    if not os.environ.get(KEY_ENV[args.backend]):
        print(f'❌ {KEY_ENV[args.backend]} is not set. Run scripts/set_api_key.sh {args.backend} '
              'to save your key, then open a new terminal.', flush=True)
        return 1

    rclpy.init()
    places = load_places()
    robot = RosRobot(places)
    backend, (auth_error, status_error, conn_error) = make_backend(
        args.backend, args.model or DEFAULT_MODEL[args.backend], places)
    agent = RobotAgent(backend, robot, places)
    print(f'[{args.backend} / {backend.model}]')

    def handle(text):
        try:
            print(f'🤖 {agent.ask(text)}\n', flush=True)
        # most specific first: the zhipu "connection" class is the SDK's base error class
        except auth_error:
            print('❌ Authentication failed: check that the API key is correct.', flush=True)
            raise SystemExit(1)
        except status_error as e:
            print(f'❌ API error: {e}', flush=True)
        except conn_error as e:
            print(f'❌ Cannot reach the API (check the network / VPN): {e}', flush=True)

    try:
        if args.request:
            handle(' '.join(args.request))
        else:
            print('Talk to the robot (Ctrl+C to quit). Try: "What have you seen?" / '
                  '"Find the red fire hydrant"\n')
            while True:
                text = input('you: ').strip()
                if text:
                    handle(text)
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        robot.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
