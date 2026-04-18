#!/usr/bin/env python3
"""
Post-experiment plotting script.

Reads CSV data from experiment recording and generates publication-quality
figures for the YOLO obstacle avoidance car thesis.

Usage:
    python3 plot_experiment.py --data experiment_data/<timestamp>/
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.family'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150


def load_csv(filepath):
    """Load CSV file and return header + rows."""
    rows = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def plot_velocity_over_time(vel_data, output_dir):
    """Plot linear and angular velocity over time."""
    if not vel_data:
        print("No velocity data to plot.")
        return

    times = [float(r['elapsed_s']) for r in vel_data]
    linear = [float(r['linear_x']) for r in vel_data]
    angular = [float(r['angular_z']) for r in vel_data]

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    axes[0].plot(times, linear, color='#2ECC71', linewidth=0.8, alpha=0.8)
    axes[0].fill_between(times, linear, alpha=0.2, color='#2ECC71')
    axes[0].set_ylabel('Linear Velocity (m/s)', fontsize=12)
    axes[0].set_title('Robot Velocity Commands Over Time', fontsize=14, fontweight='bold')
    axes[0].axhline(y=0, color='gray', linestyle='--', alpha=0.3)
    axes[0].set_ylim(-0.05, 0.3)
    axes[0].grid(True, alpha=0.2)
    axes[0].legend(['linear_x'], loc='upper right')

    axes[1].plot(times, angular, color='#E74C3C', linewidth=0.8, alpha=0.8)
    axes[1].fill_between(times, angular, alpha=0.2, color='#E74C3C')
    axes[1].set_ylabel('Angular Velocity (rad/s)', fontsize=12)
    axes[1].set_xlabel('Time (s)', fontsize=12)
    axes[1].axhline(y=0, color='gray', linestyle='--', alpha=0.3)
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(['angular_z'], loc='upper right')

    plt.tight_layout()
    path = os.path.join(output_dir, 'velocity_over_time.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def plot_detections_over_time(det_data, output_dir):
    """Plot detection count and class distribution over time."""
    if not det_data:
        print("No detection data to plot.")
        return

    times = [float(r['elapsed_s']) for r in det_data]
    counts = [int(r['num_detections']) for r in det_data]

    # Collect all class occurrences
    all_classes = {}
    for r in det_data:
        if r['det_classes']:
            for cls in r['det_classes'].split('|'):
                if cls:
                    all_classes[cls] = all_classes.get(cls, 0) + 1

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Detection count over time
    axes[0][0].plot(times, counts, color='#3498DB', linewidth=0.8, alpha=0.8)
    axes[0][0].fill_between(times, counts, alpha=0.15, color='#3498DB')
    axes[0][0].set_xlabel('Time (s)', fontsize=11)
    axes[0][0].set_ylabel('Detections per Frame', fontsize=11)
    axes[0][0].set_title('Detection Count Over Time', fontsize=13, fontweight='bold')
    axes[0][0].grid(True, alpha=0.2)

    # Rolling average detection count (window=10)
    if len(counts) > 10:
        window = 10
        rolling_avg = np.convolve(counts, np.ones(window)/window, mode='valid')
        rolling_times = times[window-1:]
        axes[0][0].plot(rolling_times, rolling_avg, color='#E74C3C',
                        linewidth=2, label=f'Rolling avg (w={window})')
        axes[0][0].legend()

    # Class distribution pie chart
    if all_classes:
        sorted_classes = sorted(all_classes.items(), key=lambda x: x[1], reverse=True)
        top_n = 8
        if len(sorted_classes) > top_n:
            top = sorted_classes[:top_n]
            other_count = sum(v for _, v in sorted_classes[top_n:])
            top.append(('other', other_count))
        else:
            top = sorted_classes

        labels = [f'{k}\n({v})' for k, v in top]
        values = [v for _, v in top]
        colors = plt.cm.Set3(np.linspace(0, 1, len(top)))

        axes[0][1].pie(values, labels=labels, colors=colors, autopct='%1.1f%%',
                       textprops={'fontsize': 9})
        axes[0][1].set_title('Detection Class Distribution', fontsize=13, fontweight='bold')

    # Confidence distribution
    all_confs = []
    for r in det_data:
        if r['det_confidences']:
            for c in r['det_confidences'].split('|'):
                if c:
                    all_confs.append(float(c))

    if all_confs:
        axes[1][0].hist(all_confs, bins=30, color='#9B59B6', edgecolor='black',
                        linewidth=0.5, alpha=0.8)
        axes[1][0].set_xlabel('Confidence', fontsize=11)
        axes[1][0].set_ylabel('Count', fontsize=11)
        axes[1][0].set_title('Detection Confidence Distribution', fontsize=13, fontweight='bold')
        axes[1][0].axvline(x=np.mean(all_confs), color='red', linestyle='--',
                          label=f'Mean: {np.mean(all_confs):.3f}')
        axes[1][0].legend()
        axes[1][0].grid(True, alpha=0.2)

    # Detection area distribution (proxy for distance)
    all_areas = []
    for r in det_data:
        if r['det_areas']:
            for a in r['det_areas'].split('|'):
                if a:
                    all_areas.append(float(a))

    if all_areas:
        axes[1][1].hist(all_areas, bins=50, color='#F39C12', edgecolor='black',
                        linewidth=0.5, alpha=0.8)
        axes[1][1].set_xlabel('Detection Box Area (px²)', fontsize=11)
        axes[1][1].set_ylabel('Count', fontsize=11)
        axes[1][1].set_title('Detection Area Distribution (Distance Proxy)',
                            fontsize=13, fontweight='bold')
        if all_areas:
            axes[1][1].set_xlim(0, np.percentile(all_areas, 95))
        axes[1][1].grid(True, alpha=0.2)

    plt.tight_layout()
    path = os.path.join(output_dir, 'detections_analysis.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def plot_avoidance_behavior(det_data, vel_data, output_dir):
    """Plot combined avoidance behavior: detections vs velocity response."""
    if not det_data or not vel_data:
        print("Insufficient data for avoidance behavior plot.")
        return

    det_times = [float(r['elapsed_s']) for r in det_data]
    det_counts = [int(r['num_detections']) for r in det_data]

    vel_times = [float(r['elapsed_s']) for r in vel_data]
    linear = [float(r['linear_x']) for r in vel_data]
    angular = [float(r['angular_z']) for r in vel_data]

    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)

    # Detections
    axes[0].bar(det_times, det_counts, width=0.3, color='#3498DB', alpha=0.7)
    axes[0].set_ylabel('Detections', fontsize=11)
    axes[0].set_title('Avoidance Behavior: Detection → Response',
                      fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.2)

    # Linear velocity
    axes[1].plot(vel_times, linear, color='#2ECC71', linewidth=1)
    axes[1].fill_between(vel_times, linear, alpha=0.2, color='#2ECC71')
    axes[1].set_ylabel('Linear (m/s)', fontsize=11)
    axes[1].axhline(y=0, color='gray', linestyle='--', alpha=0.3)
    axes[1].grid(True, alpha=0.2)

    # Angular velocity
    axes[2].plot(vel_times, angular, color='#E74C3C', linewidth=1)
    axes[2].fill_between(vel_times, angular, alpha=0.2, color='#E74C3C')
    axes[2].set_ylabel('Angular (rad/s)', fontsize=11)
    axes[2].set_xlabel('Time (s)', fontsize=12)
    axes[2].axhline(y=0, color='gray', linestyle='--', alpha=0.3)
    axes[2].grid(True, alpha=0.2)

    plt.tight_layout()
    path = os.path.join(output_dir, 'avoidance_behavior.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def plot_system_stats(stats_data, output_dir):
    """Plot system performance stats."""
    if not stats_data:
        print("No stats data to plot.")
        return

    times = [float(r['elapsed_s']) for r in stats_data]
    det_hz = [float(r['detection_hz']) for r in stats_data]
    total_det = [int(r['total_detections_so_far']) for r in stats_data]
    total_vel = [int(r['total_vel_cmds_so_far']) for r in stats_data]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Detection frequency
    axes[0].plot(times, det_hz, 'o-', color='#E74C3C', markersize=4, linewidth=1.5)
    axes[0].axhline(y=10, color='green', linestyle='--', alpha=0.5, label='Target: 10 Hz')
    axes[0].set_xlabel('Time (s)', fontsize=11)
    axes[0].set_ylabel('Detection Frequency (Hz)', fontsize=11)
    axes[0].set_title('YOLO Detection Frequency', fontsize=13, fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.2)
    if det_hz:
        avg_hz = np.mean([h for h in det_hz if h > 0])
        axes[0].axhline(y=avg_hz, color='blue', linestyle=':', alpha=0.5,
                        label=f'Avg: {avg_hz:.1f} Hz')
        axes[0].legend()

    # Cumulative detections
    axes[1].plot(times, total_det, color='#3498DB', linewidth=2)
    axes[1].set_xlabel('Time (s)', fontsize=11)
    axes[1].set_ylabel('Cumulative Detections', fontsize=11)
    axes[1].set_title('Cumulative Detection Count', fontsize=13, fontweight='bold')
    axes[1].grid(True, alpha=0.2)

    # Cumulative velocity commands
    axes[2].plot(times, total_vel, color='#2ECC71', linewidth=2)
    axes[2].set_xlabel('Time (s)', fontsize=11)
    axes[2].set_ylabel('Cumulative Velocity Commands', fontsize=11)
    axes[2].set_title('Cumulative Velocity Commands', fontsize=13, fontweight='bold')
    axes[2].grid(True, alpha=0.2)

    plt.tight_layout()
    path = os.path.join(output_dir, 'system_stats.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def plot_zone_analysis(det_data, output_dir, image_width=640):
    """Analyze which zones (left/center/right) detections fall in."""
    if not det_data:
        print("No detection data for zone analysis.")
        return

    left_boundary = image_width / 3.0
    right_boundary = 2.0 * image_width / 3.0

    zone_counts = {'Left': 0, 'Center': 0, 'Right': 0}
    zone_over_time = []  # (time, left, center, right)

    for r in det_data:
        t = float(r['elapsed_s'])
        left = center = right = 0
        if r['det_center_xs']:
            for cx_str in r['det_center_xs'].split('|'):
                if cx_str:
                    cx = float(cx_str)
                    if cx < left_boundary:
                        zone_counts['Left'] += 1
                        left += 1
                    elif cx > right_boundary:
                        zone_counts['Right'] += 1
                        right += 1
                    else:
                        zone_counts['Center'] += 1
                        center += 1
        zone_over_time.append((t, left, center, right))

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Zone distribution
    zones = list(zone_counts.keys())
    counts = [zone_counts[z] for z in zones]
    colors = ['#3498DB', '#E74C3C', '#2ECC71']
    bars = axes[0].bar(zones, counts, color=colors, edgecolor='black', linewidth=0.5)
    axes[0].set_title('Detection Zone Distribution', fontsize=13, fontweight='bold')
    axes[0].set_ylabel('Total Detections', fontsize=11)
    for bar, val in zip(bars, counts):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     str(val), ha='center', va='bottom', fontsize=12)
    axes[0].grid(True, alpha=0.2, axis='y')

    # Zone over time (stacked area)
    if zone_over_time:
        times = [z[0] for z in zone_over_time]
        lefts = [z[1] for z in zone_over_time]
        centers = [z[2] for z in zone_over_time]
        rights = [z[3] for z in zone_over_time]

        axes[1].stackplot(times, lefts, centers, rights,
                         labels=['Left', 'Center', 'Right'],
                         colors=['#3498DB', '#E74C3C', '#2ECC71'], alpha=0.7)
        axes[1].set_xlabel('Time (s)', fontsize=11)
        axes[1].set_ylabel('Detections per Frame', fontsize=11)
        axes[1].set_title('Zone Detection Over Time', fontsize=13, fontweight='bold')
        axes[1].legend(loc='upper right')
        axes[1].grid(True, alpha=0.2)

    plt.tight_layout()
    path = os.path.join(output_dir, 'zone_analysis.png')
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print(f"Saved: {path}")


def generate_summary(det_data, vel_data, stats_data, output_dir):
    """Generate text summary of experiment."""
    summary_lines = []
    summary_lines.append("=" * 60)
    summary_lines.append("YOLO Obstacle Avoidance Experiment Summary")
    summary_lines.append("=" * 60)

    if det_data:
        total_frames = len(det_data)
        total_det = sum(int(r['num_detections']) for r in det_data)
        duration = float(det_data[-1]['elapsed_s']) if det_data else 0
        avg_det_per_frame = total_det / total_frames if total_frames else 0

        all_confs = []
        for r in det_data:
            if r['det_confidences']:
                for c in r['det_confidences'].split('|'):
                    if c:
                        all_confs.append(float(c))

        summary_lines.append(f"\nDuration: {duration:.1f}s")
        summary_lines.append(f"Total detection frames: {total_frames}")
        summary_lines.append(f"Total detections: {total_det}")
        summary_lines.append(f"Avg detections/frame: {avg_det_per_frame:.2f}")
        if all_confs:
            summary_lines.append(f"Avg confidence: {np.mean(all_confs):.3f}")
            summary_lines.append(f"Min confidence: {np.min(all_confs):.3f}")
            summary_lines.append(f"Max confidence: {np.max(all_confs):.3f}")

    if vel_data:
        linears = [float(r['linear_x']) for r in vel_data]
        angulars = [float(r['angular_z']) for r in vel_data]
        stops = sum(1 for v in linears if abs(v) < 0.01)
        turns = sum(1 for a in angulars if abs(a) > 0.1)

        summary_lines.append(f"\nTotal velocity commands: {len(vel_data)}")
        summary_lines.append(f"Avg linear velocity: {np.mean(linears):.4f} m/s")
        summary_lines.append(f"Avg angular velocity: {np.mean(angulars):.4f} rad/s")
        summary_lines.append(f"Stop events (v<0.01): {stops} ({100*stops/len(vel_data):.1f}%)")
        summary_lines.append(f"Turn events (|w|>0.1): {turns} ({100*turns/len(vel_data):.1f}%)")

    if stats_data:
        det_hz_vals = [float(r['detection_hz']) for r in stats_data if float(r['detection_hz']) > 0]
        if det_hz_vals:
            summary_lines.append(f"\nAvg detection frequency: {np.mean(det_hz_vals):.1f} Hz")
            summary_lines.append(f"Min detection frequency: {np.min(det_hz_vals):.1f} Hz")
            summary_lines.append(f"Max detection frequency: {np.max(det_hz_vals):.1f} Hz")

    summary_lines.append("\n" + "=" * 60)

    summary_text = '\n'.join(summary_lines)
    print(summary_text)

    with open(os.path.join(output_dir, 'experiment_summary.txt'), 'w') as f:
        f.write(summary_text)


def main():
    parser = argparse.ArgumentParser(description='Plot experiment data')
    parser.add_argument('--data', type=str, required=True,
                        help='Path to experiment data directory')
    args = parser.parse_args()

    data_dir = args.data
    plots_dir = os.path.join(data_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    # Load data
    det_data = load_csv(os.path.join(data_dir, 'detections.csv'))
    vel_data = load_csv(os.path.join(data_dir, 'cmd_vel.csv'))
    stats_data = load_csv(os.path.join(data_dir, 'stats.csv'))

    print(f"Loaded: {len(det_data)} detection records, "
          f"{len(vel_data)} velocity records, "
          f"{len(stats_data)} stats records")

    # Generate all plots
    plot_velocity_over_time(vel_data, plots_dir)
    plot_detections_over_time(det_data, plots_dir)
    plot_avoidance_behavior(det_data, vel_data, plots_dir)
    plot_system_stats(stats_data, plots_dir)
    plot_zone_analysis(det_data, plots_dir)
    generate_summary(det_data, vel_data, stats_data, plots_dir)

    print(f"\nAll plots saved to: {plots_dir}")


if __name__ == '__main__':
    main()
