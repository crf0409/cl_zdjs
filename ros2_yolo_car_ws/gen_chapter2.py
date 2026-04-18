#!/usr/bin/env python3
"""
第二章 相关技术与理论基础 — 图表生成 + Word文档生成
"""
import json, os, csv, cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 200
plt.rcParams['savefig.bbox'] = 'tight'

OUT = '/home/siton02/md0/ros2_yolo_car_ws/chapter2_figures'
os.makedirs(OUT, exist_ok=True)

YOLO_RES = '/home/siton02/md0/crf/cl_zdjs/project1_yolo_obstacle/results'
SAMPLES = '/home/siton02/md0/crf/cl_zdjs/project1_yolo_obstacle/nuscenes_samples/CAM_FRONT'
with open(os.path.join(YOLO_RES, 'thesis_experiments_summary.json')) as f:
    yolo = json.load(f)

# ═══════════════════════════════════════════════════
# 图2-1  YOLO 网络结构示意图（Backbone-Neck-Head）
# ═══════════════════════════════════════════════════
def fig_yolo_arch():
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.set_xlim(0, 16); ax.set_ylim(0, 6); ax.axis('off')
    ax.set_title('YOLO 目标检测网络架构示意图', fontsize=14, fontweight='bold')

    # Backbone
    r1 = mpatches.FancyBboxPatch((0.3, 1.5), 4.2, 3, boxstyle="round,pad=0.2",
        facecolor='#BBDEFB', edgecolor='#1565C0', lw=2)
    ax.add_patch(r1)
    ax.text(2.4, 4.0, 'Backbone 骨干网络', ha='center', fontsize=12, fontweight='bold', color='#1565C0')
    ax.text(2.4, 3.2, 'CSPDarknet / C2f', ha='center', fontsize=10, color='#333')
    ax.text(2.4, 2.6, '多尺度特征提取', ha='center', fontsize=9, color='#666')
    ax.text(2.4, 2.0, 'P3(80x80) P4(40x40) P5(20x20)', ha='center', fontsize=8, color='#888')

    # Neck
    r2 = mpatches.FancyBboxPatch((5.5, 1.5), 4.2, 3, boxstyle="round,pad=0.2",
        facecolor='#FFF3E0', edgecolor='#E65100', lw=2)
    ax.add_patch(r2)
    ax.text(7.6, 4.0, 'Neck 特征融合', ha='center', fontsize=12, fontweight='bold', color='#E65100')
    ax.text(7.6, 3.2, 'FPN + PAN', ha='center', fontsize=10, color='#333')
    ax.text(7.6, 2.6, '自顶向下 + 自底向上', ha='center', fontsize=9, color='#666')
    ax.text(7.6, 2.0, '多尺度特征双向融合', ha='center', fontsize=8, color='#888')

    # Head
    r3 = mpatches.FancyBboxPatch((10.7, 1.5), 4.8, 3, boxstyle="round,pad=0.2",
        facecolor='#E8F5E9', edgecolor='#2E7D32', lw=2)
    ax.add_patch(r3)
    ax.text(13.1, 4.0, 'Head 检测头', ha='center', fontsize=12, fontweight='bold', color='#2E7D32')
    ax.text(13.1, 3.2, '解耦头 (Decoupled)', ha='center', fontsize=10, color='#333')
    ax.text(13.1, 2.5, '分类分支    回归分支', ha='center', fontsize=9, color='#666')
    ax.text(13.1, 1.9, '类别概率  边界框+置信度', ha='center', fontsize=8, color='#888')

    # 输入
    ax.text(0.15, 3.0, '输入\n640x640\nRGB', ha='center', fontsize=9, color='#333',
            bbox=dict(boxstyle='round', facecolor='#F5F5F5', edgecolor='gray'))
    ax.annotate('', xy=(0.3, 3.0), xytext=(0.0, 3.0),
                arrowprops=dict(arrowstyle='->', color='gray', lw=1.5))

    # 箭头
    ax.annotate('', xy=(5.5, 3.0), xytext=(4.5, 3.0),
                arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2))
    ax.annotate('', xy=(10.7, 3.0), xytext=(9.7, 3.0),
                arrowprops=dict(arrowstyle='->', color='#E65100', lw=2))

    # 输出
    ax.text(15.8, 3.0, '输出\nBBox\nClass\nConf', ha='center', fontsize=9, color='#333',
            bbox=dict(boxstyle='round', facecolor='#F5F5F5', edgecolor='gray'))
    ax.annotate('', xy=(15.5, 3.0), xytext=(15.1, 3.0),
                arrowprops=dict(arrowstyle='->', color='#2E7D32', lw=2))

    fig.savefig(os.path.join(OUT, 'fig_2_1_yolo_architecture.png'))
    plt.close()
    print("Saved: fig_2_1_yolo_architecture.png")

