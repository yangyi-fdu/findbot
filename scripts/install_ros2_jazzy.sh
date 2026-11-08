#!/usr/bin/env bash
# Install ROS 2 Jazzy, Gazebo Harmonic, Nav2, SLAM Toolbox and TurtleBot3 on Ubuntu 24.04.
#   bash scripts/install_ros2_jazzy.sh
#   ROS_MIRROR=http://mirrors.ustc.edu.cn/ros2/ubuntu bash scripts/install_ros2_jazzy.sh   # use a mirror
set -euo pipefail
ROS_MIRROR=${ROS_MIRROR:-http://packages.ros.org/ros2/ubuntu}
step() { echo; echo "==================== $* ===================="; }

echo 'Acquire::Retries "5";' | sudo tee /etc/apt/apt.conf.d/80-retries >/dev/null

step "1/5 base tools + universe repository"
sudo apt-get update
sudo apt-get install -y software-properties-common curl gnupg lsb-release
sudo add-apt-repository -y universe

step "2/5 ROS 2 apt repository ($ROS_MIRROR)"
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
$ROS_MIRROR $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list
sudo apt-get update
sudo apt-get upgrade -y

step "3/5 ROS 2 Jazzy desktop + dev tools"
sudo apt-get install -y ros-jazzy-desktop ros-dev-tools

step "4/5 Gazebo bridge, Nav2, SLAM Toolbox, TurtleBot3, vision messages"
sudo apt-get install -y \
  ros-jazzy-ros-gz \
  ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
  ros-jazzy-slam-toolbox \
  ros-jazzy-turtlebot3 ros-jazzy-turtlebot3-simulations ros-jazzy-turtlebot3-teleop \
  ros-jazzy-vision-msgs ros-jazzy-cv-bridge ros-jazzy-teleop-twist-keyboard \
  python3-pip python3-venv git

step "5/5 rosdep"
[ -f /etc/ros/rosdep/sources.list.d/20-default.list ] || sudo rosdep init
for i in 1 2 3; do ROSDEP_SOURCE_TIMEOUT=120 rosdep update --rosdistro jazzy && break; done

echo; echo "Done. Next: bash scripts/install_python_deps.sh"
