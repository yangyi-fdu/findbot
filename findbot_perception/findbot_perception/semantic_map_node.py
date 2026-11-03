"""Semantic map: remembers where objects are.

Subscribes to `detections` (ObjectObservationArray, map frame), fuses them with
SemanticMemory, and offers:
  - service  `semantic_map/query`   (findbot_interfaces/srv/QueryObjects)
  - topic    `semantic_map/markers` (RViz: confirmed objects with labels)
The memory is saved to `memory_file` on shutdown and reloaded on start.
"""
import os

import rclpy
import yaml
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Point
from nav_msgs.msg import OccupancyGrid
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from visualization_msgs.msg import Marker, MarkerArray

from findbot_interfaces.msg import ObjectObservationArray, SemanticObject
from findbot_interfaces.srv import QueryObjects
from findbot_perception.geometry import near_occupied
from findbot_perception.semantic_memory import SemanticMemory


class SemanticMapNode(Node):

    def __init__(self):
        super().__init__('semantic_map')
        self.declare_parameter('merge_radius', 0.6)
        self.declare_parameter('min_observations', 3)
        self.declare_parameter('conflict_radius', 0.4)
        self.declare_parameter('min_confidence', 0.45)
        # Labels YOLO tends to hallucinate in this simulated arena (walls/pillars).
        self.declare_parameter('ignore_labels', ['airplane', 'tv', 'refrigerator', 'toilet'])
        self.declare_parameter('memory_file', os.path.expanduser('~/.findbot/semantic_map.yaml'))
        self.declare_parameter('load_memory', True)

        p = self.get_parameter
        self.memory = SemanticMemory(p('merge_radius').value, p('min_observations').value,
                                     p('conflict_radius').value)
        self.memory_file = p('memory_file').value
        # one JPEG per remembered object: <dir of memory_file>/snapshots/<id>.jpg
        self.snapshot_dir = os.path.join(os.path.dirname(self.memory_file), 'snapshots')
        if p('load_memory').value and os.path.exists(self.memory_file):
            with open(self.memory_file) as f:
                self.memory.load_list(yaml.safe_load(f) or [])
            self.get_logger().info(f'loaded {len(self.memory.objects)} objects from {self.memory_file}')

        # The static map was built before the objects were placed, so a detection that
        # lands on a mapped obstacle is really a wall or pillar mistaken for an object.
        self.declare_parameter('static_map_reject_radius', 0.1)
        self.map = None
        map_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, 'map', self.on_map, map_qos)
        self.rejected_static = 0

        self.create_subscription(ObjectObservationArray, 'detections', self.on_detections, 10)
        self.create_service(QueryObjects, 'semantic_map/query', self.on_query)
        self.marker_pub = self.create_publisher(MarkerArray, 'semantic_map/markers', 10)
        self.create_timer(1.0, self.publish_markers)
        # Save periodically, not only on shutdown: a killed process or power loss
        # would otherwise lose everything learned in this session.
        self.dirty = False
        self.create_timer(10.0, self.save_if_dirty)
        self.known = set()   # ids already announced as confirmed

    def on_map(self, msg: OccupancyGrid):
        self.map = msg

    def on_static_obstacle(self, x, y) -> bool:
        if self.map is None:
            return False
        info = self.map.info
        return near_occupied(self.map.data, info.width, info.height, info.resolution,
                             info.origin.position.x, info.origin.position.y, x, y,
                             self.get_parameter('static_map_reject_radius').value)

    def on_detections(self, msg: ObjectObservationArray):
        ignore = set(self.get_parameter('ignore_labels').value)
        min_conf = self.get_parameter('min_confidence').value
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        for o in msg.observations:
            if o.label in ignore or o.confidence < min_conf:
                continue
            if self.on_static_obstacle(o.position.x, o.position.y):
                self.rejected_static += 1
                if self.rejected_static % 20 == 1:
                    self.get_logger().info(f'rejected {self.rejected_static} detections on mapped '
                                           f'walls/pillars (latest: {o.label})')
                continue
            obj = self.memory.add(o.label, o.position.x, o.position.y, o.position.z, o.confidence, o.color, stamp)
            self.dirty = True
            # Keep the most confident photo of every object (used by reports and the LLM step).
            if o.snapshot.data and o.confidence > obj.snapshot_confidence:
                os.makedirs(self.snapshot_dir, exist_ok=True)
                with open(os.path.join(self.snapshot_dir, f'{obj.id}.jpg'), 'wb') as f:
                    f.write(bytes(o.snapshot.data))
                obj.snapshot_confidence = float(o.confidence)
        for obj in self.memory.confirmed():
            if obj.id not in self.known:
                self.known.add(obj.id)
                self.get_logger().info(f'new object: {obj.color} {obj.label} at ({obj.x:.2f}, {obj.y:.2f})')

    def on_query(self, req: QueryObjects.Request, res: QueryObjects.Response):
        res.objects = [self.to_msg(o) for o in self.memory.query(req.label, req.color)]
        self.get_logger().info(f'query label={req.label!r} color={req.color!r} -> {len(res.objects)} match(es)')
        return res

    @staticmethod
    def to_msg(o) -> SemanticObject:
        m = SemanticObject()
        m.id, m.label, m.color = o.id, o.label, o.color
        m.position = Point(x=o.x, y=o.y, z=o.z)
        m.observations, m.confidence = o.observations, float(o.confidence)
        m.last_seen = Time(sec=int(o.last_seen), nanosec=int((o.last_seen % 1) * 1e9))
        return m

    def publish_markers(self):
        arr = MarkerArray()
        clear = Marker()
        clear.action = Marker.DELETEALL
        arr.markers.append(clear)
        for o in self.memory.confirmed():
            for kind in (Marker.CYLINDER, Marker.TEXT_VIEW_FACING):
                m = Marker()
                m.header.frame_id = 'map'
                m.ns = 'semantic_map'
                m.id = 2 * o.id + (kind == Marker.TEXT_VIEW_FACING)
                m.type = kind
                m.pose.position = Point(x=o.x, y=o.y, z=0.25 if kind == Marker.CYLINDER else 0.75)
                m.pose.orientation.w = 1.0
                m.color.a = 0.9
                if kind == Marker.CYLINDER:
                    m.scale.x = m.scale.y = 0.3
                    m.scale.z = 0.5
                    m.color.r, m.color.g, m.color.b = 1.0, 0.6, 0.0
                else:
                    m.scale.z = 0.2
                    m.color.r = m.color.g = m.color.b = 1.0
                    m.text = f'{o.color} {o.label} ({o.observations})'
                arr.markers.append(m)
        self.marker_pub.publish(arr)

    def save_if_dirty(self):
        if self.dirty:
            self.save(quiet=True)
            self.dirty = False

    def save(self, quiet=False):
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
        tmp = self.memory_file + '.tmp'
        with open(tmp, 'w') as f:
            yaml.safe_dump(self.memory.to_list(), f, sort_keys=False)
        os.replace(tmp, self.memory_file)  # atomic: never leaves a half-written file
        if not quiet:
            print(f'[semantic_map] saved {len(self.memory.objects)} objects to {self.memory_file}')


def main(args=None):
    rclpy.init(args=args)
    node = SemanticMapNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.save()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
