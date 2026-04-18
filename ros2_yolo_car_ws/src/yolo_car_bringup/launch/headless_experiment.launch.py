"""
Headless experiment launch file.

Launches Gazebo in server-only mode (no GUI), spawns TurtleBot3,
starts YOLO detection and obstacle avoidance nodes.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    # Set TurtleBot3 model
    turtlebot3_model = SetEnvironmentVariable('TURTLEBOT3_MODEL', 'waffle_pi')

    # Gazebo paths
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    turtlebot3_gazebo_dir = get_package_share_directory('turtlebot3_gazebo')

    world = os.path.join(turtlebot3_gazebo_dir, 'worlds', 'turtlebot3_world.world')

    # Gazebo server only (headless, no GUI)
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': f'-r -s -v2 --headless-rendering {world}',
            'on_exit_shutdown': 'true'
        }.items()
    )

    # Robot state publisher
    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(turtlebot3_gazebo_dir, 'launch', 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': 'true'}.items()
    )

    # Spawn TurtleBot3
    urdf_path = os.path.join(
        turtlebot3_gazebo_dir, 'models', 'turtlebot3_waffle_pi', 'model.sdf'
    )
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'waffle_pi',
            '-file', urdf_path,
            '-x', '-2.0', '-y', '-0.5', '-z', '0.01'
        ],
        output='screen',
    )

    # Gazebo-ROS bridge (topics: cmd_vel, odom, scan, imu, etc.)
    bridge_params = os.path.join(
        turtlebot3_gazebo_dir, 'params', 'turtlebot3_waffle_pi_bridge.yaml'
    )
    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['--ros-args', '-p', f'config_file:={bridge_params}'],
        output='screen',
    )

    # Gazebo-ROS image bridge (camera)
    image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camera/image_raw'],
        output='screen',
    )

    # Set GZ_SIM_RESOURCE_PATH
    set_gz_resource_path = SetEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(turtlebot3_gazebo_dir, 'models')
    )

    # YOLO detection node
    yolo_config = os.path.join(
        get_package_share_directory('yolo_detection_node'),
        'config', 'detection_params.yaml'
    )
    yolo_node = Node(
        package='yolo_detection_node',
        executable='yolo_detector',
        name='yolo_detector',
        parameters=[yolo_config],
        output='screen',
    )

    # Obstacle avoidance node
    avoidance_config = os.path.join(
        get_package_share_directory('obstacle_avoidance_node'),
        'config', 'avoidance_params.yaml'
    )
    avoidance_node = Node(
        package='obstacle_avoidance_node',
        executable='obstacle_avoidance',
        name='obstacle_avoidance',
        parameters=[avoidance_config],
        output='screen',
    )

    ld = LaunchDescription()
    ld.add_action(turtlebot3_model)
    ld.add_action(set_gz_resource_path)
    ld.add_action(gzserver_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_robot)
    ld.add_action(gz_bridge)
    ld.add_action(image_bridge)
    ld.add_action(yolo_node)
    ld.add_action(avoidance_node)

    return ld
