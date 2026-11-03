"""Whole findbot system: simulation + Nav2 + YOLO detector + semantic map + find_object server.

  ros2 launch findbot_bringup system.launch.py            # with RViz
  ros2 run findbot_behaviors find "fire hydrant" --color red
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('findbot_bringup')
    perception = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'perception_demo.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui'), 'rviz': LaunchConfiguration('rviz')}.items(),
    )
    find_server = Node(
        package='findbot_behaviors', executable='find_object_server', name='find_object_server',
        parameters=[{'use_sim_time': True}], output='screen',
    )
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true'),
        perception,
        TimerAction(period=25.0, actions=[find_server]),
    ])
