import math

import pytest

from findbot_behaviors.find_logic import approach_candidates, describe, visit_order


def test_visit_order_is_nearest_neighbour():
    places = {'far': (10, 0), 'near': (1, 0), 'mid': (5, 0)}
    assert visit_order((0, 0), places) == ['near', 'mid', 'far']


def test_visit_order_empty():
    assert visit_order((0, 0), {}) == []


def test_first_candidate_is_between_robot_and_object_and_faces_it():
    x, y, yaw = approach_candidates((4.0, 0.0), robot=(0.0, 0.0), distance=0.7)[0]
    assert (x, y) == (pytest.approx(3.3), pytest.approx(0.0, abs=1e-9))
    assert yaw == pytest.approx(0.0, abs=1e-9)       # facing +x, towards the object


def test_all_candidates_at_distance_and_facing_object():
    for x, y, yaw in approach_candidates((1.0, 2.0), robot=(0.0, 0.0), distance=0.7):
        assert math.dist((x, y), (1.0, 2.0)) == pytest.approx(0.7)
        assert math.atan2(2.0 - y, 1.0 - x) == pytest.approx(yaw)


def test_describe():
    assert describe('chair', '') == 'chair'
    assert describe('fire hydrant', 'red') == 'red fire hydrant'
