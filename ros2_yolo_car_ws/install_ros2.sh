#!/bin/bash
# ROS 2 Jazzy + Gazebo + TurtleBot3 一键安装脚本
# 用法: sudo bash /home/siton02/md0/ros2_yolo_car_ws/install_ros2.sh
set -e

echo "=========================================="
echo " Step 1: 设置 Locale"
echo "=========================================="
locale-gen en_US en_US.UTF-8
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

echo "=========================================="
echo " Step 2: 添加 ROS 2 apt 源"
echo "=========================================="
apt install -y software-properties-common curl
add-apt-repository -y universe
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu noble main" | \
  tee /etc/apt/sources.list.d/ros2.list > /dev/null

echo "=========================================="
echo " Step 3: 安装 ROS 2 Jazzy Desktop"
echo "=========================================="
apt update
apt install -y ros-jazzy-desktop

echo "=========================================="
echo " Step 4: 安装开发工具"
echo "=========================================="
apt install -y python3-colcon-common-extensions python3-rosdep

# rosdep init 可能已执行过，忽略错误
rosdep init 2>/dev/null || true
# rosdep update 需要以普通用户身份运行，后面再做

echo "=========================================="
echo " Step 5: 安装 Gazebo 桥接 + Nav2"
echo "=========================================="
apt install -y ros-jazzy-ros-gz ros-jazzy-navigation2 ros-jazzy-nav2-bringup

echo "=========================================="
echo " Step 6: 安装 TurtleBot3"
echo "=========================================="
apt install -y ros-jazzy-turtlebot3* || echo "部分 TurtleBot3 包不可用，将从源码构建"

echo "=========================================="
echo " Step 7: 安装 cv_bridge + vision_msgs"
echo "=========================================="
apt install -y ros-jazzy-cv-bridge ros-jazzy-vision-msgs ros-jazzy-image-transport

echo "=========================================="
echo " 安装完成！"
echo "=========================================="
echo ""
echo "接下来请以普通用户身份运行:"
echo "  rosdep update"
echo "  echo 'source /opt/ros/jazzy/setup.bash' >> ~/.bashrc"
echo "  echo 'export TURTLEBOT3_MODEL=waffle_pi' >> ~/.bashrc"
echo "  source ~/.bashrc"
