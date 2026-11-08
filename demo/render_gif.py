"""Render a recorded demo (demo/record_demo.py) into an animated GIF and an MP4.

Left: the SLAM map with the robot, its trail, the Nav2 plan and the remembered objects.
Right: the robot's camera with YOLO boxes, and the conversation.

  python3 demo/render_gif.py [--speed 12] [--fps 8] [--width 960]

Writes docs/media/demo.gif and ~/findbot_demo/demo.mp4
"""
import argparse
import json
import math
import os
import textwrap

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

DEMO = os.path.expanduser('~/findbot_demo')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(REPO, 'findbot_bringup', 'maps', 'tb3_world')

BG, PANEL, INK, MUTED = (244, 246, 245), (255, 255, 255), (27, 36, 34), (95, 108, 104)
FREE, WALL, UNKNOWN = (250, 251, 250), (43, 51, 48), (214, 220, 217)
TEAL, ORANGE, BLUE, GREEN = (15, 107, 98), (217, 119, 6), (37, 99, 235), (21, 128, 61)
OBJ_COLORS = {'red': (220, 38, 38), 'blue': (37, 99, 235), 'green': (22, 163, 74), 'black': (40, 40, 40),
              'gray': (120, 120, 120), 'white': (200, 200, 200), 'yellow': (202, 138, 4), 'orange': (234, 88, 12)}


def font(size, bold=False, mono=False):
    names = (['DejaVuSansMono-Bold.ttf' if bold else 'DejaVuSansMono.ttf'] if mono
             else ['DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'])
    for n in names:
        p = os.path.join('/usr/share/fonts/truetype/dejavu', n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def latest(series, t):
    """Last entry of a time-sorted [[t, ...], ...] list with time <= t."""
    best = None
    for item in series:
        if item[0] > t:
            break
        best = item
    return best


class MapView:

    def __init__(self, size):
        meta = yaml.safe_load(open(MAP + '.yaml'))
        img = cv2.imread(MAP + '.pgm', cv2.IMREAD_GRAYSCALE)
        self.res, (self.ox, self.oy, _) = meta['resolution'], meta['origin']
        self.h = img.shape[0]
        known = np.argwhere(img != 205)
        (r0, c0), (r1, c1) = known.min(0) - 6, known.max(0) + 6
        self.crop = (max(c0, 0), max(r0, 0))
        img = img[max(r0, 0):r1, max(c0, 0):c1]
        self.scale = min(size[0] / img.shape[1], size[1] / img.shape[0])
        rgb = np.zeros((*img.shape, 3), np.uint8)
        rgb[:] = UNKNOWN
        rgb[img > 250] = FREE
        rgb[img < 50] = WALL
        big = cv2.resize(rgb, (int(img.shape[1] * self.scale), int(img.shape[0] * self.scale)),
                         interpolation=cv2.INTER_NEAREST)
        self.base = Image.fromarray(big)

    def px(self, x, y):
        col = (x - self.ox) / self.res - self.crop[0]
        row = self.h - (y - self.oy) / self.res - self.crop[1]
        return col * self.scale, row * self.scale

    def draw(self, tl, t):
        im = self.base.copy()
        d = ImageDraw.Draw(im, 'RGBA')
        plan = latest(tl['plans'], t)
        if plan and t - plan[0] < 3 and len(plan[1]) > 1:
            d.line([self.px(*p) for p in plan[1]], fill=ORANGE + (230,), width=3)
        trail = [self.px(p[1], p[2]) for p in tl['poses'] if p[0] <= t]
        if len(trail) > 1:
            d.line(trail, fill=TEAL + (150,), width=3)
        objs = latest(tl['objects'], t)
        for label, color, x, y in (objs[1] if objs else []):
            cx, cy = self.px(x, y)
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=OBJ_COLORS.get(color, MUTED) + (255,),
                      outline=(255, 255, 255, 255), width=2)
            text = f'{color} {label}'.strip()
            f = font(14, bold=True)
            w = d.textlength(text, font=f)
            tx = min(max(cx - w / 2, 4), im.width - w - 4)
            d.rounded_rectangle([tx - 4, cy - 34, tx + w + 4, cy - 14], 4, fill=(255, 255, 255, 230))
            d.text((tx, cy - 32), text, fill=INK, font=f)
        pose = latest(tl['poses'], t)
        if pose:
            cx, cy = self.px(pose[1], pose[2])
            r = 0.17 / self.res * self.scale
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=TEAL + (255,), outline=(255, 255, 255, 255), width=2)
            d.line([cx, cy, cx + 1.6 * r * math.cos(pose[3]), cy - 1.6 * r * math.sin(pose[3])],
                   fill=(255, 255, 255, 255), width=3)
        return im


