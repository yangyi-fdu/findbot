from setuptools import find_packages, setup

package_name = 'findbot_llm'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Yang Yi',
    maintainer_email='192686107+yangyi-fdu@users.noreply.github.com',
    description='Natural-language interface: Claude tool use on top of the FindObject action.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'chat = findbot_llm.chat:main',
        ],
    },
)
