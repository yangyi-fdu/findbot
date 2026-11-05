"""The language agent: a manual tool-use loop with swappable LLM backends.

RobotAgent owns the loop (ask -> tool calls -> results -> ... -> answer) and the robot;
a backend owns one provider's message format and API call:

  ZhipuBackend  - Zhipu GLM via the official zai-sdk (OpenAI-style messages)
  ClaudeBackend - Claude via the official anthropic SDK (Messages API)

Both the robot and the API clients are injected, so everything here is testable
without ROS or the network.
"""
import json
from dataclasses import dataclass, field

from findbot_llm.tools import openai_style_tools, build_tools, validate_args

MAX_TOOL_ROUNDS = 6   # safety stop: a single request never needs more than a few robot actions


@dataclass
class ToolCall:
    id: str
    name: str
    args: object          # parsed JSON (or the raw string if it was not valid JSON)


@dataclass
class Turn:
    text: str = ''
    calls: list = field(default_factory=list)
    problem: str = ''     # set when the turn ended abnormally (refusal, truncation, filter)


class ClaudeBackend:
    """Claude Messages API. History is append-only: the full response content goes back."""

    def __init__(self, client, places, system, model='claude-opus-5-5'):
        self.client, self.system, self.model = client, system, model
        self.tools = build_tools(places)
        self.messages = []

    def add_user(self, text):
        self.messages.append({'role': 'user', 'content': text})

    def step(self) -> Turn:
        r = self.client.beta.messages.create(
            model=self.model, max_tokens=16000, system=self.system, tools=self.tools,
            messages=self.messages,
            output_config={'effort': 'low'},                 # routing a command is easy
            betas=['server-side-fallback-2026-07-01'], fallbacks='default',
        )
        self.messages.append({'role': 'assistant', 'content': r.content})
        text = '\n'.join(b.text for b in r.content if b.type == 'text').strip()
        if r.stop_reason == 'refusal':
            return Turn(text, problem='模型拒绝了这个请求，换个说法试试。')
        if r.stop_reason == 'max_tokens':
            return Turn(text, problem='回复被截断了。')
        calls = [ToolCall(b.id, b.name, b.input) for b in r.content if b.type == 'tool_use']
        return Turn(text, calls if r.stop_reason == 'tool_use' else [])

    def add_tool_results(self, results):
        # All results of one turn go back in a single user message.
        self.messages.append({'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': cid, 'content': out, **({'is_error': True} if err else {})}
            for cid, out, err in results]})


class ZhipuBackend:
    """Zhipu GLM chat completions (OpenAI-style tool calls), via zai-sdk."""

    def __init__(self, client, places, system, model='glm-4.7-flash'):
        self.client, self.model = client, model
        self.tools = openai_style_tools(places)
        self.messages = [{'role': 'system', 'content': system}]

    def add_user(self, text):
        self.messages.append({'role': 'user', 'content': text})

    def step(self) -> Turn:
        r = self.client.chat.completions.create(
            model=self.model, messages=self.messages, tools=self.tools,
            tool_choice='auto',          # the only value Zhipu supports
            temperature=0.2,             # we want consistent tool choices, not creativity
        )
        choice = r.choices[0]
        msg = choice.message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError:
                args = tc.function.arguments           # validate_args will reject it
            calls.append(ToolCall(tc.id, tc.function.name, args))
        # Echo the assistant turn back exactly as the API expects it next time.
        turn_msg = {'role': 'assistant', 'content': msg.content or ''}
        if msg.tool_calls:
            turn_msg['tool_calls'] = [{'id': tc.id, 'type': 'function',
                                       'function': {'name': tc.function.name,
                                                    'arguments': tc.function.arguments}}
                                      for tc in msg.tool_calls]
        self.messages.append(turn_msg)
        text = (msg.content or '').strip()
        if choice.finish_reason == 'sensitive':
            return Turn(text, problem='请求被内容安全审核拦截了，换个说法试试。')
        if choice.finish_reason == 'length':
            return Turn(text, problem='回复被截断了。')
        return Turn(text, calls)

    def add_tool_results(self, results):
        for cid, out, err in results:
            self.messages.append({'role': 'tool', 'tool_call_id': cid,
                                  'content': f'Error: {out}' if err else out})


class RobotAgent:

    def __init__(self, backend, robot, places, log=print):
        self.backend, self.robot, self.places, self.log = backend, robot, list(places), log

    def ask(self, user_text: str) -> str:
        """One user request -> as many tool calls as the model needs -> final reply text."""
        self.backend.add_user(user_text)
        for _ in range(MAX_TOOL_ROUNDS + 1):
            turn = self.backend.step()
            if turn.problem:
                return f'（{turn.problem}）'
            if not turn.calls:
                return turn.text
            results = []
            for call in turn.calls:
                self.log(f'  → 调用工具 {call.name}({json.dumps(call.args, ensure_ascii=False)})')
                try:
                    validate_args(call.name, call.args, self.places)
                    results.append((call.id, self.run_tool(call.name, call.args), False))
                except Exception as e:  # bad arguments or a robot-side failure: tell the model
                    self.log(f'    ✗ {e}')
                    results.append((call.id, str(e), True))
            self.backend.add_tool_results(results)
        return '（工具调用次数太多，已停止。）'

    def run_tool(self, name, args):
        if name == 'find_object':
            color = args.get('color', 'any')
            return self.robot.find_object(args['label'], '' if color == 'any' else color)
        if name == 'list_known_objects':
            return self.robot.list_known_objects()
        return self.robot.go_to(args['place'])
