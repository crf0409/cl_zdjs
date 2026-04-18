"""
Obstacle Avoidance ROS 2 Node.

Subscribes to YOLO detection results, applies a three-zone reactive
avoidance algorithm, and publishes velocity commands.
"""

import rclpy
from rclpy.node import Node
from vision_msgs.msg import Detection2DArray
from geometry_msgs.msg import Twist, TwistStamped


class ObstacleAvoidanceNode(Node):
    def __init__(self):
        super().__init__('obstacle_avoidance')

        # Declare parameters
        self.declare_parameter('linear_speed', 0.2)
        self.declare_parameter('angular_speed', 0.5)
        self.declare_parameter('threat_area_threshold', 0.05)
        self.declare_parameter('emergency_area_threshold', 0.15)
        self.declare_parameter('image_width', 640)
        self.declare_parameter('image_height', 480)
        self.declare_parameter('obstacle_classes', [
            'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter',
            'bench', 'chair', 'couch', 'dining table', 'bottle',
            'backpack', 'umbrella', 'handbag', 'suitcase', 'potted plant',
            'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
        ])

        # Get parameters
        self.linear_speed = self.get_parameter('linear_speed').get_parameter_value().double_value
        self.angular_speed = self.get_parameter('angular_speed').get_parameter_value().double_value
        self.threat_threshold = self.get_parameter('threat_area_threshold').get_parameter_value().double_value
        self.emergency_threshold = self.get_parameter('emergency_area_threshold').get_parameter_value().double_value
        self.image_width = self.get_parameter('image_width').get_parameter_value().integer_value
        self.image_height = self.get_parameter('image_height').get_parameter_value().integer_value
        self.obstacle_classes = self.get_parameter('obstacle_classes').get_parameter_value().string_array_value

        self.image_area = self.image_width * self.image_height

        # Zone boundaries (left third, center third, right third)
        self.left_boundary = self.image_width / 3.0
        self.right_boundary = 2.0 * self.image_width / 3.0

        # Subscribers
        self.detection_sub = self.create_subscription(
            Detection2DArray, '/yolo/detections', self.detection_callback, 10)

        # Publishers - TurtleBot3 Gazebo bridge expects TwistStamped on /cmd_vel
        self.cmd_vel_pub = self.create_publisher(TwistStamped, '/cmd_vel', 10)

        # Timer: publish stop if no detections received for 0.5s
        self.last_detection_time = self.get_clock().now()
        self.timer = self.create_timer(0.1, self.safety_timer_callback)

        self.get_logger().info('Obstacle avoidance node started')

    def _make_twist_stamped(self, linear_x, angular_z):
        """Create a TwistStamped message."""
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = linear_x
        msg.twist.angular.z = angular_z
        return msg

    def detection_callback(self, msg: Detection2DArray):
        self.last_detection_time = self.get_clock().now()

        # Compute threat levels for each zone
        left_threat = 0.0
        center_threat = 0.0
        right_threat = 0.0

        for det in msg.detections:
            # Filter by obstacle classes
            if det.id and det.id not in self.obstacle_classes:
                continue

            cx = det.bbox.center.position.x
            w = det.bbox.size_x
            h = det.bbox.size_y
            area_ratio = (w * h) / self.image_area

            # Skip small detections (not threatening)
            if area_ratio < 0.01:
                continue

            # Assign threat to zone based on center x position
            if cx < self.left_boundary:
                left_threat = max(left_threat, area_ratio)
            elif cx > self.right_boundary:
                right_threat = max(right_threat, area_ratio)
            else:
                center_threat = max(center_threat, area_ratio)

        # Generate velocity command based on threat levels
        has_left = left_threat >= self.threat_threshold
        has_center = center_threat >= self.threat_threshold
        has_right = right_threat >= self.threat_threshold
        emergency_center = center_threat >= self.emergency_threshold

        linear_x = 0.0
        angular_z = 0.0

        if emergency_center:
            linear_x = 0.0
            if left_threat <= right_threat:
                angular_z = self.angular_speed * 1.5
            else:
                angular_z = -self.angular_speed * 1.5
            self.get_logger().warn('EMERGENCY: Large obstacle ahead! Stopping and turning.')

        elif has_left and has_center and has_right:
            linear_x = 0.0
            angular_z = 0.0
            self.get_logger().warn('All zones blocked - stopping.')

        elif has_center:
            linear_x = 0.0
            if left_threat <= right_threat:
                angular_z = self.angular_speed
            else:
                angular_z = -self.angular_speed
            self.get_logger().info('Center obstacle - turning.')

        elif has_left and has_right:
            linear_x = self.linear_speed * 0.5
            angular_z = 0.0
            self.get_logger().info('Both sides have obstacles - slowing down.')

        elif has_left:
            linear_x = self.linear_speed * 0.7
            angular_z = -self.angular_speed * 0.5
            self.get_logger().info('Left obstacle - turning right.')

        elif has_right:
            linear_x = self.linear_speed * 0.7
            angular_z = self.angular_speed * 0.5
            self.get_logger().info('Right obstacle - turning left.')

        else:
            linear_x = self.linear_speed
            angular_z = 0.0

        self.cmd_vel_pub.publish(self._make_twist_stamped(linear_x, angular_z))

    def safety_timer_callback(self):
        """Stop the robot if no detections received for too long."""
        elapsed = (self.get_clock().now() - self.last_detection_time).nanoseconds / 1e9
        if elapsed > 1.0:
            self.cmd_vel_pub.publish(
                self._make_twist_stamped(self.linear_speed * 0.3, 0.0))


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_vel_pub.publish(node._make_twist_stamped(0.0, 0.0))
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
