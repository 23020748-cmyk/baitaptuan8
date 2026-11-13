"""Launch the robot simulator and webcam controller in the same ROS session."""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    def include(package, filename, arguments):
        path = os.path.join(get_package_share_directory(package), 'launch', filename)
        return IncludeLaunchDescription(PythonLaunchDescriptionSource(path),
                                        launch_arguments=arguments.items())
    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='false'),
        DeclareLaunchArgument('camera_source', default_value='0'),
        DeclareLaunchArgument('model_dir', default_value=''),
        include('turtlebot4_gesture_control', 'gesture_sim.launch.py',
                {'gui': LaunchConfiguration('gui')}),
        include('turtlebot4_emotion_control', 'emotion_control.launch.py', {
            'camera_source': LaunchConfiguration('camera_source'),
            'model_dir': LaunchConfiguration('model_dir'), 'backend': 'opencv',
            'show_window': 'true', 'cmd_vel_topic': '/cmd_vel', 'odom_topic': '/odom',
        }),
    ])
