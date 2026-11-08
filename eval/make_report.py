"""Build a self-contained HTML report from ~/findbot_report (run after eval/run_eval.sh find).

Shows the photo the robot kept of every remembered object, its position error against
ground truth, a map with estimated and true positions, and the FindObject scenarios.
Writes ~/findbot_report/report.html
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'findbot_perception'))
from findbot_perception.semantic_memory import SemanticMemory  # noqa: E402

from ground_truth import OBJECTS  # noqa: E402

R = os.path.expanduser('~/findbot_report')
STATE_NAMES = {'QUERYING': 'check memory', 'EXPLORING': 'search', 'LOOKING': 'look around',
               'APPROACHING': 'approach'}


def data_uri(data, mime):
    return f'data:{mime};base64,{base64.b64encode(data).decode()}'


def nearest_truth(o):
    return min(((name, xy, math.dist((o.x, o.y), xy)) for name, xy in OBJECTS.items()), key=lambda t: t[2])


def draw_map(objs, results):
    meta = yaml.safe_load(open(os.path.join(R, 'tb3_world.yaml')))
    img = cv2.imread(os.path.join(R, 'tb3_world.pgm'), cv2.IMREAD_GRAYSCALE)
    res, (ox, oy, _) = meta['resolution'], meta['origin']
    s, h = 6, img.shape[0]
    big = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((*big.shape, 4), np.uint8)
    canvas[big < 50] = (60, 66, 64, 255)                         # walls and pillars
    canvas[(big >= 50) & (big <= 250)] = (200, 205, 203, 90)    # unknown

    def px(x, y):
        return int((x - ox) / res * s), int((h - (y - oy) / res) * s)

    for xy in OBJECTS.values():
        cv2.drawMarker(canvas, px(*xy), (150, 150, 150, 255), cv2.MARKER_TILTED_CROSS, 22, 2)
    for i, o in enumerate(objs, 1):
        c = px(o.x, o.y)
        cv2.circle(canvas, c, 17, (98, 107, 15, 255), -1, cv2.LINE_AA)
        cv2.putText(canvas, str(i), (c[0] - 7, c[1] + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255, 255), 2,
                    cv2.LINE_AA)
    cv2.circle(canvas, px(0, 0), 9, (43, 98, 217, 255), -1, cv2.LINE_AA)
    for r in results:
        if r.get('robot_to_object_m') is not None:
            x, y = px(*r['robot_position'])
            cv2.rectangle(canvas, (x - 8, y - 8), (x + 8, y + 8), (43, 98, 217, 255), 2, cv2.LINE_AA)
    return data_uri(cv2.imencode('.png', canvas)[1].tobytes(), 'image/png')


def main():
    mem = SemanticMemory()
    mem.load_list(yaml.safe_load(open(os.path.join(R, 'memory', 'semantic_map.yaml'))) or [])
    objs = mem.confirmed()
    results = json.load(open(os.path.join(R, 'find_results.json')))

    cards, errors = [], []
    for i, o in enumerate(objs, 1):
        truth_name, (tx, ty), d = nearest_truth(o)
        same = truth_name.split(' (')[0] == o.label
        if same:
            errors.append(d)
        snap = os.path.join(R, 'memory', 'snapshots', f'{o.id}.jpg')
        img = (f'<img src="{data_uri(open(snap, "rb").read(), "image/jpeg")}" alt="camera crop of the {html.escape(o.label)}">'
               if os.path.exists(snap) else '<div class="noimg">no photo</div>')
        note = '' if same else f'<p class="warn">Detected as “{html.escape(o.label)}”; it is the {truth_name}.</p>'
        cards.append(f'''
      <figure class="obj"><span class="num">{i}</span>{img}
        <figcaption><h3>{html.escape(f"{o.color} {o.label}".strip())}</h3>{note}
          <dl><dt>estimate</dt><dd>({o.x:.2f}, {o.y:.2f})</dd><dt>ground truth</dt><dd>({tx:.2f}, {ty:.2f})</dd>
          <dt>error</dt><dd><b>{d * 100:.0f} cm</b></dd><dt>sightings</dt><dd>{o.observations}</dd></dl>
        </figcaption></figure>''')

    rows = []
    for r in results:
        flow = ''.join(f'<span class="pill">{STATE_NAMES.get(s, s)}</span>' for s in r['states'])
        stop = f'{r["robot_to_object_m"]:.2f} m' if r.get('robot_to_object_m') is not None else '—'
        outcome = ('found' if r['success'] else 'not found') + (', as expected' if r['passed'] else ', unexpected')
        rows.append(f'''
        <tr class="{'ok' if r['passed'] else 'fail'}"><td><span class="badge">{outcome}</span></td>
          <td>{html.escape(r['name'])}<div class="cmd">find {html.escape(r['query'])}</div></td>
          <td class="flow">{flow}</td><td class="n">{r['wall_seconds']} s</td><td class="n">{stop}</td></tr>''')

    page = open(os.path.join(HERE, 'report_template.html')).read()
    for k, v in {'CARDS': ''.join(cards), 'ROWS': ''.join(rows), 'MAP': draw_map(objs, results),
                 'N_OK': sum(r['passed'] for r in results), 'N_ALL': len(results), 'N_OBJ': len(objs),
                 'MEAN_ERR': f'{np.mean(errors) * 100:.0f}' if errors else '—'}.items():
        page = page.replace(f'%%{k}%%', str(v))
    open(os.path.join(R, 'report.html'), 'w').write(page)
    print('wrote', os.path.join(R, 'report.html'))


if __name__ == '__main__':
    main()
