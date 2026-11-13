from glob import glob
from setuptools import find_packages, setup

package_name = 'turtlebot4_emotion_control'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md', 'requirements-vision.txt',
                                 'requirements-deepface.txt']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Khoa',
    maintainer_email='khoa@example.com',
    description='DeepFace webcam expression control for TurtleBot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'emotion_control_node = turtlebot4_emotion_control.emotion_control_node:main',
    ]},
)