def chat_lines(tl, t, width_chars):
    """Styled, wrapped conversation lines visible at time t."""
    out = []
    for ts, line in tl['chat']:
        if ts > t:
            break
        s = line.strip()
        if s.startswith('you:'):
            style, s = 'you', s
        elif s.startswith('→ tool call'):
            style, s = 'tool', s.replace('→ tool call ', '→ ')
        elif s.startswith('['):
            style = 'fb'
        elif s.startswith('🤖'):
            style, s = 'bot', 'findbot: ' + s[1:].strip()
        else:
            continue
        for i, part in enumerate(textwrap.wrap(s, width_chars) or ['']):
            out.append((style, part if i == 0 else '  ' + part))
    return out


def render_frame(tl, t, mapview, size, speed):
    W, H = size
    frame = Image.new('RGB', size, BG)
    d = ImageDraw.Draw(frame)
    mw = H                                   # square map panel on the left
    m = mapview.draw(tl, t)
    frame.paste(m, ((mw - m.width) // 2, (H - m.height) // 2 + 14))
    d.text((14, 10), 'findbot', fill=INK, font=font(22, bold=True))
    d.text((112, 16), 'ROS 2 Jazzy · Nav2 · YOLO RGB-D · LLM tool use', fill=MUTED, font=font(13))
    d.text((14, H - 26), f'×{speed:g} speed', fill=MUTED, font=font(13))

    rx, rw = mw, W - mw
    cam = latest(tl['frames'], t)
    ch = int(rw * 0.75)
    if cam:
        img = Image.open(os.path.join(DEMO, 'cam', cam[1])).convert('RGB').resize((rw, ch))
        frame.paste(img, (rx, 0))
    d.rectangle([rx, 0, W, ch], outline=(214, 222, 219))
    d.rounded_rectangle([rx + 8, 8, rx + 128, 30], 4, fill=(0, 0, 0))
    d.text((rx + 14, 11), 'robot camera', fill=(255, 255, 255), font=font(13))

    d.rectangle([rx, ch, W, H], fill=PANEL)
    styles = {'you': (BLUE, font(15, bold=True)), 'tool': (ORANGE, font(13, mono=True)),
              'fb': (MUTED, font(13, mono=True)), 'bot': (GREEN, font(15, bold=True))}
    lines = chat_lines(tl, t, width_chars=int(rw / 8.6))
    max_lines = (H - ch - 16) // 19
    y = ch + 10
    for style, text in lines[-max_lines:]:
        color, f = styles[style]
        d.text((rx + 12, y), text, fill=color, font=f)
        y += 19
    return frame


def timeline_times(tl, speed, fps, hold_s):
    """Video frame times in recording time: constant speed-up, with holds on new messages."""
    step = speed / fps
    holds = sorted(ts for ts, line in tl['chat'] if line.startswith('you:') or line.strip().startswith('🤖'))
    times, t, hi = [], 0.0, 0
    while t <= tl['end']:
        times.append(t)
        while hi < len(holds) and holds[hi] <= t:
            times += [holds[hi]] * int(hold_s * fps)
            hi += 1
        t += step
    times += [tl['end']] * int(2 * fps)          # rest on the final frame
    return times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--speed', type=float, default=12)
    ap.add_argument('--fps', type=int, default=8)
    ap.add_argument('--width', type=int, default=960)
    ap.add_argument('--hold', type=float, default=1.6)
    a = ap.parse_args()
    tl = json.load(open(os.path.join(DEMO, 'timeline.json')))
    size = (a.width, int(a.width * 9 / 16))
    mapview = MapView((size[1] - 40, size[1] - 40))
    times = timeline_times(tl, a.speed, a.fps, a.hold)
    frames = [render_frame(tl, t, mapview, size, a.speed) for t in times]

    os.makedirs(os.path.join(REPO, 'docs', 'media'), exist_ok=True)
    gif = os.path.join(REPO, 'docs', 'media', 'demo.gif')
    pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(gif, save_all=True, append_images=pal[1:], duration=int(1000 / a.fps), loop=0, optimize=True)
    mp4 = os.path.join(DEMO, 'demo.mp4')
    vw = cv2.VideoWriter(mp4, cv2.VideoWriter_fourcc(*'mp4v'), a.fps, size)
    for f in frames:
        vw.write(cv2.cvtColor(np.asarray(f), cv2.COLOR_RGB2BGR))
    vw.release()
    print(f'{len(frames)} frames, {len(frames) / a.fps:.0f} s; gif {os.path.getsize(gif) / 1e6:.1f} MB -> {gif}; '
          f'mp4 -> {mp4}')
    frames[len(frames) // 2].save(os.path.join(DEMO, 'preview.png'))


if __name__ == '__main__':
    main()
