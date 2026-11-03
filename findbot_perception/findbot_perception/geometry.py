"""Pure helpers for turning a 2D detection into a 3D point and a colour name.

No ROS imports here so everything can be unit-tested without a running system.
"""
import numpy as np

# Hue ranges in OpenCV's HSV (H in 0..179). Red wraps around 0.
_HUE_NAMES = [
    (0, 10, 'red'), (10, 22, 'orange'), (22, 35, 'yellow'), (35, 85, 'green'),
    (85, 100, 'cyan'), (100, 130, 'blue'), (130, 160, 'purple'), (160, 180, 'red'),
]


def shrink_box(x1, y1, x2, y2, factor):
    """Box scaled about its centre (factor 0.5 -> middle half). Integer pixel bounds."""
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    hw, hh = (x2 - x1) * factor / 2.0, (y2 - y1) * factor / 2.0
    return int(round(cx - hw)), int(round(cy - hh)), int(round(cx + hw)), int(round(cy + hh))


def box_depth(depth, box, min_valid=0.1, max_valid=8.0, shrink=0.4):
    """Robust depth (metres) of the object inside a bounding box, or None.

    Uses the median over the central part of the box: the box edges usually
    contain background, and the median ignores the remaining outliers.
    """
    h, w = depth.shape[:2]
    x1, y1, x2, y2 = shrink_box(*box, shrink)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, max(x2, x1 + 1)), min(h, max(y2, y1 + 1))
    patch = depth[y1:y2, x1:x2].astype(np.float32).ravel()
    patch = patch[np.isfinite(patch) & (patch > min_valid) & (patch < max_valid)]
    if patch.size < 5:
        return None
    return float(np.median(patch))


def deproject(u, v, z, fx, fy, cx, cy):
    """Pixel (u, v) at depth z -> 3D point in the camera optical frame (pinhole model).

    Optical frame: x right, y down, z forward.
    """
    return ((u - cx) * z / fx, (v - cy) * z / fy, z)


def near_occupied(grid, width, height, resolution, origin_x, origin_y, x, y, radius, threshold=65):
    """True if any occupied cell of an occupancy grid lies within `radius` of (x, y).

    `grid` is the row-major int8 data of a nav_msgs/OccupancyGrid (-1 unknown, 0..100).
    Used to reject 'objects' that are really mapped walls or pillars.
    """
    cx = int((x - origin_x) / resolution)
    cy = int((y - origin_y) / resolution)
    r = int(np.ceil(radius / resolution))
    for j in range(max(0, cy - r), min(height, cy + r + 1)):
        for i in range(max(0, cx - r), min(width, cx + r + 1)):
            if (i - cx) ** 2 + (j - cy) ** 2 <= r * r and grid[j * width + i] >= threshold:
                return True
    return False


def dominant_color(bgr_patch, min_saturated_fraction=0.15):
    """Name of the dominant colour in a BGR image patch ('' if the patch is empty).

    Saturated pixels vote for a hue name; if too few pixels are saturated the
    patch is achromatic and we return black / white / gray by brightness.
    """
    import cv2  # local import: keeps the module importable without OpenCV for tests

    if bgr_patch is None or bgr_patch.size == 0:
        return ''
    hsv = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.int32)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    saturated = (s > 80) & (v > 50)
    if saturated.mean() < min_saturated_fraction:
        mean_v = v.mean()
        return 'black' if mean_v < 60 else 'white' if mean_v > 190 else 'gray'
    votes = {}
    for lo, hi, name in _HUE_NAMES:
        votes[name] = votes.get(name, 0) + int(((h >= lo) & (h < hi) & saturated).sum())
    return max(votes, key=votes.get)