fig_yolo_arch()


# ═══════════════════════════════════════════════════
# 图2-2  YOLOv5 vs YOLO11 结构差异对比表
# ═══════════════════════════════════════════════════
def fig_v5_v11_compare():
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.axis('off')
    headers = ['特性', 'YOLOv5', 'YOLO11 (v8演进)']
    rows = [
        ['骨干网络', 'CSPDarknet + C3模块', 'CSPDarknet + C2f模块'],
        ['特征融合', 'FPN + PAN', 'FPN + PAN (改进)'],
        ['检测头', '耦合头 (Coupled)', '解耦头 (Decoupled)'],
        ['锚框方式', '基于锚框 (Anchor-based)', '无锚框 (Anchor-free)'],
        ['损失函数', 'CIoU + BCE', 'CIoU + DFL + BCE'],
        ['标签分配', 'IoU匹配', 'TaskAligned Assigner'],
        ['推理速度', '30-46 FPS (RTX3090)', '36-47 FPS (RTX3090)'],
        ['COCO mAP', '37.4 (s规模)', '44.9 (s规模)'],
    ]
    colors = [['#E3F2FD']*3 if i%2==0 else ['white']*3 for i in range(len(rows))]
    table = ax.table(cellText=rows, colLabels=headers, cellColours=colors,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)
    for j in range(3):
        table[0, j].set_facecolor('#1565C0')
        table[0, j].set_text_props(color='white', fontweight='bold')
    ax.set_title('YOLOv5 与 YOLO11 关键技术差异对比', fontsize=13, fontweight='bold', pad=20)
    fig.savefig(os.path.join(OUT, 'fig_2_2_v5_vs_v11_comparison.png'))
    plt.close()
    print("Saved: fig_2_2_v5_vs_v11_comparison.png")

fig_v5_v11_compare()


