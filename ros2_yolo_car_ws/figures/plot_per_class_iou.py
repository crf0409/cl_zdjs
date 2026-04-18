#!/usr/bin/env python3
"""Generate per-class IoU bar chart for ALOcc+YOLOv8s on nuScenes Mini."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# ---------------------------------------------------------------------------
# Font setup: use FontProperties with explicit .ttc path for CJK support
# ---------------------------------------------------------------------------
import os

_font_path = None
_ttc_candidates = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
]
for p in _ttc_candidates:
    if os.path.isfile(p):
        _font_path = p
        break

# Also check SimHei
if _font_path is None:
    for f in fm.fontManager.ttflist:
        if 'SimHei' in f.name:
            _font_path = f.fname
            break

if _font_path:
    # Register the font so rcParams can find it
    fm.fontManager.addfont(_font_path)
    _fp = fm.FontProperties(fname=_font_path)
    chosen_font = _fp.get_name()
else:
    chosen_font = 'DejaVu Sans'

plt.rcParams['font.family'] = chosen_font
plt.rcParams['font.sans-serif'] = [chosen_font]
plt.rcParams['font.size'] = 10
plt.rcParams['axes.unicode_minus'] = False  # fix minus sign rendering
print(f'Using font: {chosen_font} (from {_font_path})')

# ---------------------------------------------------------------------------
# Data definition (18 classes in nuScenes order)
# ---------------------------------------------------------------------------
class_names_cn = [
    '其他',        # others
    '护栏',        # barrier
    '自行车',      # bicycle
    '公交车',      # bus
    '汽车',        # car
    '工程车',      # construction_vehicle
    '摩托车',      # motorcycle
    '行人',        # pedestrian
    '锥桶',        # traffic_cone
    '拖车',        # trailer
    '卡车',        # truck
    '可行驶路面',  # driveable_surface
    '其他地面',    # other_flat
    '人行道',      # sidewalk
    '地形',        # terrain
    '人造物',      # manmade
    '植被',        # vegetation
    '空闲空间',    # free
]

# IoU values; None = nan (no data)
iou_values_raw = [
    0.0,    # others
    0.0,    # barrier
    None,   # bicycle (nan)
    None,   # bus (nan)
    4.36,   # car
    None,   # construction_vehicle (nan)
    None,   # motorcycle (nan)
    None,   # pedestrian (nan)
    None,   # traffic_cone (nan)
    None,   # trailer (nan)
    None,   # truck (nan)
    100.0,  # driveable_surface
    None,   # other_flat (nan)
    None,   # sidewalk (nan)
    0.0,    # terrain
    41.96,  # manmade
    24.78,  # vegetation
    89.76,  # free
]

n = len(class_names_cn)
iou_values = np.array([v if v is not None else 0.0 for v in iou_values_raw])
is_nan = np.array([v is None for v in iou_values_raw])

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
miou = 24.44
occupied_iou = 66.67

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 6))

x = np.arange(n)
bar_width = 0.7

# Colors
color_valid = '#4A90D9'   # blue for valid classes
color_nan   = '#B0B0B0'   # gray for nan classes

colors = [color_nan if is_nan[i] else color_valid for i in range(n)]

bars = ax.bar(x, iou_values, width=bar_width, color=colors, edgecolor='black',
              linewidth=0.6, zorder=3)

# Add hatching to nan bars
for i, bar in enumerate(bars):
    if is_nan[i]:
        bar.set_hatch('///')

# Horizontal mIoU line
ax.axhline(y=miou, color='red', linestyle='--', linewidth=1.5, zorder=4,
           label=f'mIoU = {miou}%')

# Value labels on bars
for i, (val, raw) in enumerate(zip(iou_values, iou_values_raw)):
    if raw is not None and val > 0:
        ax.text(i, val + 1.5, f'{val:.1f}', ha='center', va='bottom',
                fontsize=8, fontweight='bold', color='#333333')

# Text annotation box
textstr = f'mIoU = {miou}%\noccupied IoU = {occupied_iou}%'
props = dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.85,
             edgecolor='gray')
ax.text(0.98, 0.95, textstr, transform=ax.transAxes, fontsize=11,
        verticalalignment='top', horizontalalignment='right', bbox=props,
        fontweight='bold')

# Axes & labels
ax.set_xticks(x)
ax.set_xticklabels(class_names_cn, rotation=45, ha='right', fontsize=10)
ax.set_ylabel('IoU (%)', fontsize=12)
ax.set_title('ALOcc+YOLOv8s 逐类IoU评估结果 (nuScenes Mini)', fontsize=14,
             fontweight='bold', pad=12)
ax.set_ylim(0, 115)
ax.set_xlim(-0.6, n - 0.4)

# Legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor=color_valid, edgecolor='black', label='有效IoU'),
    Patch(facecolor=color_nan, edgecolor='black', hatch='///', label='无数据 (nan)'),
    plt.Line2D([0], [0], color='red', linestyle='--', linewidth=1.5,
               label=f'mIoU = {miou}%'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10,
          framealpha=0.9)

# Grid
ax.yaxis.grid(True, linestyle=':', alpha=0.5, zorder=0)
ax.set_axisbelow(True)

plt.tight_layout()

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out_path = '/home/siton02/md0/crf/ros2_yolo_car_ws/figures/per_class_iou.png'
fig.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f'Saved: {out_path}')
