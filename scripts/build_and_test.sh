#!/usr/bin/env bash
# Build the workspace and run the unit tests.
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
source "$REPO/scripts/setup_env.sh"
cd ~/ros2_ws
colcon build --symlink-install "$@" 2>&1 | grep -E "Summary|Failed|error:" || true
source install/setup.bash
cd "$REPO"
python3 -m pytest -q findbot_behaviors/test findbot_perception/test findbot_llm/test 2>&1 | tail -3
