"""Step 2a: build a map. Simulation + SLAM Toolbox + RViz.

Drive the robot around (teleop or wanderer), then save the map with:
  ros2 run nav2_map_server map_saver_cli -f <path/to/map_name>
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('findbot_bringup')
    slam_toolbox = get_package_share_directory('slam_toolbox')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'sim.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui')}.items(),
    )
    # Online async SLAM: builds the map live while the robot drives, dropping scans
    # if it falls behind (good for a slow, CPU-rendered simulation).
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(slam_toolbox, 'launch', 'online_async_launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items(),
    )
    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', os.path.join(bringup, 'rviz', 'findbot.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz')),
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false', description='Start the Gazebo GUI'),
        DeclareLaunchArgument('rviz', default_value='true', description='Start RViz'),
        sim,
        slam,
        rviz,
    ])
