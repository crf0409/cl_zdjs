"""
YOLO Detection ROS 2 Node.

Subscribes to camera images, runs YOLO inference, and publishes
Detection2DArray messages and annotated images.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
from cv_bridge import CvBridge
from ultralytics import YOLO


class YoloDetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_detector')

        # Declare parameters
        self.declare_parameter('model_path', '/home/siton02/md0/crf/cl_zdjs/project1_yolo_obstacle/yolo11s.pt')
        self.declare_parameter('confidence_threshold', 0.25)
        self.declare_parameter('device', 'cuda:0')
        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('target_classes', [
            'person', 'bicycle', 'car', 'motorcycle', 'bus', 'truck',
            'traffic light', 'fire hydrant', 'stop sign', 'parking meter',
            'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'backpack', 'umbrella', 'handbag', 'suitcase', 'potted plant',
            'chair', 'couch', 'dining table', 'bottle',
        ])

        # Get parameters
        model_path = self.get_parameter('model_path').get_parameter_value().string_value
        self.conf_threshold = self.get_parameter('confidence_threshold').get_parameter_value().double_value
        device = self.get_parameter('device').get_parameter_value().string_value
        image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        self.target_classes = self.get_parameter('target_classes').get_parameter_value().string_array_value

        # Load YOLO model
        self.get_logger().info(f'Loading YOLO model from: {model_path}')
        self.model = YOLO(model_path)
        self.model.to(device)
        self.get_logger().info(f'YOLO model loaded on {device}')

        self.bridge = CvBridge()

        # Subscribers
        self.image_sub = self.create_subscription(
            Image, image_topic, self.image_callback, 10)

        # Publishers
        self.detection_pub = self.create_publisher(
            Detection2DArray, '/yolo/detections', 10)
        self.annotated_pub = self.create_publisher(
            Image, '/yolo/annotated_image', 10)

        self.get_logger().info(f'YOLO detector node started. Subscribing to: {image_topic}')

    def image_callback(self, msg: Image):
        # Convert ROS Image to OpenCV
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'cv_bridge conversion failed: {e}')
            return

        # Run YOLO inference
        results = self.model(cv_image, verbose=False, conf=self.conf_threshold)

        # Build Detection2DArray message
        detection_array = Detection2DArray()
        detection_array.header = msg.header

        for r in results:
            boxes = r.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i])
                cls_name = r.names[cls_id]

                # Filter by target classes if specified
                if self.target_classes and cls_name not in self.target_classes:
                    continue

                conf = float(boxes.conf[i])
                xyxy = boxes.xyxy[i].cpu().numpy()

                det = Detection2D()
                det.header = msg.header

                # Set bounding box (center + size format)
                det.bbox.center.position.x = float((xyxy[0] + xyxy[2]) / 2.0)
                det.bbox.center.position.y = float((xyxy[1] + xyxy[3]) / 2.0)
                det.bbox.size_x = float(xyxy[2] - xyxy[0])
                det.bbox.size_y = float(xyxy[3] - xyxy[1])

                # Set hypothesis
                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = cls_name
                hyp.hypothesis.score = conf
                det.results.append(hyp)

                # Store class name in detection id for downstream use
                det.id = cls_name

                detection_array.detections.append(det)

        # Publish detections
        self.detection_pub.publish(detection_array)

        # Publish annotated image
        annotated = results[0].plot()
        annotated_msg = self.bridge.cv2_to_imgmsg(annotated, encoding='bgr8')
        annotated_msg.header = msg.header
        self.annotated_pub.publish(annotated_msg)


def main(args=None):
    rclpy.init(args=args)
    node = YoloDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