# ═══════════════════════════════════════════════════
# 图2-3  ROS 2 通信架构示意图
# ═══════════════════════════════════════════════════
def fig_ros2_arch():
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14); ax.set_ylim(0, 7); ax.axis('off')
    ax.set_title('ROS 2 节点-话题-服务通信架构', fontsize=14, fontweight='bold')

    # Node A
    rA = mpatches.FancyBboxPatch((0.5, 3.5), 3, 2.5, boxstyle="round,pad=0.2",
        facecolor='#BBDEFB', edgecolor='#1565C0', lw=2)
    ax.add_patch(rA)
    ax.text(2, 5.5, '节点 A', fontsize=12, fontweight='bold', ha='center', color='#1565C0')
    ax.text(2, 4.8, '(相机驱动)', fontsize=10, ha='center', color='#333')
    ax.text(2, 4.2, 'Publisher', fontsize=9, ha='center', color='#666')

    # Node B
    rB = mpatches.FancyBboxPatch((5.5, 3.5), 3, 2.5, boxstyle="round,pad=0.2",
        facecolor='#FFF3E0', edgecolor='#E65100', lw=2)
    ax.add_patch(rB)
    ax.text(7, 5.5, '节点 B', fontsize=12, fontweight='bold', ha='center', color='#E65100')
    ax.text(7, 4.8, '(YOLO检测)', fontsize=10, ha='center', color='#333')
    ax.text(7, 4.2, 'Sub + Pub', fontsize=9, ha='center', color='#666')

    # Node C
    rC = mpatches.FancyBboxPatch((10.5, 3.5), 3, 2.5, boxstyle="round,pad=0.2",
        facecolor='#E8F5E9', edgecolor='#2E7D32', lw=2)
    ax.add_patch(rC)
    ax.text(12, 5.5, '节点 C', fontsize=12, fontweight='bold', ha='center', color='#2E7D32')
    ax.text(12, 4.8, '(避障决策)', fontsize=10, ha='center', color='#333')
    ax.text(12, 4.2, 'Subscriber', fontsize=9, ha='center', color='#666')

    # Topic arrows
    ax.annotate('', xy=(5.5, 4.8), xytext=(3.5, 4.8),
                arrowprops=dict(arrowstyle='->', color='#1565C0', lw=2))
    ax.text(4.5, 5.3, '话题 (Topic)', fontsize=9, ha='center', color='#555', style='italic')
    ax.text(4.5, 5.0, '/camera/image_raw', fontsize=8, ha='center', color='#1565C0')

    ax.annotate('', xy=(10.5, 4.8), xytext=(8.5, 4.8),
                arrowprops=dict(arrowstyle='->', color='#E65100', lw=2))
    ax.text(9.5, 5.3, '话题 (Topic)', fontsize=9, ha='center', color='#555', style='italic')
    ax.text(9.5, 5.0, '/yolo/detections', fontsize=8, ha='center', color='#E65100')

    # DDS layer
    dds = mpatches.FancyBboxPatch((0.5, 0.5), 13, 2, boxstyle="round,pad=0.2",
        facecolor='#F3E5F5', edgecolor='#7B1FA2', lw=2, linestyle='--')
    ax.add_patch(dds)
    ax.text(7, 1.8, 'DDS 中间件层 (Data Distribution Service)', fontsize=12,
            ha='center', fontweight='bold', color='#7B1FA2')
    ax.text(7, 1.1, '发布/订阅 | QoS策略 | 自动发现 | 跨进程通信',
            fontsize=10, ha='center', color='#666')

    # DDS connections
    for x in [2, 7, 12]:
        ax.annotate('', xy=(x, 2.5), xytext=(x, 3.5),
                    arrowprops=dict(arrowstyle='<->', color='#7B1FA2', lw=1.5, linestyle='--'))

    # Service box
    srv = mpatches.FancyBboxPatch((5.5, 6.3), 3, 0.5, boxstyle="round,pad=0.1",
        facecolor='#FFECB3', edgecolor='#FF8F00', lw=1.5)
    ax.add_patch(srv)
    ax.text(7, 6.55, '服务 (Service): 请求/响应模式', fontsize=8, ha='center', color='#E65100')

    fig.savefig(os.path.join(OUT, 'fig_2_3_ros2_architecture.png'))
    plt.close()
    print("Saved: fig_2_3_ros2_architecture.png")

fig_ros2_arch()


# ═══════════════════════════════════════════════════
# 图2-4  nuScenes 数据集概览（样本展示）
# ═══════════════════════════════════════════════════
def fig_nuscenes_overview():
    import glob
    imgs = sorted(glob.glob(os.path.join(SAMPLES, '*.jpg')))
    # 选4张代表性场景
    indices = [0, 20, 40, 60]
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    titles = ['场景1: 城市桥梁', '场景2: 城市街道', '场景3: 十字路口', '场景4: 居民区']
    for idx, (ax, i) in enumerate(zip(axes.flatten(), indices)):
        if i < len(imgs):
            img = cv2.imread(imgs[i])
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ax.imshow(img_rgb)
            ax.set_title(titles[idx], fontsize=12, fontweight='bold')
        ax.axis('off')
    plt.suptitle('nuScenes mini-val 数据集典型场景示例（CAM_FRONT）',
                 fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT, 'fig_2_4_nuscenes_overview.png'))
    plt.close()
    print("Saved: fig_2_4_nuscenes_overview.png")

fig_nuscenes_overview()


