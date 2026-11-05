#!/usr/bin/env bash
# 第4步实测：清空记忆 -> 启动整个系统（无窗口）-> 跑 4 个找物体场景 -> 保存结果和物体照片
source ~/ros2_setup/ros_env.sh >/dev/null
bash ~/ros2_setup/killsim.sh >/dev/null; ros2_daemon_ensure
source ~/ros2_ws/install/setup.bash
rm -rf ~/.findbot/semantic_map.yaml ~/.findbot/snapshots ~/findbot_report; mkdir -p ~/findbot_report
ros2 launch findbot_bringup system.launch.py rviz:=false >/tmp/eval_sys.log 2>&1 &
echo "[$(date +%T)] 等待系统就绪……"
for _ in $(seq 60); do ros2 action list 2>/dev/null | grep -q find_object && break; sleep 5; done
ros2 action list 2>/dev/null | grep -q find_object || { echo "系统没起来"; grep -E "\[Err\]|died|Traceback" /tmp/eval_sys.log | head; exit 1; }
sleep 10
echo "[$(date +%T)] 系统就绪，开始测试"
python3 ~/ros2_setup/eval_find.py
sleep 12   # 让语义地图完成最后一次自动保存
cp -r ~/.findbot ~/findbot_report/memory
cp ~/ros2_ws/src/findbot/findbot_bringup/maps/tb3_world.{pgm,yaml} ~/findbot_report/
grep -E "find_object_server.*(OK|FAIL|Traceback|Error)" /tmp/eval_sys.log | cut -c1-200 | tail -6
bash ~/ros2_setup/killsim.sh
echo "[$(date +%T)] ALL DONE"
