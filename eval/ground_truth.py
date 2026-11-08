"""Ground truth from the simulator, used by every evaluation script.

The map frame was built by SLAM with the robot spawned at Gazebo world (-2.0, -0.5),
so map = world + (2.0, 0.5).
"""
import re
import subprocess

MAP_FROM_WORLD = (2.0, 0.5)

# Object centres in the map frame (from findbot_bringup/worlds/findbot_world.sdf).
OBJECTS = {
    'fire hydrant': (4.0, -0.4),
    'chair': (1.0, -1.8),
    'person': (1.0, 2.8),
    'suitcase': (-0.1, 1.4),
    'backpack (red)': (3.0, 2.8),
    'backpack (blue)': (3.0, -1.8),
}


def robot_position(model='findbot_waffle'):
    """Robot position in the map frame, read from Gazebo (not from the robot's own estimate)."""
    out = subprocess.run(['gz', 'topic', '-e', '-t', '/world/default/dynamic_pose/info', '-n', '1'],
                         capture_output=True, text=True, timeout=15).stdout
    seg = out[out.find(f'name: "{model}"'):]
    pos = seg.split('position', 1)[1].split('}', 1)[0]

    def coord(axis):
        m = re.search(axis + r': ([-\d.e]+)', pos)
        return float(m.group(1)) if m else 0.0   # protobuf text omits zero fields
    return coord('x') + MAP_FROM_WORLD[0], coord('y') + MAP_FROM_WORLD[1]
