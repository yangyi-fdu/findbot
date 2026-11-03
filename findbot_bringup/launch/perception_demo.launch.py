"""Step 3 demo: navigation on the saved map + YOLO detector + semantic map, in one launch."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    bringup = get_package_share_directory('findbot_bringup')
    perception = get_package_share_directory('findbot_perception')
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup, 'launch', 'nav.launch.py')),
        launch_arguments={'gui': LaunchConfiguration('gui'), 'rviz': LaunchConfiguration('rviz')}.items(),
    )
    detector = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(perception, 'launch', 'detector.launch.py')))
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='true'),
        nav,
        # Give the simulation and TF a head start before YOLO starts asking for transforms.
        TimerAction(period=20.0, actions=[detector]),
    ])