# ═══════════════════════════════════════════════════
# 图2-5  nuScenes 传感器配置示意图
# ═══════════════════════════════════════════════════
def fig_nuscenes_sensors():
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(-5, 5); ax.set_ylim(-5, 5); ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('nuScenes 自动驾驶平台传感器配置', fontsize=14, fontweight='bold')

    # 车体
    car = mpatches.FancyBboxPatch((-1.2, -2), 2.4, 4, boxstyle="round,pad=0.2",
        facecolor='#E0E0E0', edgecolor='#424242', lw=2)
    ax.add_patch(car)
    ax.text(0, 0, '自动驾驶\n车辆', ha='center', fontsize=11, fontweight='bold', color='#333')

    # 6个摄像头
    cam_positions = {
        'CAM_FRONT': (0, 2.5),
        'CAM_FRONT_LEFT': (-2.5, 2),
        'CAM_FRONT_RIGHT': (2.5, 2),
        'CAM_BACK': (0, -2.8),
        'CAM_BACK_LEFT': (-2.5, -2),
        'CAM_BACK_RIGHT': (2.5, -2),
    }
    for name, (x, y) in cam_positions.items():
        circle = plt.Circle((x, y), 0.4, color='#1E88E5', alpha=0.8)
        ax.add_patch(circle)
        ax.text(x, y, 'C', ha='center', va='center', fontsize=9,
                fontweight='bold', color='white')
        short = name.replace('CAM_', '')
        ax.text(x, y-0.65, short, ha='center', fontsize=7, color='#1565C0')

    # LiDAR
    lidar = plt.Circle((0, 1.2), 0.35, color='#E53935', alpha=0.8)
    ax.add_patch(lidar)
    ax.text(0, 1.2, 'L', ha='center', va='center', fontsize=10,
            fontweight='bold', color='white')
    ax.text(0, 0.7, 'LiDAR\n32线', ha='center', fontsize=7, color='#C62828')

    # RADAR
    radar_pos = [(0, 3.2), (-3, 0.5), (3, 0.5), (-2, -2.8), (2, -2.8)]
    for x, y in radar_pos:
        r = plt.Circle((x, y), 0.25, color='#FF9800', alpha=0.7)
        ax.add_patch(r)
        ax.text(x, y, 'R', ha='center', va='center', fontsize=8,
                fontweight='bold', color='white')

    # 图例
    legend_elements = [
        mpatches.Patch(facecolor='#1E88E5', label='摄像头 x6 (1600x900)'),
        mpatches.Patch(facecolor='#E53935', label='LiDAR x1 (32线)'),
        mpatches.Patch(facecolor='#FF9800', label='毫米波雷达 x5'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=10)

    # 标注
    ax.text(0, 4.5, '1000个场景 | 140万帧 | 6个摄像头 | 1个LiDAR | 5个RADAR',
            ha='center', fontsize=10, color='#555',
            bbox=dict(boxstyle='round', facecolor='#F5F5F5', edgecolor='gray'))

    fig.savefig(os.path.join(OUT, 'fig_2_5_nuscenes_sensors.png'))
    plt.close()
    print("Saved: fig_2_5_nuscenes_sensors.png")

fig_nuscenes_sensors()


# ═══════════════════════════════════════════════════
# 图2-6  Gazebo 仿真平台架构图
# ═══════════════════════════════════════════════════
def fig_gazebo_arch():
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14); ax.set_ylim(0, 7); ax.axis('off')
    ax.set_title('Gazebo Harmonic 仿真平台与 ROS 2 集成架构', fontsize=14, fontweight='bold')

    # Gazebo
    rg = mpatches.FancyBboxPatch((0.5, 1), 5.5, 5, boxstyle="round,pad=0.3",
        facecolor='#E3F2FD', edgecolor='#1565C0', lw=2)
    ax.add_patch(rg)
    ax.text(3.25, 5.5, 'Gazebo Harmonic', fontsize=13, fontweight='bold', ha='center', color='#1565C0')

    boxes_gz = [
        ('物理引擎\n(DART/ODE)', 1.0, 3.5, '#BBDEFB'),
        ('渲染引擎\n(Ogre2)', 3.5, 3.5, '#BBDEFB'),
        ('传感器模型\n(Camera/LiDAR)', 1.0, 1.5, '#90CAF9'),
        ('世界模型\n(SDF/URDF)', 3.5, 1.5, '#90CAF9'),
    ]
    for text, x, y, c in boxes_gz:
        r = mpatches.FancyBboxPatch((x, y), 2, 1.3, boxstyle="round,pad=0.1",
            facecolor=c, edgecolor='#1565C0', lw=1)
        ax.add_patch(r)
        ax.text(x+1, y+0.65, text, ha='center', va='center', fontsize=9, color='#333')

    # Bridge
    rb = mpatches.FancyBboxPatch((6.5, 2.5), 1.5, 2, boxstyle="round,pad=0.15",
        facecolor='#FFF3E0', edgecolor='#E65100', lw=2)
    ax.add_patch(rb)
    ax.text(7.25, 3.8, 'ros_gz\nbridge', ha='center', fontsize=10, fontweight='bold', color='#E65100')
    ax.text(7.25, 2.8, 'GZ<->ROS', ha='center', fontsize=8, color='#666')

    ax.annotate('', xy=(6.5, 3.5), xytext=(6.0, 3.5),
                arrowprops=dict(arrowstyle='<->', color='#E65100', lw=2))
    ax.annotate('', xy=(8.5, 3.5), xytext=(8.0, 3.5),
                arrowprops=dict(arrowstyle='<->', color='#E65100', lw=2))

    # ROS 2
    rr = mpatches.FancyBboxPatch((8.5, 1), 5, 5, boxstyle="round,pad=0.3",
        facecolor='#E8F5E9', edgecolor='#2E7D32', lw=2)
    ax.add_patch(rr)
    ax.text(11, 5.5, 'ROS 2 Jazzy', fontsize=13, fontweight='bold', ha='center', color='#2E7D32')

    boxes_ros = [
        ('YOLO\n检测节点', 9.0, 3.5, '#C8E6C9'),
        ('避障\n决策节点', 11.5, 3.5, '#C8E6C9'),
        ('Nav2\n导航栈', 9.0, 1.5, '#A5D6A7'),
        ('RViz2\n可视化', 11.5, 1.5, '#A5D6A7'),
    ]
    for text, x, y, c in boxes_ros:
        r = mpatches.FancyBboxPatch((x, y), 2, 1.3, boxstyle="round,pad=0.1",
            facecolor=c, edgecolor='#2E7D32', lw=1)
        ax.add_patch(r)
        ax.text(x+1, y+0.65, text, ha='center', va='center', fontsize=9, color='#333')

    # TurtleBot3 标注
    ax.text(3.25, 0.5, 'TurtleBot3 waffle_pi | Camera 640x480@30Hz | LiDAR 360deg',
            ha='center', fontsize=9, color='#1565C0',
            bbox=dict(boxstyle='round', facecolor='#E3F2FD', edgecolor='#1565C0'))

    fig.savefig(os.path.join(OUT, 'fig_2_6_gazebo_ros2_arch.png'))
    plt.close()
    print("Saved: fig_2_6_gazebo_ros2_arch.png")

