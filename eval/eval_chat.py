"""End-to-end natural-language test: real simulation + real LLM (the system must be running).

Each request runs `ros2 run findbot_llm chat <request>`; the robot's ground-truth position
is recorded afterwards. Writes ~/findbot_report/chat_results.json.
"""
import json
import math
import os
import re
import subprocess
import sys
import time

from ground_truth import OBJECTS, robot_position

REQUESTS = [  # request, object the robot should end up at (None = should not move to one)
    ('What have you seen?', None),
    ('Find the red fire hydrant', 'fire hydrant'),
    ('What have you seen now?', None),
    ('Take me to the chair', 'chair'),
    ('Find my keys', None),
]


def main():
    extra = sys.argv[1:]   # e.g. --backend claude, --model glm-5.3
    rows = []
    for text, target in REQUESTS:
        print(f'\n===== you: {text}', flush=True)
        t0 = time.time()
        p = subprocess.run(['ros2', 'run', 'findbot_llm', 'chat', *extra, text],
                           capture_output=True, text=True, timeout=1500)
        wall = time.time() - t0
        lines = [line.rstrip() for line in p.stdout.splitlines() if line.strip()]
        print('\n'.join(lines), flush=True)
        rx, ry = robot_position()
        d = math.dist((rx, ry), OBJECTS[target]) if target else None
        rows.append({
            'request': text, 'target': target, 'wall_seconds': round(wall),
            'tool_calls': [line.split('tool call ', 1)[1] for line in lines if 'tool call ' in line],
            'robot_feedback': [line.strip() for line in lines if re.match(r'\s+\[', line)],
            'reply': next((line[2:].strip() for line in lines if line.startswith('🤖')), ''),
            'robot_position': [round(rx, 2), round(ry, 2)],
            'robot_to_target_m': round(d, 2) if d is not None else None,
        })
        if d is not None:
            print(f'  -> ground truth: robot {d:.2f} m from the {target}, {wall:.0f} s', flush=True)
    os.makedirs(os.path.expanduser('~/findbot_report'), exist_ok=True)
    with open(os.path.expanduser('~/findbot_report/chat_results.json'), 'w') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
