"""Record a demo run for the README animation (the system must already be running).

Sends natural-language requests through `ros2 run findbot_llm chat` and, at the same time,
records what the robot does: its pose (TF), the Nav2 plan, the annotated camera image and
the semantic map. Everything is timestamped with wall-clock time.

  python3 demo/record_demo.py "Find the red fire hydrant" "Take me to the chair"

Writes ~/findbot_demo/{timeline.json, cam/*.jpg}; render with demo/render_gif.py.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from nav_msgs.msg import Path
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Image
from tf2_ros import Buffer, TransformException, TransformListener

from findbot_interfaces.srv import QueryObjects

OUT = os.path.expanduser('~/findbot_demo')


class Recorder(Node):

    def __init__(self):
        super().__init__('demo_recorder')
        self.t0 = time.time()
        self.data = {'poses': [], 'plans': [], 'objects': [], 'frames': [], 'chat': []}
        self.bridge = CvBridge()
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.create_subscription(Image, 'detections/image', self.on_image, 2)
        self.create_subscription(Path, 'plan', self.on_plan, 2)
        self.query = self.create_client(QueryObjects, 'semantic_map/query')
        self.create_timer(0.25, self.on_pose)
        self.create_timer(2.0, self.on_objects)

    def now(self):
        return round(time.time() - self.t0, 2)

    def on_image(self, msg):
        name = f'{len(self.data["frames"]):05d}.jpg'
        cv2.imwrite(os.path.join(OUT, 'cam', name), self.bridge.imgmsg_to_cv2(msg, 'bgr8'),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.data['frames'].append([self.now(), name])

    def on_plan(self, msg):
        pts = [(round(p.pose.position.x, 3), round(p.pose.position.y, 3)) for p in msg.poses[::5]]
        self.data['plans'].append([self.now(), pts])

    def on_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
        except TransformException:
            return
        q = t.transform.rotation
        yaw = 2 * __import__('math').atan2(q.z, q.w)
        p = t.transform.translation
        self.data['poses'].append([self.now(), round(p.x, 3), round(p.y, 3), round(yaw, 3)])

    def on_objects(self):
        if not self.query.service_is_ready():
            return
        fut = self.query.call_async(QueryObjects.Request())
        fut.add_done_callback(lambda f: self.data['objects'].append(
            [self.now(), [[o.label, o.color, round(o.position.x, 3), round(o.position.y, 3)]
                          for o in (f.result().objects if f.result() else [])]]))


def run_chat(rec, request):
    """Run one chat request, timestamping every line it prints."""
    rec.data['chat'].append([rec.now(), f'you: {request}'])
    env = {**os.environ, 'PYTHONUNBUFFERED': '1'}
    p = subprocess.Popen(['ros2', 'run', 'findbot_llm', 'chat', request], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, env=env)
    for line in p.stdout:
        line = line.rstrip()
        if line.strip() and not line.startswith('['):   # skip the "[zhipu / model]" banner
            rec.data['chat'].append([rec.now(), line])
            print(line, flush=True)
    p.wait()


def main():
    requests = sys.argv[1:] or ['Find the red fire hydrant', 'Take me to the chair']
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.path.join(OUT, 'cam'))
    rclpy.init()
    rec = Recorder()
    ex = MultiThreadedExecutor(num_threads=3)
    ex.add_node(rec)
    threading.Thread(target=ex.spin, daemon=True).start()
    time.sleep(5)                                    # let TF and the first images arrive
    for r in requests:
        run_chat(rec, r)
        time.sleep(4)                                # a short pause after each answer
    rec.data['end'] = rec.now()
    with open(os.path.join(OUT, 'timeline.json'), 'w') as f:
        json.dump(rec.data, f)
    print(f'recorded {rec.data["end"]:.0f} s: {len(rec.data["poses"])} poses, '
          f'{len(rec.data["frames"])} camera frames, {len(rec.data["chat"])} chat lines')
    ex.shutdown()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
