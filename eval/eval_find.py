"""FindObject scenarios against ground truth (the system must already be running).

Writes ~/findbot_report/find_results.json.
"""
import json
import math
import os
import re
import subprocess
import time

from ground_truth import OBJECTS, robot_position

SCENARIOS = [  # name, find CLI arguments, expected success
    ('Empty memory: find the red fire hydrant (must explore)', ['fire hydrant', '--color', 'red'], True),
    ('Find a chair (possibly seen while exploring)', ['chair'], True),
    ('Find the red fire hydrant again (remembered)', ['fire hydrant', '--color', 'red'], True),
    ('Find a backpack without exploring (should fail cleanly)', ['backpack', '--no-explore'], False),
]


def main():
    results = []
    for name, args, expected in SCENARIOS:
        print(f'\n===== {name}', flush=True)
        t0 = time.time()
        p = subprocess.run(['ros2', 'run', 'findbot_behaviors', 'find', *args],
                           capture_output=True, text=True, timeout=1500)
        wall = time.time() - t0
        lines = [line for line in p.stdout.splitlines() if line.strip()]
        print('\n'.join(lines), flush=True)
        states = [m.group(1) for line in lines if (m := re.match(r'\s*\[(\w+)\s*\]', line))]
        rx, ry = robot_position()
        target = OBJECTS.get(args[0])
        d = math.dist((rx, ry), target) if target else None
        success = p.returncode == 0
        results.append({
            'name': name, 'query': ' '.join(args), 'success': success, 'passed': success == expected,
            'message': next((line for line in lines if line.startswith(('✅', '❌'))), '').strip(),
            'states': list(dict.fromkeys(states)), 'wall_seconds': round(wall),
            'robot_position': [round(rx, 2), round(ry, 2)],
            'robot_to_object_m': round(d, 2) if d is not None and success else None,
        })
        if d is not None and success:
            print(f'  -> ground truth: robot at ({rx:.2f}, {ry:.2f}), {d:.2f} m from the object, {wall:.0f} s')
    os.makedirs(os.path.expanduser('~/findbot_report'), exist_ok=True)
    with open(os.path.expanduser('~/findbot_report/find_results.json'), 'w') as f:
        json.dump(results, f, indent=1)
    print(f'\npassed {sum(r["passed"] for r in results)}/{len(results)}')


if __name__ == '__main__':
    main()
