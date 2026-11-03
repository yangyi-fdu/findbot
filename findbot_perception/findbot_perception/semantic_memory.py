"""Object memory: fuse noisy per-frame detections into a few reliable objects.

Pure Python (no ROS) so the fusion logic can be unit-tested.
"""
from collections import Counter
from dataclasses import dataclass, field
import math


@dataclass
class MemoryObject:
    id: int
    label: str
    x: float
    y: float
    z: float
    observations: int = 0
    confidence_sum: float = 0.0
    colors: Counter = field(default_factory=Counter)
    last_seen: float = 0.0          # seconds (any monotonic clock the caller uses)

    @property
    def confidence(self) -> float:
        return self.confidence_sum / max(1, self.observations)

    @property
    def color(self) -> str:
        return self.colors.most_common(1)[0][0] if self.colors else ''

    @property
    def score(self) -> float:
        """How much we believe this object: many confident sightings win."""
        return self.observations * self.confidence

    def to_dict(self) -> dict:
        return {'id': self.id, 'label': self.label, 'x': self.x, 'y': self.y, 'z': self.z,
                'observations': self.observations, 'confidence_sum': self.confidence_sum,
                'colors': dict(self.colors), 'last_seen': self.last_seen}

    @classmethod
    def from_dict(cls, d: dict) -> 'MemoryObject':
        d = dict(d)
        d['colors'] = Counter(d.get('colors', {}))
        return cls(**d)


class SemanticMemory:

    def __init__(self, merge_radius=0.6, min_observations=3, conflict_radius=0.4):
        self.merge_radius = merge_radius          # same label closer than this -> same object
        self.min_observations = min_observations  # sightings needed before an object is trusted
        self.conflict_radius = conflict_radius    # different labels this close -> same thing, keep best
        self.objects: list[MemoryObject] = []
        self._next_id = 1

    def add(self, label, x, y, z, confidence, color='', stamp=0.0) -> MemoryObject:
        """Fuse one observation; returns the object it was merged into (or created)."""
        best, best_d = None, self.merge_radius
        for o in self.objects:
            if o.label == label:
                d = math.hypot(o.x - x, o.y - y)
                if d < best_d:
                    best, best_d = o, d
        if best is None:
            best = MemoryObject(self._next_id, label, x, y, z)
            self._next_id += 1
            self.objects.append(best)
        # Confidence-weighted running mean of the position.
        w_old, w_new = best.confidence_sum, confidence
        total = w_old + w_new
        if total > 0:
            best.x = (best.x * w_old + x * w_new) / total
            best.y = (best.y * w_old + y * w_new) / total
            best.z = (best.z * w_old + z * w_new) / total
        best.observations += 1
        best.confidence_sum += confidence
        if color:
            best.colors[color] += 1
        best.last_seen = max(best.last_seen, stamp)
        return best

    def confirmed(self) -> list[MemoryObject]:
        """Trusted objects: seen often enough, and not beaten by a different label at the same spot."""
        cands = [o for o in self.objects if o.observations >= self.min_observations]
        kept = []
        for o in sorted(cands, key=lambda o: -o.score):
            if all(math.hypot(o.x - k.x, o.y - k.y) >= self.conflict_radius for k in kept):
                kept.append(o)
        return kept

    def query(self, label='', color='') -> list[MemoryObject]:
        """Confirmed objects matching label/colour ('' = any), most observed first."""
        res = [o for o in self.confirmed()
               if (not label or o.label == label) and (not color or o.color == color)]
        return sorted(res, key=lambda o: -o.observations)

    def to_list(self) -> list[dict]:
        return [o.to_dict() for o in self.objects]

    def load_list(self, items: list[dict]):
        self.objects = [MemoryObject.from_dict(d) for d in items]
        self._next_id = max((o.id for o in self.objects), default=0) + 1
