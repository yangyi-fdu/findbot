#!/usr/bin/env bash
# Record a demo from a clean state: clear memory, start the system headless, run the requests.
#   bash demo/record_demo.sh ["request 1" "request 2" ...]
DEMO=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$DEMO")
source "$REPO/scripts/setup_env.sh" >/dev/null
bash "$REPO/scripts/kill_sim.sh" >/dev/null; ros2_daemon_ensure
rm -rf ~/.findbot/semantic_map.yaml ~/.findbot/snapshots
ros2 launch findbot_bringup system.launch.py rviz:=false >/tmp/findbot_demo_system.log 2>&1 &
echo "[$(date +%T)] waiting for the system..."
for _ in $(seq 60); do ros2 action list 2>/dev/null | grep -q find_object && break; sleep 5; done
ros2 action list 2>/dev/null | grep -q find_object || { echo "system did not start"; bash "$REPO/scripts/kill_sim.sh"; exit 1; }
sleep 10
echo "[$(date +%T)] recording"
python3 "$DEMO/record_demo.py" "$@"
bash "$REPO/scripts/kill_sim.sh" >/dev/null
echo "[$(date +%T)] done; render with: python3 demo/render_gif.py"
