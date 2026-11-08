"""Language-understanding probe: real LLM, fake robot (no simulation needed, fast and cheap).

Checks that the model picks the right tool with the right arguments for typical requests,
in English, Korean and Chinese. Outputs vary between runs, so each request is repeated.

  python3 eval/probe_llm.py                          # zhipu glm-4.7-flash, 3 repeats
  python3 eval/probe_llm.py --model glm-5.3 --repeats 5
  python3 eval/probe_llm.py --backend claude

Writes ~/findbot_report/probe_<model>.json
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.expanduser('~/findbot_venv/lib/python3.12/site-packages'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'findbot_llm'))

from findbot_llm.agent import ClaudeBackend, RobotAgent, ZhipuBackend  # noqa: E402
from findbot_llm.tools import SYSTEM_PROMPT  # noqa: E402

PLACES = ['home', 'far_side', 'north', 'south']
# request, acceptable first tool call(s); None = the model should answer without a tool
CASES = [
    ('What have you seen?', ('list_known_objects', {})),
    ('Find the red fire hydrant', ('find_object', {'label': 'fire hydrant', 'color': 'red'})),
    ('Can you find my keys?', None),
    ('Go to the north side', ('go_to', {'place': 'north'})),
    ('Is there a chair? If so, take me there', ('find_object', {'label': 'chair'})),
    # "is there" may be answered from memory or by searching; both are reasonable
    ('Is there a blue box anywhere?', [('list_known_objects', {}),
                                       ('find_object', {'label': 'suitcase', 'color': 'blue'})]),
    ('빨간 소화전을 찾아 줘', ('find_object', {'label': 'fire hydrant', 'color': 'red'})),   # Korean
    ('의자 있는 곳으로 데려가 줘', ('find_object', {'label': 'chair'})),                    # Korean
    ('帮我找红色的消防栓', ('find_object', {'label': 'fire hydrant', 'color': 'red'})),      # Chinese
]


class FakeRobot:
    """Canned answers shaped like the real ROS bridge's results."""

    KNOWN = {'fire hydrant': 'red fire hydrant at map (3.94, -0.37)', 'chair': 'blue chair at map (1.05, -1.68)',
             'suitcase': 'blue suitcase at map (-0.07, 1.19)', 'person': 'blue person at map (0.95, 2.64)'}

    def __init__(self):
        self.calls = []

    def find_object(self, label, color):
        self.calls.append(('find_object', {'label': label, 'color': color or 'any'}))
        if label in self.KNOWN:
            return f'found: {self.KNOWN[label]}, seen 20 times; drove up to it and stopped in front of it (60 s).'
        return f'not found: searched 4 places, no {color} {label} found (300 s)'

    def list_known_objects(self):
        self.calls.append(('list_known_objects', {}))
        return '\n'.join(f'- {v}, seen 20 times' for v in self.KNOWN.values())

    def go_to(self, place):
        self.calls.append(('go_to', {'place': place}))
        return f'arrived at {place} (40 s)'


def matches(expected, got):
    if expected is None:
        return not got
    if isinstance(expected, list):
        return any(matches(e, got) for e in expected)
    if not got:
        return False
    name, args = expected
    gname, gargs = got[0]
    return gname == name and all(gargs.get(k) == v for k, v in args.items())


def make_backend(backend, model):
    if backend == 'claude':
        import anthropic
        return ClaudeBackend(anthropic.Anthropic(), PLACES, SYSTEM_PROMPT, model or 'claude-opus-5-5')
    import zai
    from zai import ZhipuAiClient
    client = ZhipuAiClient(api_key=os.environ['ZAI_API_KEY'])
    return ZhipuBackend(client, PLACES, SYSTEM_PROMPT, model or 'glm-4.7-flash',
                        busy_errors=(zai.core.APIReachLimitError,))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--backend', default='zhipu', choices=['zhipu', 'claude'])
    ap.add_argument('--model', default=None)
    ap.add_argument('--repeats', type=int, default=3)
    a = ap.parse_args()

    rows = []
    for text, expected in [c for c in CASES for _ in range(a.repeats)]:
        robot, log = FakeRobot(), []
        backend = make_backend(a.backend, a.model)
        agent = RobotAgent(backend, robot, PLACES, log=log.append)
        t0 = time.time()
        try:
            reply = agent.ask(text)
        except Exception as e:  # noqa: BLE001 - every failure belongs in the table
            reply = f'EXCEPTION {type(e).__name__}: {e}'
        good = matches(expected, robot.calls)
        rows.append({'request': text, 'calls': robot.calls, 'reply': reply, 'pass': good,
                     'seconds': round(time.time() - t0, 1)})
        print(f'{"PASS" if good else "FAIL"}  {text}\n      calls: {robot.calls or "(none)"}\n      reply: {reply}\n',
              flush=True)
    passed = sum(r['pass'] for r in rows)
    print(f'{backend.model}: {passed}/{len(rows)} passed ({len(CASES)} requests x {a.repeats})')
    os.makedirs(os.path.expanduser('~/findbot_report'), exist_ok=True)
    with open(os.path.expanduser(f'~/findbot_report/probe_{backend.model}.json'), 'w') as f:
        json.dump({'model': backend.model, 'passed': passed, 'total': len(rows), 'rows': rows},
                  f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
