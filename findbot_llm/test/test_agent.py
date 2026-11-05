from types import SimpleNamespace as NS

from findbot_llm.agent import RobotAgent
from findbot_llm.tools import COCO_CLASSES, SYSTEM_PROMPT, build_tools


def text(t):
    return NS(type='text', text=t)


def tool_use(i, name, args):
    return NS(type='tool_use', id=i, name=name, input=args)


class FakeClient:
    """Plays back scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.requests.append({**kw, 'messages': list(kw['messages'])})
        return self.responses.pop(0)


class FakeRobot:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def find_object(self, label, color):
        self.calls.append(('find_object', label, color))
        if self.fail:
            raise RuntimeError('find_object action server is not running')
        return 'found: red fire hydrant at map (3.94, -0.37)'

    def list_known_objects(self):
        self.calls.append(('list_known_objects',))
        return '- blue chair at map (1.05, -1.68)'

    def go_to(self, place):
        self.calls.append(('go_to', place))
        return f'arrived at {place}'


def make(responses, robot=None):
    client = FakeClient(responses)
    robot = robot or FakeRobot()
    agent = RobotAgent(client, robot, build_tools(['home', 'north']), SYSTEM_PROMPT, log=lambda *_: None)
    return agent, client, robot


def test_tool_call_then_answer():
    agent, client, robot = make([
        NS(stop_reason='tool_use', content=[text('我去找找'), tool_use('t1', 'find_object',
                                                                    {'label': 'fire hydrant', 'color': 'red'})]),
        NS(stop_reason='end_turn', content=[text('找到了红色消防栓。')]),
    ])
    assert agent.ask('帮我找红色的消防栓') == '找到了红色消防栓。'
    assert robot.calls == [('find_object', 'fire hydrant', 'red')]
    # second request carries: user, assistant(tool_use), user(tool_result with the same id)
    msgs = client.requests[1]['messages']
    assert [m['role'] for m in msgs] == ['user', 'assistant', 'user']
    assert msgs[2]['content'][0]['tool_use_id'] == 't1'


def test_any_colour_becomes_empty_filter():
    agent, _, robot = make([
        NS(stop_reason='tool_use', content=[tool_use('t1', 'find_object', {'label': 'chair', 'color': 'any'})]),
        NS(stop_reason='end_turn', content=[text('ok')]),
    ])
    agent.ask('找把椅子')
    assert robot.calls == [('find_object', 'chair', '')]


def test_robot_error_is_reported_to_claude_not_raised():
    agent, client, _ = make([
        NS(stop_reason='tool_use', content=[tool_use('t1', 'find_object', {'label': 'chair', 'color': 'any'})]),
        NS(stop_reason='end_turn', content=[text('机器人系统没在运行。')]),
    ], robot=FakeRobot(fail=True))
    assert agent.ask('找椅子') == '机器人系统没在运行。'
    result = client.requests[1]['messages'][2]['content'][0]
    assert result['is_error'] is True and 'not running' in result['content']


def test_plain_answer_without_tools():
    agent, _, robot = make([NS(stop_reason='end_turn', content=[text('我认不出钥匙。')])])
    assert agent.ask('帮我找钥匙') == '我认不出钥匙。'
    assert robot.calls == []


def test_history_is_kept_across_requests():
    agent, client, _ = make([NS(stop_reason='end_turn', content=[text('a')]),
                             NS(stop_reason='end_turn', content=[text('b')])])
    agent.ask('第一句')
    agent.ask('第二句')
    assert [m['role'] for m in client.requests[1]['messages']] == ['user', 'assistant', 'user']


def test_refusal_is_handled():
    agent, _, _ = make([NS(stop_reason='refusal', content=[])])
    assert '拒绝' in agent.ask('...')


def test_tools_are_strict_and_closed():
    tools = build_tools(['home', 'north'])
    for t in tools:
        s = t['input_schema']
        assert t['strict'] is True and s['additionalProperties'] is False
        assert set(s['required']) == set(s['properties'])
    find = next(t for t in tools if t['name'] == 'find_object')
    assert len(COCO_CLASSES) == 80 and find['input_schema']['properties']['label']['enum'] == COCO_CLASSES
    go = next(t for t in tools if t['name'] == 'go_to')
    assert go['input_schema']['properties']['place']['enum'] == ['home', 'north']
