"""Planning helpers for FindObject (pure Python, unit-tested without ROS)."""
import math


def visit_order(start, places):
    """Greedy nearest-neighbour tour over named places.

    start: (x, y); places: {name: (x, y)} -> [name, ...]
    Cheap and good enough for a handful of places; avoids zig-zagging across the map.
    """
    order, pos, left = [], start, dict(places)
    while left:
        name = min(left, key=lambda n: math.dist(pos, left[n]))
        order.append(name)
        pos = left.pop(name)
    return order


def approach_candidates(obj, robot, distance, n=12):
    """Poses (x, y, yaw) on a circle of `distance` around obj, facing it.

    Sorted so the side facing the robot comes first (shortest drive, and the
    side we most likely saw the object from).
    """
    ox, oy = obj
    base = math.atan2(robot[1] - oy, robot[0] - ox)
    cands = []
    for k in range(n):
        # 0, +step, -step, +2step, ... : fan out from the robot-facing side
        off = ((k + 1) // 2) * (2 * math.pi / n) * (1 if k % 2 else -1)
        a = base + off
        x, y = ox + distance * math.cos(a), oy + distance * math.sin(a)
        cands.append((x, y, math.atan2(oy - y, ox - x)))
    return cands


def describe(label, color):
    return f'{color} {label}'.strip()
