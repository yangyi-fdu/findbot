"""Step 5 end-to-end: real system + real LLM. Each request runs `ros2 run findbot_llm chat`.

Saves the transcript and the robot's ground-truth position after each request to
~/findbot_report/step5_live.json.
"""
import json
import math
import os
import re
import subprocess
import time

from eval_find import TRUTH, robot_truth  # same helpers as the step-4 evaluation

REQUESTS = [
    ('你都看到过什么？', None),
    ('帮我找红色的消防栓', 'fire hydrant'),
    ('现在你都看到过什么？', None),
    ('带我去椅子那里', 'chair'),
    ('帮我找一下钥匙', None),
]


def main():
    rows = []
    for text, target in REQUESTS:
        print(f'\n===== 你：{text}', flush=True)
        t0 = time.time()
        p = subprocess.run(['ros2', 'run', 'findbot_llm', 'chat', text],
                           capture_output=True, text=True, timeout=1500)
        wall = time.time() - t0
        lines = [l.rstrip() for l in p.stdout.splitlines() if l.strip() and not l.startswith('[zhipu')]
        print('\n'.join(lines), flush=True)
        try:
            rx, ry = robot_truth()
        except Exception:
            rx = ry = float('nan')
        d = math.dist((rx, ry), TRUTH[target]) if target else None
        rows.append({
            'request': text, 'target': target, 'wall_seconds': round(wall),
            'tool_calls': [l.split('调用工具 ', 1)[1] for l in lines if '调用工具' in l],
            'robot_feedback': [l.strip() for l in lines if re.match(r'\s+\[', l)],
            'reply': next((l[2:].strip() for l in lines if l.startswith('🤖')), ''),
            'errors': [l for l in lines if l.startswith('❌')] + p.stderr.splitlines()[-3:] if p.returncode else [],
            'robot_truth': [round(rx, 2), round(ry, 2)],
            'robot_to_target_m': round(d, 2) if d is not None else None,
        })
        if d is not None:
            print(f'  -> 真实：机器人停在 ({rx:.2f},{ry:.2f})，离{target} {d:.2f} m；用时 {wall:.0f} s', flush=True)
    with open(os.path.expanduser('~/findbot_report/step5_live.json'), 'w') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print('\nRESULTS SAVED', flush=True)


if __name__ == '__main__':
    main()
