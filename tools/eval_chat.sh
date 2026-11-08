#!/usr/bin/env bash
# 第5步端到端实测：清空记忆 -> 启动整个系统（无窗口）-> 用自然语言下 5 条指令 -> 保存记录和照片
source ~/ros2_setup/ros_env.sh >/dev/null
bash ~/ros2_setup/killsim.sh >/dev/null; ros2_daemon_ensure
source ~/ros2_ws/install/setup.bash
rm -rf ~/.findbot/semantic_map.yaml ~/.findbot/snapshots ~/findbot_report/memory
mkdir -p ~/findbot_report
ros2 launch findbot_bringup system.launch.py rviz:=false >/tmp/eval_chat_sys.log 2>&1 &
echo "[$(date +%T)] 等待系统就绪……"
for _ in $(seq 60); do ros2 action list 2>/dev/null | grep -q find_object && break; sleep 5; done
ros2 action list 2>/dev/null | grep -q find_object || { echo "系统没起来"; grep -E "\[Err\]|died|Traceback" /tmp/eval_chat_sys.log | head; exit 1; }
sleep 10
echo "[$(date +%T)] 系统就绪，开始对话"
cd ~/ros2_setup && python3 eval_chat.py
sleep 12   # 让语义地图完成最后一次自动保存
cp -r ~/.findbot/semantic_map.yaml ~/.findbot/snapshots ~/findbot_report/ 2>/dev/null
mkdir -p ~/findbot_report/memory && mv ~/findbot_report/semantic_map.yaml ~/findbot_report/snapshots ~/findbot_report/memory/ 2>/dev/null
cp ~/ros2_ws/src/findbot/findbot_bringup/maps/tb3_world.{pgm,yaml} ~/findbot_report/
bash ~/ros2_setup/killsim.sh
echo "[$(date +%T)] ALL DONE"
