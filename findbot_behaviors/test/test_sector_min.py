import math

import pytest
from sensor_msgs.msg import LaserScan

from findbot_behaviors.wanderer import sector_min


def make_scan(ranges):
    s = LaserScan()
    s.angle_min = 0.0
    s.angle_increment = 2 * math.pi / len(ranges)
    s.range_min = 0.12
    s.range_max = 3.5
    s.ranges = ranges
    return s


def test_front_obstacle_found_across_wraparound():
    r = [3.0] * 360
    r[355] = 0.4  # 5 deg to the right, stored at the end of the array
    # ranges is float32[] in the message definition, so compare approximately
    assert sector_min(make_scan(r), -30, 30) == pytest.approx(0.4)


def test_invalid_ranges_ignored():
    r = [math.inf] * 360
    r[0] = 0.05  # below range_min -> noise
    assert sector_min(make_scan(r), -30, 30) == math.inf


def test_side_sector_excludes_front():
    r = [3.0] * 360
    r[0] = 0.3
    r[60] = 1.0
    assert sector_min(make_scan(r), 30, 100) == 1.0
