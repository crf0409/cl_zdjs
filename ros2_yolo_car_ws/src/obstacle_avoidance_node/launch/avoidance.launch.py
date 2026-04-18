import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('obstacle_avoidance_node'),
        'config',
        'avoidance_params.yaml'
    )

    return LaunchDescription([
        Node(
            package='obstacle_avoidance_node',
            executable='obstacle_avoidance',
            name='obstacle_avoidance',
            parameters=[config],
            output='screen',
        ),
    ])
