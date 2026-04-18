"""
Full system launch file for YOLO obstacle avoidance car.

Launches:
1. TurtleBot3 Gazebo simulation (waffle_pi with camera)
2. YOLO detection node
3. Obstacle avoidance node
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Set TurtleBot3 model
    turtlebot3_model = SetEnvironmentVariable('TURTLEBOT3_MODEL', 'waffle_pi')

    # TurtleBot3 Gazebo world launch
    turtlebot3_gazebo_dir = get_package_share_directory('turtlebot3_gazebo')
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(turtlebot3_gazebo_dir, 'launch', 'turtlebot3_world.launch.py')
        ),
    )

    # YOLO detection node
    yolo_config = os.path.join(
        get_package_share_directory('yolo_detection_node'),
        'config',
        'detection_params.yaml'
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
        'config',
        'avoidance_params.yaml'
    )
    avoidance_node = Node(
        package='obstacle_avoidance_node',
        executable='obstacle_avoidance',
        name='obstacle_avoidance',
        parameters=[avoidance_config],
        output='screen',
    )

    return LaunchDescription([
        turtlebot3_model,
        gazebo_launch,
        yolo_node,
        avoidance_node,
    ])
