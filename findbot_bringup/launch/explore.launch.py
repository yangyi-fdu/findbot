"""Map while navigating: Simulation + SLAM Toolbox + Nav2 (no AMCL / map_server) + RViz.

SLAM provides both the growing map and the map->odom transform, so Nav2 can plan
into it right away. Click "Nav2 Goal" in RViz (into white or grey areas) to explore,
then save the map with:
  ros2 run nav2_map_server map_saver_cli -f <path/to/map_name>
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup = get_package_share_directory('findbot_bringup')
    nav2_bringup = get_package_share_directory('nav2_bringup')

    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'slam.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui'), 'rviz': LaunchConfiguration('rviz')}.items(),
    )
    # navigation_launch.py = planner + controller + behaviors + bt_navigator, without localization
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'params_file': os.path.join(bringup, 'config', 'nav2_params.yaml'),
            'use_sim_time': 'true',
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false', description='Start the Gazebo GUI'),
        DeclareLaunchArgument('rviz', default_value='true', description='Start RViz'),
        slam,
        nav2,
    ])