fig_gazebo_arch()


# ═══════════════════════════════════════════════════
# 图2-7  数据集对比表（KITTI/COCO/nuScenes）
# ═══════════════════════════════════════════════════
def fig_dataset_compare():
    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.axis('off')
    headers = ['数据集', '年份', '规模', '传感器', '类别数', '标注类型', '本课题应用']
    rows = [
        ['COCO', '2014', '33万图像', '单摄像头', '80', '实例分割/检测', 'YOLO预训练权重来源'],
        ['KITTI', '2012', '1.5万帧', '双目+LiDAR', '8', '3D检测/跟踪', '经典基准参考'],
        ['nuScenes', '2019', '140万帧', '6摄像头+LiDAR+RADAR', '23', '3D检测/跟踪/分割', '离线评估数据集'],
        ['Gazebo仿真', '2024', '可无限生成', '虚拟摄像头+LiDAR', '自定义', '自动标注', '在线避障实验'],
    ]
    colors = [['white']*7, ['white']*7, ['#E8F5E9']*7, ['#E8F5E9']*7]
    table = ax.table(cellText=rows, colLabels=headers, cellColours=colors,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)
    for j in range(7):
        table[0, j].set_facecolor('#1565C0')
        table[0, j].set_text_props(color='white', fontweight='bold')
    ax.set_title('常用目标检测数据集与仿真平台对比', fontsize=13, fontweight='bold', pad=20)
    fig.savefig(os.path.join(OUT, 'fig_2_7_dataset_comparison.png'))
    plt.close()
    print("Saved: fig_2_7_dataset_comparison.png")

fig_dataset_compare()


