"""Start Gazebo Harmonic with findbot_waffle (TurtleBot3 waffle + RGB-D camera).

Unlike the upstream turtlebot3_world.launch.py, the Gazebo GUI is optional
(gui:=false saves a lot of CPU; use RViz to look at the robot instead).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    bringup = get_package_share_directory('findbot_bringup')
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    gz_sim_launch = os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')

    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_sim_launch),
        launch_arguments={'gz_args': ['-r -s -v2 ', world], 'on_exit_shutdown': 'true'}.items(),
    )
    gz_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gz_sim_launch),
        launch_arguments={'gz_args': '-g -v2 ', 'on_exit_shutdown': 'true'}.items(),
        condition=IfCondition(gui),
    )
    # TF for the robot's links; the URDF frames match the SDF model (incl. camera_rgb_optical_frame).
    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(tb3_gazebo, 'launch', 'robot_state_publisher.launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items(),
    )
    spawn = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-name', 'findbot_waffle',
                   '-file', os.path.join(bringup, 'models', 'findbot_waffle', 'model.sdf'),
                   '-x', LaunchConfiguration('x'), '-y', LaunchConfiguration('y'), '-z', '0.01'],
    )
    bridge = Node(
        package='ros_gz_bridge', executable='parameter_bridge', output='screen',
        parameters=[{'config_file': os.path.join(bringup, 'config', 'gz_bridge.yaml')}],
    )
    # Images go through ros_gz_image (more efficient than the generic bridge).
    image_bridge = Node(
        package='ros_gz_image', executable='image_bridge', output='screen',
        arguments=['camera/image', 'camera/depth_image'],
        parameters=[{'use_sim_time': True}],
    )

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value=os.path.join(bringup, 'worlds', 'findbot_world.sdf')),
        DeclareLaunchArgument('gui', default_value='false', description='Start the Gazebo GUI'),
        DeclareLaunchArgument('x', default_value='-2.0'),
        DeclareLaunchArgument('y', default_value='-0.5'),
        # turtlebot3 models provide the meshes our model and world refer to
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(tb3_gazebo, 'models')),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(bringup, 'models')),
        # objects placed in findbot_world (downloaded from Gazebo Fuel, not in the repo)
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.expanduser('~/findbot_models/gz')),
        gz_server,
        gz_client,
        spawn,
        bridge,
        image_bridge,
        robot_state_publisher,
    ])
