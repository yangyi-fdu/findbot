import json
from types import SimpleNamespace as NS

import pytest

from findbot_llm.agent import ClaudeBackend, RobotAgent, ZhipuBackend
from findbot_llm.tools import COCO_CLASSES, SYSTEM_PROMPT, build_tools, openai_style_tools, validate_args

PLACES = ['home', 'north']


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


# ---------------------------------------------------------------- fake Claude
def c_text(t):
    return NS(type='text', text=t)


def c_tool(i, name, args):
    return NS(type='tool_use', id=i, name=name, input=args)


class FakeClaude:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.requests.append({**kw, 'messages': list(kw['messages'])})
        return self.responses.pop(0)


# ---------------------------------------------------------------- fake Zhipu (OpenAI-style)
def z_reply(text='', calls=(), finish='stop'):
    tool_calls = [NS(id=i, type='function', function=NS(name=n, arguments=a)) for i, n, a in calls] or None
    return NS(choices=[NS(finish_reason=finish, message=NS(content=text, tool_calls=tool_calls))])


class FakeZhipu:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.requests.append({**kw, 'messages': list(kw['messages'])})
        return self.responses.pop(0)


def claude_agent(responses, robot=None):
    client, robot = FakeClaude(responses), robot or FakeRobot()
    return RobotAgent(ClaudeBackend(client, PLACES, SYSTEM_PROMPT), robot, PLACES, log=lambda *_: None), client, robot


def zhipu_agent(responses, robot=None):
    client, robot = FakeZhipu(responses), robot or FakeRobot()
    return RobotAgent(ZhipuBackend(client, PLACES, SYSTEM_PROMPT), robot, PLACES, log=lambda *_: None), client, robot


# ---------------------------------------------------------------- Claude backend
def test_claude_tool_call_then_answer():
    agent, client, robot = claude_agent([
        NS(stop_reason='tool_use', content=[c_text('我去找找'),
                                            c_tool('t1', 'find_object', {'label': 'fire hydrant', 'color': 'red'})]),
        NS(stop_reason='end_turn', content=[c_text('找到了红色消防栓。')]),
    ])
    assert agent.ask('帮我找红色的消防栓') == '找到了红色消防栓。'
    assert robot.calls == [('find_object', 'fire hydrant', 'red')]
    msgs = client.requests[1]['messages']
    assert [m['role'] for m in msgs] == ['user', 'assistant', 'user']
    assert msgs[2]['content'][0]['tool_use_id'] == 't1'


def test_claude_robot_error_goes_back_as_is_error():
    agent, client, _ = claude_agent([
        NS(stop_reason='tool_use', content=[c_tool('t1', 'find_object', {'label': 'chair', 'color': 'any'})]),
        NS(stop_reason='end_turn', content=[c_text('机器人系统没在运行。')]),
    ], robot=FakeRobot(fail=True))
    assert agent.ask('找椅子') == '机器人系统没在运行。'
    result = client.requests[1]['messages'][2]['content'][0]
    assert result['is_error'] is True and 'not running' in result['content']


def test_claude_refusal_is_handled():
    agent, _, _ = claude_agent([NS(stop_reason='refusal', content=[])])
    assert '拒绝' in agent.ask('...')


# ---------------------------------------------------------------- Zhipu backend
def test_zhipu_tool_call_then_answer():
    agent, client, robot = zhipu_agent([
        z_reply(calls=[('c1', 'find_object', json.dumps({'label': 'chair', 'color': 'any'}))], finish='tool_calls'),
        z_reply('找到椅子了。'),
    ])
    assert agent.ask('找把椅子') == '找到椅子了。'
    assert robot.calls == [('find_object', 'chair', '')]
    msgs = client.requests[1]['messages']
    assert [m['role'] for m in msgs] == ['system', 'user', 'assistant', 'tool']
    assert msgs[2]['tool_calls'][0]['id'] == 'c1' and msgs[3]['tool_call_id'] == 'c1'
    assert client.requests[0]['tool_choice'] == 'auto'


def test_zhipu_invalid_label_is_rejected_before_the_robot_moves():
    agent, client, robot = zhipu_agent([
        z_reply(calls=[('c1', 'find_object', json.dumps({'label': 'keys', 'color': 'any'}))], finish='tool_calls'),
        z_reply('抱歉，机器人认不出钥匙。'),
    ])
    assert agent.ask('帮我找钥匙') == '抱歉，机器人认不出钥匙。'
    assert robot.calls == []
    tool_msg = client.requests[1]['messages'][3]
    assert tool_msg['content'].startswith('Error:') and 'not a detector class' in tool_msg['content']


def test_zhipu_malformed_json_arguments_are_reported():
    agent, client, robot = zhipu_agent([
        z_reply(calls=[('c1', 'go_to', '{"place": "north"')], finish='tool_calls'),
        z_reply('好的。'),
    ])
    agent.ask('去北边')
    assert robot.calls == [] and client.requests[1]['messages'][3]['content'].startswith('Error:')


def test_zhipu_content_filter_is_handled():
    agent, _, _ = zhipu_agent([z_reply(finish='sensitive')])
    assert '审核' in agent.ask('...')


def test_history_is_kept_across_requests():
    agent, client, _ = zhipu_agent([z_reply('a'), z_reply('b')])
    agent.ask('第一句')
    agent.ask('第二句')
    assert [m['role'] for m in client.requests[1]['messages']] == ['system', 'user', 'assistant', 'user']


def test_too_many_tool_rounds_stops():
    call = ('c', 'list_known_objects', '{}')
    agent, _, robot = zhipu_agent([z_reply(calls=[call], finish='tool_calls')] * 10)
    assert '太多' in agent.ask('一直查')
    assert len(robot.calls) == 7


# ---------------------------------------------------------------- tools
def test_tools_are_strict_and_closed():
    for t in build_tools(PLACES):
        s = t['input_schema']
        assert t['strict'] is True and s['additionalProperties'] is False
        assert set(s['required']) == set(s['properties'])
    find = next(t for t in build_tools(PLACES) if t['name'] == 'find_object')
    assert len(COCO_CLASSES) == 80 and find['input_schema']['properties']['label']['enum'] == COCO_CLASSES


def test_openai_style_tools_match():
    names = [t['function']['name'] for t in openai_style_tools(PLACES)]
    assert names == [t['name'] for t in build_tools(PLACES)]
    assert all(t['type'] == 'function' for t in openai_style_tools(PLACES))


@pytest.mark.parametrize('name, args', [
    ('find_object', {'label': 'keys', 'color': 'any'}),
    ('find_object', {'label': 'chair', 'color': 'pink'}),
    ('go_to', {'place': 'kitchen'}),
    ('fly', {}),
    ('go_to', 'north'),
])
def test_validate_args_rejects(name, args):
    with pytest.raises(ValueError):
        validate_args(name, args, PLACES)


def test_validate_args_accepts():
    validate_args('find_object', {'label': 'fire hydrant', 'color': 'red'}, PLACES)
    validate_args('go_to', {'place': 'north'}, PLACES)
    validate_args('list_known_objects', {}, PLACES)
