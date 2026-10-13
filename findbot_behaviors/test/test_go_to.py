import pytest

from findbot_behaviors.go_to import resolve_target

PLACES = {'north': {'x': 2.0, 'y': 2.3, 'yaw': -90.0}, 'home': {'x': 0.0, 'y': 0.0}}


def test_named_place():
    assert resolve_target(['north'], PLACES) == (2.0, 2.3, -90.0)


def test_named_place_default_yaw():
    assert resolve_target(['home'], PLACES) == (0.0, 0.0, 0.0)


def test_raw_coordinates():
    assert resolve_target(['1.5', '-0.5'], PLACES) == (1.5, -0.5, 0.0)
    assert resolve_target(['1.5', '-0.5', '90'], PLACES) == (1.5, -0.5, 90.0)


def test_unknown_place():
    with pytest.raises(ValueError, match='unknown place'):
        resolve_target(['kitchen'], PLACES)
