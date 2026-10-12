"""Step 2b: navigate on a saved map. Simulation + Nav2 (AMCL localization) + RViz.

In RViz use "Nav2 Goal" to click a destination.
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
    nav2_bringup = get_package_share_directory('nav2_bringup')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'sim.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui')}.items(),
    )
    # bringup_launch.py = map_server + AMCL (localization) + planner/controller/behaviors
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'map': LaunchConfiguration('map'),
            'params_file': LaunchConfiguration('params_file'),
            'use_sim_time': 'true',
        }.items(),
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
        DeclareLaunchArgument('map', default_value=os.path.join(bringup, 'maps', 'tb3_world.yaml')),
        DeclareLaunchArgument('params_file', default_value=os.path.join(bringup, 'config', 'nav2_params.yaml')),
        sim,
        nav2,
        rviz,
    ])
