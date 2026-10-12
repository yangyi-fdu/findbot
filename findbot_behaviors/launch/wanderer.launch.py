from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    params = PathJoinSubstitution([FindPackageShare('findbot_behaviors'), 'config', 'wanderer.yaml'])
    return LaunchDescription([
        Node(
            package='findbot_behaviors',
            executable='wanderer',
            name='wanderer',
            parameters=[params],
            output='screen',
        ),
    ])
