import math

import numpy as np
import pytest

from findbot_perception.geometry import box_depth, deproject, dominant_color, near_occupied, shrink_box


def test_near_occupied():
    # 10x10 grid, 0.1 m cells, origin (0, 0); one occupied cell at (5, 5) -> centre (0.55, 0.55)
    grid = [0] * 100
    grid[5 * 10 + 5] = 100
    assert near_occupied(grid, 10, 10, 0.1, 0.0, 0.0, 0.55, 0.55, 0.1)
    assert near_occupied(grid, 10, 10, 0.1, 0.0, 0.0, 0.62, 0.55, 0.1)
    assert not near_occupied(grid, 10, 10, 0.1, 0.0, 0.0, 0.85, 0.85, 0.1)
    assert not near_occupied(grid, 10, 10, 0.1, 0.0, 0.0, 5.0, 5.0, 0.1)   # outside the map


def test_deproject_centre_pixel_is_on_optical_axis():
    assert deproject(320, 240, 2.0, 500, 500, 320, 240) == (0.0, 0.0, 2.0)


def test_deproject_right_and_down_are_positive_x_and_y():
    x, y, z = deproject(420, 290, 2.0, 500, 500, 320, 240)
    assert x == pytest.approx(0.4) and y == pytest.approx(0.2) and z == 2.0


def test_shrink_box_keeps_centre():
    assert shrink_box(0, 0, 100, 200, 0.5) == (25, 50, 75, 150)


def test_box_depth_uses_median_and_ignores_background():
    depth = np.full((100, 100), 5.0, dtype=np.float32)   # far background
    depth[30:70, 30:70] = 1.5                              # object
    depth[50, 50] = math.inf                               # invalid pixel
    assert box_depth(depth, (20, 20, 80, 80)) == pytest.approx(1.5)


def test_box_depth_none_when_no_valid_pixels():
    depth = np.full((50, 50), np.nan, dtype=np.float32)
    assert box_depth(depth, (0, 0, 50, 50)) is None


@pytest.mark.parametrize('bgr, name', [
    ((0, 0, 220), 'red'), ((220, 0, 0), 'blue'), ((0, 200, 0), 'green'),
    ((0, 220, 220), 'yellow'), ((20, 20, 20), 'black'), ((240, 240, 240), 'white'),
])
def test_dominant_color(bgr, name):
    patch = np.zeros((20, 20, 3), dtype=np.uint8)
    patch[:] = bgr
    assert dominant_color(patch) == name
