"""Build the step-4 HTML report (photos of remembered objects, map, scenario results).

Reads ~/findbot_report/{memory/, step4_results.json, tb3_world.pgm/yaml}
Writes ~/findbot_report/report.html (self-contained, images embedded as data URIs).
"""
import base64
import html
import json
import math
import os
import sys

import cv2
import numpy as np
import yaml

sys.path.insert(0, os.path.expanduser('~/ros2_ws/src/findbot/findbot_perception'))
from findbot_perception.semantic_memory import SemanticMemory  # noqa: E402

R = os.path.expanduser('~/findbot_report')
TRUTH = {  # map frame; label the detector uses -> (Chinese name, true position)
    'fire hydrant': ('消防栓', (4.0, -0.4)), 'chair': ('椅子', (1.0, -1.8)),
    'person': ('人', (1.0, 2.8)), 'suitcase': ('行李箱', (-0.1, 1.4)),
}
EXTRA_TRUTH = {'红色书包': (3.0, 2.8), '蓝色书包': (3.0, -1.8)}
CN_COLOR = {'red': '红色', 'blue': '蓝色', 'green': '绿色', 'yellow': '黄色', 'orange': '橙色',
            'purple': '紫色', 'cyan': '青色', 'black': '黑色', 'white': '白色', 'gray': '灰色', '': ''}
STATE_CN = {'QUERYING': '查记忆', 'EXPLORING': '去别处找', 'LOOKING': '原地张望', 'APPROACHING': '靠近物体'}


def b64(path_or_bytes, mime='image/jpeg'):
    data = open(path_or_bytes, 'rb').read() if isinstance(path_or_bytes, str) else path_or_bytes
    return f'data:{mime};base64,{base64.b64encode(data).decode()}'


def load_memory():
    mem = SemanticMemory()
    f = os.path.join(R, 'memory', 'semantic_map.yaml')
    if os.path.exists(f):
        mem.load_list(yaml.safe_load(open(f)) or [])
    return mem.confirmed()


def nearest_truth(o):
    best = None
    for label, (cn, (tx, ty)) in TRUTH.items():
        d = math.dist((o.x, o.y), (tx, ty))
        if best is None or d < best[2]:
            best = (cn, (tx, ty), d, label)
    return best


