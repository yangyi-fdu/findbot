"""Step 4 evaluation: run FindObject scenarios against ground truth, save results for the report.

Assumes system.launch.py is running. Writes ~/findbot_report/step4_results.json.
"""
import json
import math
import os
import re
import subprocess
import time

TRUTH = {  # object centres in the map frame (= Gazebo world + (2.0, 0.5))
    'fire hydrant': (4.0, -0.4), 'chair': (1.0, -1.8), 'person': (1.0, 2.8),
    'suitcase': (-0.1, 1.4), 'backpack': (3.0, 2.8),
}
SCENARIOS = [
    ('① 清空记忆后找红色消防栓（需要探索）', ['fire hydrant', '--color', 'red']),
    ('② 找椅子（探索时可能顺便见过）', ['chair']),
    ('③ 再找红色消防栓（已记住，应直接去）', ['fire hydrant', '--color', 'red']),
    ('④ 找书包，不允许探索（应报告失败）', ['backpack', '--no-explore']),
]


def robot_truth():
    """Robot position in the map frame from Gazebo (ground truth)."""
    out = subprocess.run(['gz', 'topic', '-e', '-t', '/world/default/dynamic_pose/info', '-n', '1'],
                         capture_output=True, text=True, timeout=15).stdout
    seg = out[out.find('name: "findbot_waffle"'):]
    pos = seg.split('position', 1)[1].split('}', 1)[0]
    g = lambda k: float(m.group(1)) if (m := re.search(k + r': ([-\d.e]+)', pos)) else 0.0
    return g('x') + 2.0, g('y') + 0.5


def main():
    results = []
    for name, args in SCENARIOS:
        print(f'\n===== {name}', flush=True)
        t0 = time.time()
        p = subprocess.run(['ros2', 'run', 'findbot_behaviors', 'find', *args],
                           capture_output=True, text=True, timeout=1500)
        wall = time.time() - t0
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        print('\n'.join(lines), flush=True)
        states = [m.group(1) for l in lines if (m := re.match(r'\s*\[(\w+)\s*\]', l))]
        try:
            rx, ry = robot_truth()
        except Exception:
            rx = ry = float('nan')
        target = TRUTH.get(args[0])
        d = math.dist((rx, ry), target) if target else None
        est = re.search(r'at \(([-\d.]+), ([-\d.]+)\), seen (\d+)', p.stdout)
        results.append({
            'name': name, 'query': ' '.join(args), 'success': p.returncode == 0,
            'message': next((l for l in lines if l.startswith(('✅', '❌'))), '').strip(),
            'states': list(dict.fromkeys(states)), 'feedback': lines,
            'wall_seconds': round(wall), 'robot_truth': [round(rx, 2), round(ry, 2)],
            'robot_to_object_m': round(d, 2) if d is not None else None,
            'estimated': [float(est.group(1)), float(est.group(2))] if est else None,
            'estimate_error_m': round(math.dist((float(est.group(1)), float(est.group(2))), target), 2)
            if est and target else None,
        })
        print(f'  -> 真实: 机器人停在 ({rx:.2f},{ry:.2f})，离物体 {d:.2f} m；用时 {wall:.0f} s' if d else '', flush=True)
    os.makedirs(os.path.expanduser('~/findbot_report'), exist_ok=True)
    with open(os.path.expanduser('~/findbot_report/step4_results.json'), 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print('\nRESULTS SAVED', flush=True)


if __name__ == '__main__':
    main()
