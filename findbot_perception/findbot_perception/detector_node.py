"""YOLO object detector that localizes detections in the map frame.

camera/image + camera/depth_image + camera/camera_info
  -> YOLO boxes -> median depth in each box -> 3D point (camera optical frame)
  -> TF -> point in `target_frame` (map) -> dominant colour
  -> publishes findbot_interfaces/ObjectObservationArray on `detections`,
     an annotated image on `detections/image` and RViz markers on `detections/markers`.
"""
import os
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from tf2_geometry_msgs import do_transform_point
from tf2_ros import Buffer, TransformException, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

from findbot_interfaces.msg import ObjectObservation, ObjectObservationArray
from findbot_perception.geometry import box_depth, deproject, dominant_color, shrink_box


class ObjectDetector(Node):

    def __init__(self):
        super().__init__('object_detector')
        self.declare_parameter('model', 'yolo11n.pt')
        self.declare_parameter('confidence', 0.4)
        self.declare_parameter('max_rate', 2.0)          # Hz; YOLO on CPU is the bottleneck
        self.declare_parameter('target_frame', 'map')
        self.declare_parameter('image_size', 640)
        # Classes to ignore (e.g. things that are part of the arena).
        self.declare_parameter('ignore_classes', [''])

        from ultralytics import YOLO  # heavy import, keep it out of module import time
        model = os.path.expanduser(self.get_parameter('model').value)
        self.get_logger().info(f'loading {model} ...')
        self.model = YOLO(model)
        self.bridge = CvBridge()
        self.camera_info = None
        self.last_run = 0.0

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.create_subscription(CameraInfo, 'camera/camera_info', self.on_info, qos_profile_sensor_data)
        rgb = Subscriber(self, Image, 'camera/image', qos_profile=qos_profile_sensor_data)
        depth = Subscriber(self, Image, 'camera/depth_image', qos_profile=qos_profile_sensor_data)
        # RGB and depth come from the same RGB-D sensor; pair frames taken within 50 ms.
        self.sync = ApproximateTimeSynchronizer([rgb, depth], queue_size=5, slop=0.05)
        self.sync.registerCallback(self.on_images)

        self.pub = self.create_publisher(ObjectObservationArray, 'detections', 10)
        self.image_pub = self.create_publisher(Image, 'detections/image', 1)
        self.marker_pub = self.create_publisher(MarkerArray, 'detections/markers', 10)
        self.get_logger().info('object_detector ready')

    def on_info(self, msg: CameraInfo):
        self.camera_info = msg

    def on_images(self, rgb_msg: Image, depth_msg: Image):
        now = time.monotonic()
        if self.camera_info is None or now - self.last_run < 1.0 / self.get_parameter('max_rate').value:
            return
        self.last_run = now

        bgr = self.bridge.imgmsg_to_cv2(rgb_msg, 'bgr8')
        depth = self.bridge.imgmsg_to_cv2(depth_msg, 'passthrough')  # 32FC1, metres
        k = self.camera_info.k
        fx, fy, cx, cy = k[0], k[4], k[2], k[5]

        result = self.model(bgr, conf=self.get_parameter('confidence').value,
                            imgsz=self.get_parameter('image_size').value, verbose=False)[0]
        ignore = set(self.get_parameter('ignore_classes').value)

        out = ObjectObservationArray()
        out.header.stamp = rgb_msg.header.stamp
        out.header.frame_id = self.get_parameter('target_frame').value
        annotated = bgr.copy()

        for xyxy, cls, score in zip(result.boxes.xyxy.cpu().numpy(),
                                    result.boxes.cls.cpu().numpy().astype(int),
                                    result.boxes.conf.cpu().numpy()):
            label = self.model.names[cls]
            if label in ignore:
                continue
            x1, y1, x2, y2 = xyxy
            z = box_depth(depth, (x1, y1, x2, y2))
            if z is None:
                continue
            # Box centre is a good enough estimate of the object's centre for navigation.
            u, v = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            p_cam = deproject(u, v, z, fx, fy, cx, cy)
            p_map = self.to_target_frame(p_cam, rgb_msg.header)
            if p_map is None:
                continue
            ix1, iy1, ix2, iy2 = shrink_box(x1, y1, x2, y2, 0.5)
            color = dominant_color(bgr[max(0, iy1):iy2, max(0, ix1):ix2])

            obs = ObjectObservation()
            obs.header = out.header
            obs.label, obs.color, obs.confidence = label, color, float(score)
            obs.position = p_map
            obs.distance = float(z)
            obs.snapshot = self.snapshot(bgr, x1, y1, x2, y2, rgb_msg.header)
            out.observations.append(obs)

            cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(annotated, f'{color} {label} {score:.2f} {z:.1f}m', (int(x1), max(15, int(y1) - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        self.pub.publish(out)
        self.publish_markers(out)
        img_msg = self.bridge.cv2_to_imgmsg(annotated, 'bgr8')
        img_msg.header = rgb_msg.header
        self.image_pub.publish(img_msg)
        if out.observations:
            self.get_logger().info(', '.join(
                f'{o.color} {o.label} @({o.position.x:.2f},{o.position.y:.2f})' for o in out.observations))

    @staticmethod
    def snapshot(bgr, x1, y1, x2, y2, header) -> CompressedImage:
        """JPEG crop of the detection with a little context around it."""
        h, w = bgr.shape[:2]
        px, py = 0.15 * (x2 - x1), 0.15 * (y2 - y1)
        crop = bgr[max(0, int(y1 - py)):min(h, int(y2 + py)), max(0, int(x1 - px)):min(w, int(x2 + px))]
        msg = CompressedImage()
        msg.header = header
        msg.format = 'jpeg'
        ok, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            msg.data = buf.tobytes()
        return msg

    def to_target_frame(self, p_cam, header):
        pt = PointStamped()
        pt.header = header
        pt.point.x, pt.point.y, pt.point.z = p_cam
        try:
            tf = self.tf_buffer.lookup_transform(
                self.get_parameter('target_frame').value, header.frame_id,
                rclpy.time.Time.from_msg(header.stamp), timeout=Duration(seconds=0.2))
        except TransformException as e:
            self.get_logger().warn(f'TF {header.frame_id} -> map unavailable: {e}', throttle_duration_sec=5.0)
            return None
        return do_transform_point(pt, tf).point

    def publish_markers(self, arr: ObjectObservationArray):
        markers = MarkerArray()
        clear = Marker()
        clear.action = Marker.DELETEALL
        markers.markers.append(clear)
        for i, o in enumerate(arr.observations):
            for kind in (Marker.SPHERE, Marker.TEXT_VIEW_FACING):
                m = Marker()
                m.header = arr.header
                m.ns = 'detections'
                m.id = 2 * i + (kind == Marker.TEXT_VIEW_FACING)
                m.type = kind
                m.pose.position = o.position
                m.pose.orientation.w = 1.0
                m.color.a = 1.0
                if kind == Marker.SPHERE:
                    m.scale.x = m.scale.y = m.scale.z = 0.15
                    m.color.g = 1.0
                else:
                    m.pose.position.z += 0.3
                    m.scale.z = 0.15
                    m.color.r = m.color.g = m.color.b = 1.0
                    m.text = f'{o.color} {o.label}'
                m.lifetime = Duration(seconds=2.0).to_msg()
                markers.markers.append(m)
        self.marker_pub.publish(markers)


def main(args=None):
    rclpy.init(args=args)
    node = ObjectDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
