from glob import glob

from setuptools import find_packages, setup

package_name = 'findbot_behaviors'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ari',
    maintainer_email='yy13770086966@gmail.com',
    description='Basic robot behaviors for findbot.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wanderer = findbot_behaviors.wanderer:main',
        ],
    },
)