def draw_map(objs, results):
    meta = yaml.safe_load(open(os.path.join(R, 'tb3_world.yaml')))
    img = cv2.imread(os.path.join(R, 'tb3_world.pgm'), cv2.IMREAD_GRAYSCALE)
    res, (ox, oy, _) = meta['resolution'], meta['origin']
    s = 6
    h = img.shape[0]
    canvas = np.full((h * s, img.shape[1] * s, 4), 0, np.uint8)
    big = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
    canvas[big < 50] = (60, 66, 64, 255)       # walls / pillars
    canvas[big > 250] = (255, 255, 255, 0)     # free space -> transparent (page background shows)
    canvas[(big >= 50) & (big <= 250)] = (200, 205, 203, 90)

    def px(x, y):
        return int(((x - ox) / res) * s), int((h - (y - oy) / res) * s)

    for cn, (tx, ty) in [(v[0], v[1]) for v in TRUTH.values()] + list(EXTRA_TRUTH.items()):
        cx, cy = px(tx, ty)
        cv2.drawMarker(canvas, (cx, cy), (150, 150, 150, 255), cv2.MARKER_TILTED_CROSS, 22, 2)
    for i, o in enumerate(objs, 1):
        cx, cy = px(o.x, o.y)
        cv2.circle(canvas, (cx, cy), 17, (98, 107, 15, 255), -1, cv2.LINE_AA)
        cv2.putText(canvas, str(i), (cx - 7, cy + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255, 255), 2, cv2.LINE_AA)
    sx, sy = px(0, 0)
    cv2.circle(canvas, (sx, sy), 9, (43, 98, 217, 255), -1, cv2.LINE_AA)
    for r in results:
        if r.get('robot_to_object_m') is not None and r['success']:
            cx, cy = px(*r['robot_truth'])
            cv2.rectangle(canvas, (cx - 8, cy - 8), (cx + 8, cy + 8), (43, 98, 217, 255), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.png', canvas)
    return b64(buf.tobytes(), 'image/png')


def main():
    objs = load_memory()
    results = json.load(open(os.path.join(R, 'step4_results.json'))) if os.path.exists(
        os.path.join(R, 'step4_results.json')) else []
    errs = []
    cards = []
    for i, o in enumerate(objs, 1):
        cn, (tx, ty), d, tlabel = nearest_truth(o)
        real_name = cn if tlabel == o.label else ('红色书包' if math.dist((o.x, o.y), EXTRA_TRUTH['红色书包']) < 0.6 else cn)
        if tlabel == o.label:
            errs.append(d)
        snap = os.path.join(R, 'memory', 'snapshots', f'{o.id}.jpg')
        img = f'<img src="{b64(snap)}" alt="机器人拍到的{html.escape(o.label)}">' if os.path.exists(snap) \
            else '<div class="noimg">没有照片</div>'
        mismatch = '' if tlabel == o.label else f'<p class="warn">YOLO 叫它“{html.escape(o.label)}”，其实是{real_name}</p>'
        cards.append(f'''
      <figure class="obj">
        <span class="num">{i}</span>
        {img}
        <figcaption>
          <h3>{CN_COLOR.get(o.color, o.color)}{html.escape(TRUTH.get(o.label, (o.label,))[0])} <code>{html.escape(o.color)} {html.escape(o.label)}</code></h3>
          {mismatch}
          <dl>
            <dt>估计位置</dt><dd>({o.x:.2f}, {o.y:.2f})</dd>
            <dt>真实位置</dt><dd>({tx:.2f}, {ty:.2f})</dd>
            <dt>误差</dt><dd><b>{d * 100:.0f} cm</b></dd>
            <dt>看到次数</dt><dd>{o.observations}</dd>
          </dl>
        </figcaption>
      </figure>''')

    rows = []
    for r in results:
        # Scenario ④ is designed to fail ("report failure instead of wandering off").
        r['expected'] = '应报告失败' not in r['name']
        r['passed'] = r['success'] == r['expected']
        pills = ''.join(f'<span class="pill">{STATE_CN.get(s, s)}</span>' for s in r['states'])
        stop = f'{r["robot_to_object_m"]:.2f} m' if r.get('robot_to_object_m') is not None and r['success'] else '—'
        outcome = ('找到了' if r['success'] else '没找到') + ('，符合预期' if r['passed'] else '，不符合预期')
        rows.append(f'''
        <tr class="{'ok' if r['passed'] else 'fail'}">
          <td><span class="badge">{outcome}</span></td>
          <td>{html.escape(r['name'])}<div class="cmd">find {html.escape(r['query'])}</div></td>
          <td class="flow">{pills}</td>
          <td class="n">{r['wall_seconds']} s</td>
          <td class="n">{stop}</td>
          <td class="msg">{html.escape(r['message'].lstrip('✅❌ '))}</td>
        </tr>''')

    n_ok = sum(r['passed'] for r in results)
    mean_err = f'{np.mean(errs) * 100:.0f}' if errs else '—'
    map_uri = draw_map(objs, results)
    page = TEMPLATE
    for k, v in {'CARDS': ''.join(cards) or '<p>（没有记住的物体）</p>', 'ROWS': ''.join(rows),
                 'N_OK': n_ok, 'N_ALL': len(results), 'N_OBJ': len(objs), 'MEAN_ERR': mean_err,
                 'MAP_URI': map_uri}.items():
        page = page.replace(f'%%{k}%%', str(v))
    out = os.path.join(R, 'report.html')
    open(out, 'w').write(page)
    print('wrote', out, f'{len(page) / 1e6:.1f} MB')


TEMPLATE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_template.html')).read()

if __name__ == '__main__':
    main()