# ═══════════════════════════════════════════════════
# 图2-8  TensorRT 加速流程图
# ═══════════════════════════════════════════════════
def fig_tensorrt_flow():
    fig, ax = plt.subplots(figsize=(16, 4))
    ax.set_xlim(0, 16); ax.set_ylim(0, 4); ax.axis('off')
    ax.set_title('TensorRT 模型优化与部署流程', fontsize=14, fontweight='bold')

    steps = [
        ('PyTorch\n(.pt)', 0.3, '#BBDEFB', '#1565C0'),
        ('ONNX\n(.onnx)', 3.3, '#FFF3E0', '#E65100'),
        ('TensorRT\n优化', 6.3, '#FCE4EC', '#C62828'),
        ('Engine\n(.engine)', 9.3, '#E8F5E9', '#2E7D32'),
        ('推理部署\n(GPU)', 12.3, '#F3E5F5', '#7B1FA2'),
    ]
    for text, x, fc, ec in steps:
        r = mpatches.FancyBboxPatch((x, 1.0), 2.5, 2, boxstyle="round,pad=0.2",
            facecolor=fc, edgecolor=ec, lw=2)
        ax.add_patch(r)
        ax.text(x+1.25, 2.0, text, ha='center', va='center', fontsize=11,
                fontweight='bold', color=ec)

    # 箭头 + 标注
    labels = ['torch.export', 'trtexec\nFP16/INT8', '层融合\n内核调优', '实时\n推理']
    for i, label in enumerate(labels):
        x1 = steps[i][1] + 2.5
        x2 = steps[i+1][1]
        ax.annotate('', xy=(x2, 2.0), xytext=(x1, 2.0),
                    arrowprops=dict(arrowstyle='->', color='#424242', lw=2))
        ax.text((x1+x2)/2, 2.6, label, ha='center', fontsize=8, color='#666')

    # 加速比标注
    ax.text(8, 0.4, '加速效果: FP16 约2.5x | INT8 约3.5x | 精度损失 <1%',
            ha='center', fontsize=10, color='#C62828',
            bbox=dict(boxstyle='round', facecolor='#FFEBEE', edgecolor='#C62828'))

    fig.savefig(os.path.join(OUT, 'fig_2_8_tensorrt_flow.png'))
    plt.close()
    print("Saved: fig_2_8_tensorrt_flow.png")

fig_tensorrt_flow()


# ═══════════════════════════════════════════════════
# 图2-9  Jetson Nano 硬件特性对比表
# ═══════════════════════════════════════════════════
def fig_jetson_spec():
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.axis('off')
    headers = ['规格', 'Jetson Nano', 'Jetson Xavier NX', 'RTX 3090 (开发)']
    rows = [
        ['GPU', '128核 Maxwell', '384核 Volta', '10496核 Ampere'],
        ['AI 算力', '472 GFLOPS', '21 TOPS', '35.6 TFLOPS'],
        ['内存', '4GB 共享', '8GB 共享', '24GB GDDR6X'],
        ['功耗', '5-10W', '10-20W', '350W'],
        ['价格(约)', '800 元', '3500 元', '10000 元'],
        ['YOLO11s FPS', '~15 (TRT-INT8)', '~45 (TRT-FP16)', '43 (PyTorch)'],
    ]
    colors = [['white']*4 if i%2==0 else ['#F5F5F5']*4 for i in range(len(rows))]
    table = ax.table(cellText=rows, colLabels=headers, cellColours=colors,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)
    for j in range(4):
        table[0, j].set_facecolor('#1565C0')
        table[0, j].set_text_props(color='white', fontweight='bold')
    ax.set_title('嵌入式AI平台与开发平台硬件规格对比', fontsize=13, fontweight='bold', pad=20)
    fig.savefig(os.path.join(OUT, 'fig_2_9_jetson_comparison.png'))
    plt.close()
    print("Saved: fig_2_9_jetson_comparison.png")

fig_jetson_spec()


# ═══════════════════════════════════════════════════
print("\n" + "="*60)
print("第二章图表生成完成！")
print(f"输出目录: {OUT}")
for f in sorted(os.listdir(OUT)):
    print(f"  {f:50s} {os.path.getsize(os.path.join(OUT,f))/1024:.0f} KB")
