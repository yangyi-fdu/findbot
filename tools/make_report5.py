"""Build the step-5 HTML report: natural-language transcript, photos, probe results, interview Q&A."""
import base64
import html
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.expanduser('~/ros2_ws/src/findbot/findbot_perception'))
from findbot_perception.semantic_memory import SemanticMemory  # noqa: E402

R = os.path.expanduser('~/findbot_report')
HERE = os.path.dirname(os.path.abspath(__file__))
CN = {'fire hydrant': '消防栓', 'chair': '椅子', 'person': '人', 'suitcase': '行李箱'}
COLOR_CN = {'red': '红色', 'blue': '蓝色', 'green': '绿色', 'black': '黑色', 'gray': '灰色', 'white': '白色', '': ''}


def esc(s):
    return html.escape(str(s))


def photo_for(label):
    f = os.path.join(R, 'memory', 'semantic_map.yaml')
    if not label or not os.path.exists(f):
        return ''
    mem = SemanticMemory()
    mem.load_list(yaml.safe_load(open(f)) or [])
    objs = [o for o in mem.confirmed() if o.label == label]
    if not objs:
        return ''
    o = objs[0]
    p = os.path.join(R, 'memory', 'snapshots', f'{o.id}.jpg')
    if not os.path.exists(p):
        return ''
    uri = 'data:image/jpeg;base64,' + base64.b64encode(open(p, 'rb').read()).decode()
    cap = f'机器人拍到的{COLOR_CN.get(o.color, o.color)}{CN.get(label, label)}，看到 {o.observations} 次'
    return f'<figure class="shot"><img src="{uri}" alt="{esc(cap)}"><figcaption>{esc(cap)}</figcaption></figure>'


def turn_html(r):
    calls = ''.join(f'<code class="call">{esc(c)}</code>' for c in r['tool_calls']) or \
        '<span class="none">没有调用工具</span>'
    fb = ''.join(f'<li>{esc(x)}</li>' for x in r['robot_feedback'])
    fb = f'<ul class="fb">{fb}</ul>' if fb else ''
    truth = ''
    if r['robot_to_target_m'] is not None:
        truth = (f'<p class="truth">Gazebo 真实位置：机器人停在 ({r["robot_truth"][0]:.2f}, {r["robot_truth"][1]:.2f})，'
                 f'离{CN.get(r["target"], r["target"])} <b>{r["robot_to_target_m"]:.2f} m</b></p>')
    err = ''.join(f'<p class="err">{esc(e)}</p>' for e in r.get('errors') or [])
    return f'''
    <article class="turn">
      <p class="you"><span class="who">你</span>{esc(r["request"])}</p>
      <div class="work">
        <div class="row"><span class="tag">模型调用</span><div class="calls">{calls}</div></div>
        {f'<div class="row"><span class="tag">机器人</span>{fb}</div>' if fb else ''}
        {photo_for(r["target"])}
        {truth}{err}
      </div>
      <p class="bot"><span class="who">findbot</span>{esc(r["reply"]) or "（没有回复）"}</p>
      <p class="time">用时 {r["wall_seconds"]} s</p>
    </article>'''


def probe_html(probe):
    if not probe:
        return '<p>（没有测试数据）</p>'
    rows, seen = [], {}
    for r in probe['rows']:
        seen.setdefault(r['request'], []).append(r)
    for req, runs in seen.items():
        marks = ''.join(f'<span class="mark {"ok" if x["pass"] else "bad"}">{"✓" if x["pass"] else "✗"}</span>' for x in runs)
        calls = {json.dumps(x['calls'], ensure_ascii=False) for x in runs}
        detail = '<br>'.join(esc(c) for c in sorted(calls))
        rows.append(f'<tr><td>{esc(req)}</td><td class="marks">{marks}</td><td class="calls">{detail}</td></tr>')
    return ''.join(rows)


def main():
    live = json.load(open(os.path.join(R, 'step5_live.json')))
    pf = os.path.join(R, 'step5_probe_glm-4.7-flash.json')
    probe = json.load(open(pf)) if os.path.exists(pf) else None
    page = open(os.path.join(HERE, 'report5_template.html')).read()
    subs = {
        'TURNS': ''.join(turn_html(r) for r in live),
        'PROBE_ROWS': probe_html(probe),
        'PROBE_OK': probe['passed'] if probe else '—',
        'PROBE_ALL': probe['total'] if probe else '—',
        'N_LIVE': len(live),
    }
    for k, v in subs.items():
        page = page.replace(f'%%{k}%%', str(v))
    out = os.path.join(R, 'report5.html')
    open(out, 'w').write(page)
    print('wrote', out, f'{len(page) / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
