"""Language-understanding probe: real LLM, fake robot (no simulation needed).

Checks that the model picks the right tool with the right arguments for typical requests.
Usage: python3 probe_llm.py [model] [backend]
Writes ~/findbot_report/step5_probe.json
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser('~/findbot_venv/lib/python3.12/site-packages'))
sys.path.insert(0, os.path.expanduser('~/ros2_ws/src/findbot/findbot_llm'))

from findbot_llm.agent import RobotAgent, ZhipuBackend  # noqa: E402
from findbot_llm.tools import SYSTEM_PROMPT  # noqa: E402

PLACES = ['home', 'far_side', 'north', 'south']
CASES = [  # request, expected first tool call (None = no tool), allowed alternatives
    ('你都看到过什么？', ('list_known_objects', {})),
    ('帮我找红色的消防栓', ('find_object', {'label': 'fire hydrant', 'color': 'red'})),
    ('帮我找一下钥匙', None),
    ('去北边看看', ('go_to', {'place': 'north'})),
    ('看看有没有椅子，有的话带我过去', ('find_object', {'label': 'chair'})),
    # "is there" may be answered from memory or by searching; both are reasonable
    ('有没有蓝色的箱子？', [('list_known_objects', {}), ('find_object', {'label': 'suitcase', 'color': 'blue'})]),
    ('Can you find a person for me?', ('find_object', {'label': 'person'})),
]


class FakeRobot:
    """Canned answers, shaped like the real ROS bridge's results."""
    def __init__(self):
        self.calls = []

    def find_object(self, label, color):
        self.calls.append(('find_object', {'label': label, 'color': color or 'any'}))
        known = {'fire hydrant': 'red fire hydrant at map (3.94, -0.37)', 'chair': 'blue chair at map (1.05, -1.68)',
                 'suitcase': 'blue suitcase at map (-0.07, 1.19)', 'person': 'blue person at map (0.95, 2.64)'}
        if label in known:
            return f'found: {known[label]}, seen 20 times; the robot drove up to it and stopped in front of it (60 s).'
        return f'not found: searched 4 places, no {color} {label} found (300 s)'

    def list_known_objects(self):
        self.calls.append(('list_known_objects', {}))
        return ('- red fire hydrant at map (3.94, -0.37), seen 64 times\n- blue suitcase at map (-0.07, 1.19), seen 41 times\n'
                '- blue person at map (0.95, 2.64), seen 39 times\n- blue chair at map (1.05, -1.68), seen 20 times')

    def go_to(self, place):
        self.calls.append(('go_to', {'place': place}))
        return f'arrived at {place} (40 s)'


def matches(expected, got):
    if expected is None:
        return not got
    if not got:
        return False
    if isinstance(expected, list):          # any of several acceptable first calls
        return any(matches(e, got) for e in expected)
    name, args = expected
    gname, gargs = got[0]
    return gname == name and all(gargs.get(k) == v for k, v in args.items())


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else 'glm-4.7-flash'
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1   # models are not deterministic
    import zai
    from zai import ZhipuAiClient
    client = ZhipuAiClient(api_key=os.environ['ZAI_API_KEY'])
    busy = (zai.core.APIReachLimitError,)
    rows, ok = [], 0
    for text, expected in [c for c in CASES for _ in range(repeats)]:
        robot = FakeRobot()
        log = []
        agent = RobotAgent(ZhipuBackend(client, PLACES, SYSTEM_PROMPT, model, busy_errors=busy),
                           robot, PLACES, log=log.append)
        t0 = time.time()
        try:
            reply = agent.ask(text)
        except Exception as e:  # noqa: BLE001 - report every failure in the table
            reply = f'EXCEPTION {type(e).__name__}: {e}'
        good = matches(expected, robot.calls)
        ok += good
        rows.append({'request': text, 'expected': expected, 'calls': robot.calls, 'log': log,
                     'reply': reply, 'pass': good, 'seconds': round(time.time() - t0, 1)})
        print(f'{"✅" if good else "❌"} {text}\n   工具: {robot.calls or "（没调用）"}\n   回复: {reply}\n', flush=True)
    print(f'{model}: {ok}/{len(rows)} 通过（{len(CASES)} 句话 × {repeats} 次）')
    os.makedirs(os.path.expanduser('~/findbot_report'), exist_ok=True)
    with open(os.path.expanduser(f'~/findbot_report/step5_probe_{model}.json'), 'w') as f:
        json.dump({'model': model, 'passed': ok, 'total': len(rows), 'repeats': repeats, 'rows': rows},
                  f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
