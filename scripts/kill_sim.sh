#!/usr/bin/env bash
# Stop every simulation / ROS process left over (Ctrl+C does not always stop the Gazebo server).
pats="gz sim|ros_gz_bridge|parameter_bridge|image_bridge|robot_state_publisher|slam_toolbox|rviz2|wanderer|teleop_keyboard|nav2|amcl|map_server|controller_server|planner_server|bt_navigator|behavior_server|lifecycle_manager|component_container|object_detector|semantic_map|find_object_server|ros2 launch"
pkill -INT -f "$pats" 2>/dev/null; sleep 3
pkill -KILL -f "$pats" 2>/dev/null; sleep 1
ros2 daemon stop >/dev/null 2>&1
left=$(pgrep -af "$pats")
[ -z "$left" ] && echo "all stopped" || { echo "still running:"; echo "$left"; }
