"""Perception: YOLO detector + semantic map (object memory)."""
import os

from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

# Ultralytics + PyTorch are installed in a venv (see README). Only the detector
# needs them, so the venv is added to this node's PYTHONPATH and nowhere else.
VENV_SITE = os.path.expanduser('~/findbot_venv/lib/python3.12/site-packages')


def generate_launch_description():
    params = PathJoinSubstitution([FindPackageShare('findbot_perception'), 'config', 'detector.yaml'])
    pythonpath = os.pathsep.join(p for p in (os.environ.get('PYTHONPATH', ''), VENV_SITE) if p)
    return LaunchDescription([
        Node(
            package='findbot_perception',
            executable='object_detector',
            name='object_detector',
            parameters=[params],
            additional_env={'PYTHONPATH': pythonpath},
            output='screen',
        ),
        Node(
            package='findbot_perception',
            executable='semantic_map',
            name='semantic_map',
            parameters=[params],
            output='screen',
        ),
    ])
