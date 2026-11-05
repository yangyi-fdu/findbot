"""Tool definitions and system prompt for the language interface (pure Python, no ROS).

Every argument is constrained by an enum and the tools are `strict`, so Claude can only
ask for objects the detector can actually recognize and places that exist in the map.
"""

# Class names of the COCO-trained YOLO detector (ultralytics yolo11n.pt), in index order.
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
    'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant',
    'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
    'teddy bear', 'hair drier', 'toothbrush',
]

# Colour names produced by findbot_perception.geometry.dominant_color, plus "any".
COLORS = ['any', 'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'black', 'white', 'gray']

SYSTEM_PROMPT = """\
You are the voice of findbot, a small wheeled indoor robot (a TurtleBot3) in a simulated \
arena. You act only through the tools; you cannot see anything yourself.

How the robot works:
- Its camera detector recognizes the object classes listed in the find_object tool and \
nothing else. Translate what the user asks for (in any language) to the closest class, \
e.g. 消防栓 -> "fire hydrant", 书包 -> "backpack", 沙发 -> "couch".
- If the user asks for something that is not one of those classes, say plainly that the \
robot cannot recognize it, and do not call find_object with a substitute.
- find_object first checks the robot's memory of objects it has seen; if the object is not \
there it searches the arena and drives up to the object once it is seen. It can take a few \
minutes.
- list_known_objects answers "what have you seen / where is X" without moving.
- go_to drives to a named place.

Answer briefly, in the user's language. Report only what the tool results say happened; \
if a search failed, say so and suggest what the user could try next.\
"""


def build_tools(places):
    """Tool definitions for the Messages API. `places`: list of place names from places.yaml."""
    no_extra = {'additionalProperties': False}
    return [
        {
            'name': 'find_object',
            'description': ('Find an object and drive up to it. Uses the robot\'s memory first, '
                            'explores the arena if the object has not been seen yet. Returns '
                            'whether it was found, where, and how long it took.'),
            'strict': True,
            'input_schema': {
                'type': 'object',
                'properties': {
                    'label': {'type': 'string', 'enum': COCO_CLASSES,
                              'description': 'Detector class of the object.'},
                    'color': {'type': 'string', 'enum': COLORS,
                              'description': 'Required colour, or "any".'},
                },
                'required': ['label', 'color'], **no_extra,
            },
        },
        {
            'name': 'list_known_objects',
            'description': ('List the objects the robot remembers seeing, with colour, map '
                            'position and how often each was seen. Does not move the robot.'),
            'strict': True,
            'input_schema': {'type': 'object', 'properties': {}, 'required': [], **no_extra},
        },
        {
            'name': 'go_to',
            'description': 'Drive to a named place in the arena.',
            'strict': True,
            'input_schema': {
                'type': 'object',
                'properties': {'place': {'type': 'string', 'enum': list(places)}},
                'required': ['place'], **no_extra,
            },
        },
    ]
