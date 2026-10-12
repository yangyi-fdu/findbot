"""Reactive wanderer: drive forward, turn away from obstacles seen by the lidar.

Covers the ROS 2 basics in one node: subscription (/scan), publisher (/cmd_vel),
timer-driven control loop, parameters, and a TF listener.
"""
import math

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformException, TransformListener


def sector_min(scan: LaserScan, lo_deg: float, hi_deg: float) -> float:
    """Closest valid range whose beam angle lies in [lo_deg, hi_deg] (0 = straight ahead)."""
    best = math.inf
    for i, r in enumerate(scan.ranges):
        if not (scan.range_min < r < scan.range_max):
            continue  # inf / nan / below sensor minimum
        a = math.degrees(scan.angle_min + i * scan.angle_increment)
        a = (a + 180.0) % 360.0 - 180.0  # wrap to [-180, 180)
        if lo_deg <= a <= hi_deg:
            best = min(best, r)
    return best


class Wanderer(Node):

    def __init__(self):
        super().__init__('wanderer')
        self.declare_parameter('linear_speed', 0.15)       # m/s
        self.declare_parameter('angular_speed', 0.6)       # rad/s
        self.declare_parameter('safe_distance', 0.45)      # m, start turning below this
        self.declare_parameter('front_half_angle', 30.0)   # deg, width of the "front" cone
        self.declare_parameter('scan_timeout', 1.0)        # s, stop if lidar goes silent

        self.scan = None
        self.turning = False
        self.turn_dir = 1.0

        self.cmd_pub = self.create_publisher(TwistStamped, 'cmd_vel', 10)
        # Sensor data is best-effort; this QoS also matches reliable publishers.
        self.create_subscription(LaserScan, 'scan', self.on_scan, qos_profile_sensor_data)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.create_timer(0.1, self.control_loop)
        self.create_timer(2.0, self.report_pose)
        self.get_logger().info('wanderer started')

    def on_scan(self, msg: LaserScan):
        self.scan = msg

    def param(self, name):
        return self.get_parameter(name).value

    def control_loop(self):
        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.header.frame_id = 'base_link'

        if self.scan is None or self.scan_age() > self.param('scan_timeout'):
            self.cmd_pub.publish(cmd)  # all zeros: stop when blind
            return

        half = self.param('front_half_angle')
        front = sector_min(self.scan, -half, half)
        safe = self.param('safe_distance')

        if front < safe:
            if not self.turning:
                # Pick the turn direction once per obstacle, towards the more open side,
                # so the robot does not oscillate left/right.
                left = sector_min(self.scan, half, 100.0)
                right = sector_min(self.scan, -100.0, -half)
                self.turn_dir = 1.0 if left >= right else -1.0
                self.turning = True
                self.get_logger().info(
                    f'obstacle {front:.2f} m ahead, turning {"left" if self.turn_dir > 0 else "right"}')
            cmd.twist.angular.z = self.turn_dir * self.param('angular_speed')
        elif self.turning and front < safe * 1.5:
            # Hysteresis: keep turning until there is clear margin in front.
            cmd.twist.angular.z = self.turn_dir * self.param('angular_speed')
        else:
            self.turning = False
            # Slow down smoothly as obstacles get closer.
            scale = max(0.3, min(1.0, (front - safe) / safe))
            cmd.twist.linear.x = self.param('linear_speed') * scale

        self.cmd_pub.publish(cmd)

    def scan_age(self) -> float:
        stamp = rclpy.time.Time.from_msg(self.scan.header.stamp)
        return (self.get_clock().now() - stamp).nanoseconds * 1e-9

    def report_pose(self):
        try:
            t = self.tf_buffer.lookup_transform(
                'odom', 'base_footprint', rclpy.time.Time(), timeout=Duration(seconds=0.1))
        except TransformException as e:
            self.get_logger().warn(f'TF not available yet: {e}')
            return
        q = t.transform.rotation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        p = t.transform.translation
        self.get_logger().info(f'pose in odom: x={p.x:.2f} y={p.y:.2f} yaw={math.degrees(yaw):.0f} deg')

    def stop(self):
        self.cmd_pub.publish(TwistStamped())


def main(args=None):
    rclpy.init(args=args)
    node = Wanderer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
