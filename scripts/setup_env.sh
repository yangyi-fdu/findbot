# Source this in every terminal (add it to ~/.bashrc):
#   source ~/ros2_ws/src/findbot/scripts/setup_env.sh
source /opt/ros/jazzy/setup.bash
[ -f ~/ros2_ws/install/setup.bash ] && source ~/ros2_ws/install/setup.bash
export TURTLEBOT3_MODEL=waffle                  # the simulated robot (waffle has a camera)
export ROS_DOMAIN_ID=17                         # keep this robot's DDS traffic separate
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST  # discover nodes on this machine only

# WSL2 with networkingMode=mirrored: connecting to a closed localhost port hangs instead of
# being refused, so the ros2 CLI's probe for its daemon times out. Start the daemon first.
ros2_daemon_ensure() {
  local port=$((11511 + ${ROS_DOMAIN_ID:-0}))
  ss -ltn 2>/dev/null | grep -q "127.0.0.1:${port} " && return 0
  ros2 daemon start >/dev/null 2>&1
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    ss -ltn 2>/dev/null | grep -q "127.0.0.1:${port} " && return 0
    sleep 0.5
  done
  echo "[findbot] warning: ros2 daemon did not start; add --no-daemon to ros2 commands" >&2
}
ros2_daemon_ensure

# LLM API keys, each in its own private file (scripts/set_api_key.sh)
for _f in ~/.findbot/*.env; do [ -f "$_f" ] && source "$_f"; done; unset _f

alias kill_sim="bash $(dirname "${BASH_SOURCE[0]}")/kill_sim.sh"
true  # exit status 0 even when no key file exists (scripts use set -e)
