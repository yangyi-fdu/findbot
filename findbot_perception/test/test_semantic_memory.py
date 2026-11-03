import pytest

from findbot_perception.semantic_memory import SemanticMemory


def feed(mem, label, x, y, n, conf=0.8, color='red'):
    for i in range(n):
        mem.add(label, x + 0.01 * i, y, 0.3, conf, color)


def test_nearby_observations_merge_into_one_object():
    mem = SemanticMemory()
    feed(mem, 'backpack', 3.0, 2.8, 5)
    assert len(mem.objects) == 1
    o = mem.objects[0]
    assert o.observations == 5 and o.x == pytest.approx(3.02, abs=0.01)


def test_far_apart_objects_stay_separate():
    mem = SemanticMemory()
    feed(mem, 'backpack', 3.0, 2.8, 3)
    feed(mem, 'backpack', 3.0, -1.8, 3, color='blue')
    assert len(mem.confirmed()) == 2


def test_rare_detections_are_not_confirmed():
    mem = SemanticMemory(min_observations=3)
    feed(mem, 'airplane', 0.7, 0.8, 2)
    assert mem.confirmed() == []


def test_conflicting_labels_at_same_spot_keep_the_best():
    mem = SemanticMemory()
    feed(mem, 'suitcase', -0.1, 1.2, 8, conf=0.7)
    feed(mem, 'refrigerator', -0.05, 1.2, 4, conf=0.5)
    assert [o.label for o in mem.confirmed()] == ['suitcase']


def test_query_by_label_and_colour():
    mem = SemanticMemory()
    feed(mem, 'backpack', 3.0, 2.8, 4, color='red')
    feed(mem, 'backpack', 3.0, -1.8, 6, color='blue')
    assert [o.color for o in mem.query('backpack')] == ['blue', 'red']   # most observed first
    assert len(mem.query('backpack', 'red')) == 1
    assert mem.query('chair') == []


def test_majority_colour_wins():
    mem = SemanticMemory()
    feed(mem, 'backpack', 3.0, 2.8, 4, color='red')
    feed(mem, 'backpack', 3.0, 2.8, 1, color='orange')
    assert mem.objects[0].color == 'red'


def test_save_and_load_roundtrip():
    mem = SemanticMemory()
    feed(mem, 'chair', 1.0, -1.8, 3, color='black')
    restored = SemanticMemory()
    restored.load_list(mem.to_list())
    assert [(o.label, o.color, o.observations) for o in restored.confirmed()] == [('chair', 'black', 3)]
    assert restored.add('chair', 5.0, 5.0, 0.0, 0.9).id == 2  # ids continue after the loaded ones
