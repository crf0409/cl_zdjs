#!/usr/bin/env python3
"""
Experiment data recorder for YOLO obstacle avoidance car.

Records detection results, velocity commands, and system metrics
from ROS 2 topics into CSV files for post-experiment plotting.

Usage:
    source /opt/ros/jazzy/setup.bash
    source install/setup.bash
    python3 record_experiment.py [--duration 120]
"""

import argparse
import csv
import os
import signal
import sys
import time
from datetime import datetime

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from vision_msgs.msg import Detection2DArray
from geometry_msgs.msg import Twist, TwistStamped
from sensor_msgs.msg import Image


class ExperimentRecorder(Node):
    def __init__(self, output_dir, duration):
        super().__init__('experiment_recorder')
        self.output_dir = output_dir
        self.duration = duration
        self.start_time = time.time()
        os.makedirs(output_dir, exist_ok=True)

        # CSV files
        self.det_file = open(os.path.join(output_dir, 'detections.csv'), 'w', newline='')
        self.det_writer = csv.writer(self.det_file)
        self.det_writer.writerow([
            'timestamp', 'elapsed_s', 'num_detections',
            'det_classes', 'det_confidences', 'det_areas',
            'det_center_xs', 'det_center_ys'
        ])

        self.vel_file = open(os.path.join(output_dir, 'cmd_vel.csv'), 'w', newline='')
        self.vel_writer = csv.writer(self.vel_file)
        self.vel_writer.writerow([
            'timestamp', 'elapsed_s', 'linear_x', 'angular_z'
        ])

        self.stats_file = open(os.path.join(output_dir, 'stats.csv'), 'w', newline='')
        self.stats_writer = csv.writer(self.stats_file)
        self.stats_writer.writerow([
            'timestamp', 'elapsed_s', 'detection_hz',
            'total_detections_so_far', 'total_vel_cmds_so_far'
        ])

        # Counters
        self.total_detections = 0
        self.total_vel_cmds = 0
        self.det_timestamps = []
        self.image_count = 0

        # Subscribers
        self.create_subscription(
            Detection2DArray, '/yolo/detections', self.detection_cb, 10)
        self.create_subscription(
            TwistStamped, '/cmd_vel', self.vel_cb, 10)
        self.create_subscription(
            Image, '/camera/image_raw', self.image_cb, 10)

        # Stats timer (every 2 seconds)
        self.create_timer(2.0, self.stats_cb)

        # Duration timer
        self.create_timer(1.0, self.check_duration)

        self.get_logger().info(
            f'Experiment recorder started. Duration: {duration}s. Output: {output_dir}')

    def elapsed(self):
        return time.time() - self.start_time

    def detection_cb(self, msg):
        now = time.time()
        elapsed = self.elapsed()
        self.det_timestamps.append(now)

        classes = []
        confidences = []
        areas = []
        center_xs = []
        center_ys = []

        for det in msg.detections:
            cls_name = det.id if det.id else 'unknown'
            conf = det.results[0].hypothesis.score if det.results else 0.0
            area = det.bbox.size_x * det.bbox.size_y
            cx = det.bbox.center.position.x
            cy = det.bbox.center.position.y

            classes.append(cls_name)
            confidences.append(f'{conf:.3f}')
            areas.append(f'{area:.0f}')
            center_xs.append(f'{cx:.1f}')
            center_ys.append(f'{cy:.1f}')

        n = len(msg.detections)
        self.total_detections += n

        self.det_writer.writerow([
            f'{now:.3f}', f'{elapsed:.2f}', n,
            '|'.join(classes), '|'.join(confidences), '|'.join(areas),
            '|'.join(center_xs), '|'.join(center_ys)
        ])

    def vel_cb(self, msg):
        elapsed = self.elapsed()
        self.total_vel_cmds += 1
        twist = msg.twist  # TwistStamped -> .twist
        self.vel_writer.writerow([
            f'{time.time():.3f}', f'{elapsed:.2f}',
            f'{twist.linear.x:.4f}', f'{twist.angular.z:.4f}'
        ])

    def image_cb(self, msg):
        self.image_count += 1

    def stats_cb(self):
        now = time.time()
        elapsed = self.elapsed()

        # Compute detection Hz over last 5 seconds
        cutoff = now - 5.0
        recent = [t for t in self.det_timestamps if t > cutoff]
        det_hz = len(recent) / 5.0 if recent else 0.0

        self.stats_writer.writerow([
            f'{now:.3f}', f'{elapsed:.2f}', f'{det_hz:.1f}',
            self.total_detections, self.total_vel_cmds
        ])

        self.get_logger().info(
            f'[{elapsed:.0f}s] det_hz={det_hz:.1f} | '
            f'detections={self.total_detections} | '
            f'vel_cmds={self.total_vel_cmds} | '
            f'images={self.image_count}')

    def check_duration(self):
        if self.elapsed() >= self.duration:
            self.get_logger().info(
                f'Experiment complete after {self.duration}s. '
                f'Total detections: {self.total_detections}, '
                f'Total vel cmds: {self.total_vel_cmds}')
            self.cleanup()
            raise SystemExit(0)

    def cleanup(self):
        self.det_file.close()
        self.vel_file.close()
        self.stats_file.close()
        self.get_logger().info(f'Data saved to {self.output_dir}')


def main():
    parser = argparse.ArgumentParser(description='Record YOLO avoidance experiment data')
    parser.add_argument('--duration', type=int, default=120,
                        help='Experiment duration in seconds (default: 120)')
    parser.add_argument('--output', type=str,
                        default=None,
                        help='Output directory for CSV files')
    args = parser.parse_args()

    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output = os.path.join(
            '/home/siton02/md0/ros2_yolo_car_ws', 'experiment_data', timestamp)

    rclpy.init()
    recorder = ExperimentRecorder(args.output, args.duration)

    executor = MultiThreadedExecutor()
    executor.add_node(recorder)

    try:
        executor.spin()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        recorder.cleanup()
        recorder.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
