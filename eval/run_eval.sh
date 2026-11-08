#!/usr/bin/env bash
# Run an evaluation from a clean state:
#   bash eval/run_eval.sh find                 # FindObject scenarios
#   bash eval/run_eval.sh chat [--backend ..]  # natural-language end-to-end
# Clears the robot's object memory, starts the whole system headless, runs the scenarios,
# saves results + the remembered objects' photos to ~/findbot_report, then stops everything.
EVAL=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$EVAL")
what=${1:-find}; shift || true
source "$REPO/scripts/setup_env.sh" >/dev/null
bash "$REPO/scripts/kill_sim.sh" >/dev/null; ros2_daemon_ensure

rm -rf ~/.findbot/semantic_map.yaml ~/.findbot/snapshots
mkdir -p ~/findbot_report
ros2 launch findbot_bringup system.launch.py rviz:=false >/tmp/findbot_eval_system.log 2>&1 &
echo "[$(date +%T)] waiting for the system..."
for _ in $(seq 60); do ros2 action list 2>/dev/null | grep -q find_object && break; sleep 5; done
if ! ros2 action list 2>/dev/null | grep -q find_object; then
  echo "system did not start:"; grep -E "\[Err\]|died|Traceback" /tmp/findbot_eval_system.log | head
  bash "$REPO/scripts/kill_sim.sh"; exit 1
fi
sleep 10
echo "[$(date +%T)] system ready"

cd "$EVAL" && python3 "eval_$what.py" "$@"

sleep 12   # let the semantic map finish its periodic save
rm -rf ~/findbot_report/memory && mkdir -p ~/findbot_report/memory
cp -r ~/.findbot/semantic_map.yaml ~/.findbot/snapshots ~/findbot_report/memory/ 2>/dev/null
cp "$REPO"/findbot_bringup/maps/tb3_world.{pgm,yaml} ~/findbot_report/
bash "$REPO/scripts/kill_sim.sh" >/dev/null
echo "[$(date +%T)] done; results in ~/findbot_report"
