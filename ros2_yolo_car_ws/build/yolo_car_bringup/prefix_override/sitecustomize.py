import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/siton02/md0/ros2_yolo_car_ws/install/yolo_car_bringup'
