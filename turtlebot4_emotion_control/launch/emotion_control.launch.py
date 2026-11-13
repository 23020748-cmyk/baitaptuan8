import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config = os.path.join(get_package_share_directory('turtlebot4_emotion_control'),
                          'config', 'emotion_control.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=config),
        DeclareLaunchArgument('camera_source', default_value='0'),
        DeclareLaunchArgument('show_window', default_value='true'),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel'),
        DeclareLaunchArgument('odom_topic', default_value='/odom'),
        DeclareLaunchArgument('backend', default_value='opencv'),
        DeclareLaunchArgument('model_dir', default_value=''),
        Node(package='turtlebot4_emotion_control', executable='emotion_control_node',
             name='emotion_control', output='screen', parameters=[
                 LaunchConfiguration('config'), {
                     'camera_source': ParameterValue(LaunchConfiguration('camera_source'), value_type=str),
                     'show_window': ParameterValue(LaunchConfiguration('show_window'), value_type=bool),
                     'cmd_vel_topic': LaunchConfiguration('cmd_vel_topic'),
                     'odom_topic': LaunchConfiguration('odom_topic'),
                     'backend': LaunchConfiguration('backend'),
                     'model_dir': ParameterValue(LaunchConfiguration('model_dir'), value_type=str),
                 }]),
    ])
