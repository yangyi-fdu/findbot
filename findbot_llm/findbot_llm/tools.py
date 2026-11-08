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
nothing else. Map what the user asks for (in any language) to the closest class when the \
meaning is close, e.g. 消防栓 -> "fire hydrant", 书包/背包 -> "backpack", 箱子/行李箱 -> \
"suitcase", 沙发 -> "couch", 人 -> "person", 杯子 -> "cup".
- If nothing in the list is close (keys, a wallet, a door), say in one sentence that the \
robot cannot recognize that kind of object. Do not list the classes.
- find_object is the way to go to an object: it checks the robot's memory first, searches \
the arena if needed, and drives up to the object. Use it whenever the user wants the robot \
to find, go to, or bring them to an object. It can take a few minutes.
- list_known_objects answers "what have you seen / is there an X" without moving.
- go_to only drives to the named places in its enum (home, north, ...), never to objects.

Answer in one or two sentences, in the user's language. Report only what the tool results \
say happened; if a search failed, say so and suggest what the user could try next.\
"""


def validate_args(name, args, places):
    """Check tool arguments against the same enums the schemas declare.

    Claude's strict mode guarantees this already; other providers don't, so the agent
    always validates before touching the robot. Raises ValueError with a message the
    model can act on.
    """
    if not isinstance(args, dict):
        raise ValueError('arguments must be a JSON object')
    if name == 'find_object':
        if args.get('label') not in COCO_CLASSES:
            raise ValueError(f'label {args.get("label")!r} is not a detector class; '
                             'tell the user the robot cannot recognize it')
        if args.get('color', 'any') not in COLORS:
            raise ValueError(f'color must be one of {COLORS}')
    elif name == 'go_to':
        if args.get('place') not in places:
            raise ValueError(f'unknown place {args.get("place")!r}; known places: {list(places)}')
    elif name != 'list_known_objects':
        raise ValueError(f'unknown tool {name!r}')


def openai_style_tools(places):
    """The same tools in the OpenAI-compatible format used by Zhipu GLM."""
    return [{'type': 'function',
             'function': {'name': t['name'], 'description': t['description'],
                          'parameters': t['input_schema']}}
            for t in build_tools(places)]


def build_tools(places):
    """Tool definitions for the Claude Messages API. `places`: place names from places.yaml."""
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
