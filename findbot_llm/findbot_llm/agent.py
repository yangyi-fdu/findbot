"""The language agent: a manual tool-use loop around the Claude Messages API.

The robot side is injected (`robot`: an object with find_object / list_known_objects /
go_to methods returning strings), so the loop can be tested without ROS or the network.
"""
import json

MODEL = 'claude-opus-5-5'
MAX_TOOL_ROUNDS = 6   # safety stop: a single request never needs more than a few robot actions


class RobotAgent:

    def __init__(self, client, robot, tools, system, model=MODEL, log=print):
        self.client = client
        self.robot = robot
        self.tools = tools
        self.system = system
        self.model = model
        self.log = log
        self.messages = []   # whole conversation; the API is stateless, so we resend it each turn

    def ask(self, user_text: str) -> str:
        """One user request -> as many tool calls as Claude needs -> final reply text."""
        self.messages.append({'role': 'user', 'content': user_text})
        for _ in range(MAX_TOOL_ROUNDS + 1):
            response = self.create()
            # Append the full content (text, thinking and tool_use blocks), never a rebuilt
            # copy: the history must stay append-only for the API to accept it next turn.
            self.messages.append({'role': 'assistant', 'content': response.content})

            if response.stop_reason == 'refusal':
                return '（这个请求被模型拒绝了，换个说法试试。）'
            if response.stop_reason == 'max_tokens':
                return '（回复被截断了。）'
            calls = [b for b in response.content if b.type == 'tool_use']
            if response.stop_reason != 'tool_use' or not calls:
                return self.text_of(response)

            results = []
            for call in calls:
                self.log(f'  → 调用工具 {call.name}({json.dumps(call.input, ensure_ascii=False)})')
                try:
                    out = self.run_tool(call.name, call.input)
                    results.append({'type': 'tool_result', 'tool_use_id': call.id, 'content': out})
                except Exception as e:  # report robot-side failures to Claude instead of crashing
                    results.append({'type': 'tool_result', 'tool_use_id': call.id,
                                    'content': f'Error: {e}', 'is_error': True})
            # All results of one turn go back in a single user message.
            self.messages.append({'role': 'user', 'content': results})
        return '（工具调用次数太多，已停止。）'

    def create(self):
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=self.system,
            tools=self.tools,
            messages=self.messages,
            # Routing a spoken command to a tool is easy; low effort keeps replies fast and cheap.
            output_config={'effort': 'low'},
            # If a safety classifier declines, retry on a fallback model chosen by the API.
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        )

    def run_tool(self, name, args):
        if name == 'find_object':
            return self.robot.find_object(args['label'], '' if args['color'] == 'any' else args['color'])
        if name == 'list_known_objects':
            return self.robot.list_known_objects()
        if name == 'go_to':
            return self.robot.go_to(args['place'])
        raise ValueError(f'unknown tool {name}')

    @staticmethod
    def text_of(response):
        return '\n'.join(b.text for b in response.content if b.type == 'text').strip()
