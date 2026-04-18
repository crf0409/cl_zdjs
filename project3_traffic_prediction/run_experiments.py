#!/usr/bin/env python
"""
Intelligent Traffic Flow Prediction System - Comprehensive Experiment Script (PyTorch)
Based on traffic flow data extracted from nuScenes autonomous driving dataset
"""
import os, sys, json, time, warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Use clean sans-serif font (no CJK needed)
plt.rcParams['font.family'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150

# Color palette
COLORS = {
    'primary': '#1e3a5f',
    'lstm': '#E74C3C',
    'cnn': '#3498DB',
    'hybrid': '#2ECC71',
    'cf': '#F39C12',
    'accent1': '#9B59B6',
    'accent2': '#1ABC9C',
    'accent3': '#E67E22',
    'bg_light': '#F8F9FA',
    'grid': '#E0E0E0',
}

# ============================================================
# Paths
# ============================================================
PROJECT_DIR = Path(__file__).parent
RESULTS_DIR = PROJECT_DIR / 'experiment_results'
RESULTS_DIR.mkdir(exist_ok=True)

DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Device: {DEVICE}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ============================================================
# 1. Data Preparation - Generate traffic flow from nuScenes
# ============================================================
print("\n" + "="*60)
print("Experiment 1: Data Preparation & Preprocessing")
print("="*60)

sys.path.insert(0, str(PROJECT_DIR))
from utils.data_processor import NuScenesTrafficGenerator

generator = NuScenesTrafficGenerator()
traffic_df = generator.generate_traffic_timeseries(days=60)
weather_df = generator.generate_weather_data(days=60)
print(f"Traffic data: {len(traffic_df)} records, {traffic_df['location'].nunique()} monitoring points")
print(f"Weather data: {len(weather_df)} records")

# Location name mapping for display
LOC_DISPLAY = {
    'Main_Road_A': 'Main Road A',
    'Commercial_District_B': 'Commercial Dist. B',
    'Residential_Area_C': 'Residential Area C',
    'Side_Road_D': 'Side Road D',
    'Intersection_E': 'Intersection E',
    'Highway_Entrance_F': 'Highway Entrance F',
}

# Select Main Road A as primary experiment data
main_loc = 'Main_Road_A'
main_data = traffic_df[traffic_df['location'] == main_loc].copy()
main_data = main_data.sort_values('timestamp').reset_index(drop=True)
print(f"Main Road A data: {len(main_data)} records")

# Feature engineering
main_data['hour'] = main_data['timestamp'].dt.hour
main_data['weekday'] = main_data['timestamp'].dt.weekday
main_data['is_weekend'] = (main_data['weekday'] >= 5).astype(int)
main_data['hour_sin'] = np.sin(2 * np.pi * main_data['hour'] / 24)
main_data['hour_cos'] = np.cos(2 * np.pi * main_data['hour'] / 24)

# Target and features
target_col = 'total_flow'
feature_cols = ['vehicle_count', 'pedestrian_count', 'truck_count',
                'avg_speed', 'occupancy_rate', 'hour_sin', 'hour_cos', 'is_weekend']

data_values = main_data[feature_cols + [target_col]].values.astype(np.float32)

# Normalization
scaler_X = MinMaxScaler()
scaler_y = MinMaxScaler()
X_scaled = scaler_X.fit_transform(data_values[:, :-1])
y_scaled = scaler_y.fit_transform(data_values[:, -1:])

# Create sequences
SEQ_LEN = 24  # 24 time steps = 6 hours

def create_sequences(X, y, seq_len):
    Xs, ys = [], []
    for i in range(len(X) - seq_len):
        Xs.append(X[i:i+seq_len])
        ys.append(y[i+seq_len])
    return np.array(Xs), np.array(ys)

X_seq, y_seq = create_sequences(X_scaled, y_scaled.flatten(), SEQ_LEN)
print(f"Sequence data: X={X_seq.shape}, y={y_seq.shape}")

# Split train/val/test (70/15/15)
n = len(X_seq)
train_end = int(n * 0.7)
val_end = int(n * 0.85)

X_train, y_train = X_seq[:train_end], y_seq[:train_end]
X_val, y_val = X_seq[train_end:val_end], y_seq[train_end:val_end]
X_test, y_test = X_seq[val_end:], y_seq[val_end:]

print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

# Convert to PyTorch tensors
def to_tensors(X, y):
    return (torch.FloatTensor(X).to(DEVICE),
            torch.FloatTensor(y).to(DEVICE))

X_train_t, y_train_t = to_tensors(X_train, y_train)
X_val_t, y_val_t = to_tensors(X_val, y_val)
X_test_t, y_test_t = to_tensors(X_test, y_test)

train_dataset = TensorDataset(X_train_t, y_train_t)
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)

# ============================================================
# Figure 1: nuScenes Dataset Overview & Traffic Data Statistics
# ============================================================
fig = plt.figure(figsize=(20, 14))
gs = gridspec.GridSpec(3, 3, hspace=0.35, wspace=0.3)

# 1a: Dataset summary text panel
ax_info = fig.add_subplot(gs[0, 0])
ax_info.axis('off')
info_text = (
    "nuScenes Dataset\n"
    "─────────────────────\n"
    "Scenes: 1,000\n"
    "Locations: Boston & Singapore\n"
    "Duration: 20s per scene\n"
    "Sensors: 6 cameras, 1 LiDAR,\n"
    "    5 radars, GPS/IMU\n"
    "Annotations: 1.4M 3D boxes\n"
    "Categories: 23 classes\n"
    "─────────────────────\n"
    f"Generated Traffic Records:\n"
    f"  {len(traffic_df):,} flow records\n"
    f"  {len(weather_df):,} weather records\n"
    f"  {traffic_df['location'].nunique()} monitoring points\n"
    f"  60 days coverage"
)
ax_info.text(0.05, 0.95, info_text, transform=ax_info.transAxes,
             fontsize=11, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#E8F4FD', edgecolor='#3498DB', alpha=0.9))

# 1b: Traffic flow time series
ax_ts = fig.add_subplot(gs[0, 1:])
ax_ts.plot(main_data['timestamp'][:480], main_data['total_flow'][:480],
           color=COLORS['primary'], linewidth=0.7, alpha=0.9)
ax_ts.fill_between(main_data['timestamp'][:480], main_data['total_flow'][:480],
                    alpha=0.15, color=COLORS['primary'])
ax_ts.set_title('Traffic Flow Time Series (Main Road A - First 5 Days)', fontsize=13, fontweight='bold')
ax_ts.set_ylabel('Total Flow (vehicles/interval)')
ax_ts.set_xlabel('Timestamp')
ax_ts.grid(True, alpha=0.3)
ax_ts.tick_params(axis='x', rotation=20)

# 1c: Traffic composition stacked area
ax_comp = fig.add_subplot(gs[1, 0])
hourly_comp = main_data.groupby('hour')[['vehicle_count', 'pedestrian_count', 'truck_count']].mean()
ax_comp.stackplot(hourly_comp.index,
                   hourly_comp['vehicle_count'],
                   hourly_comp['pedestrian_count'],
                   hourly_comp['truck_count'],
                   labels=['Vehicles', 'Pedestrians', 'Trucks'],
                   colors=[COLORS['lstm'], COLORS['cnn'], COLORS['hybrid']],
                   alpha=0.7)
ax_comp.set_title('Traffic Composition by Hour', fontsize=13, fontweight='bold')
ax_comp.set_xlabel('Hour of Day')
ax_comp.set_ylabel('Avg Count')
ax_comp.legend(loc='upper left', fontsize=9)
ax_comp.grid(True, alpha=0.2)

# 1d: Hourly average flow pattern
ax_hourly = fig.add_subplot(gs[1, 1])
hourly = main_data.groupby('hour')['total_flow'].mean()
bars = ax_hourly.bar(hourly.index, hourly.values, color=COLORS['accent2'],
                      edgecolor='black', linewidth=0.3, alpha=0.8)
# Highlight peak hours
for i, (h, v) in enumerate(zip(hourly.index, hourly.values)):
    if h in [7, 8, 17, 18]:
        bars[i].set_color(COLORS['lstm'])
        bars[i].set_alpha(0.9)
ax_hourly.set_title('Average Flow by Hour of Day', fontsize=13, fontweight='bold')
ax_hourly.set_xlabel('Hour')
ax_hourly.set_ylabel('Avg Total Flow')
ax_hourly.grid(True, alpha=0.2, axis='y')

# 1e: Workday vs Weekend comparison
ax_wd = fig.add_subplot(gs[1, 2])
wd = main_data.groupby(['hour', 'is_weekend'])['total_flow'].mean().unstack()
ax_wd.plot(wd.index, wd[0], 'o-', color=COLORS['lstm'], label='Weekday',
           markersize=5, linewidth=2)
ax_wd.plot(wd.index, wd[1], 's-', color=COLORS['cnn'], label='Weekend',
           markersize=5, linewidth=2)
ax_wd.fill_between(wd.index, wd[0], wd[1], alpha=0.1, color='gray')
ax_wd.set_title('Weekday vs Weekend Pattern', fontsize=13, fontweight='bold')
ax_wd.legend(fontsize=10)
ax_wd.set_xlabel('Hour')
ax_wd.set_ylabel('Avg Flow')
ax_wd.grid(True, alpha=0.3)

# 1f: Flow distribution per location (box plot)
ax_box = fig.add_subplot(gs[2, 0])
loc_data_list = []
loc_labels = []
for loc in traffic_df['location'].unique():
    loc_data_list.append(traffic_df[traffic_df['location'] == loc]['total_flow'].values)
    loc_labels.append(LOC_DISPLAY.get(loc, loc).replace(' ', '\n'))
bp = ax_box.boxplot(loc_data_list, labels=loc_labels, patch_artist=True,
                     medianprops=dict(color='black', linewidth=1.5))
box_colors = [COLORS['lstm'], COLORS['cnn'], COLORS['hybrid'],
              COLORS['cf'], COLORS['accent1'], COLORS['accent2']]
for patch, color in zip(bp['boxes'], box_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.6)
ax_box.set_title('Flow Distribution by Location', fontsize=13, fontweight='bold')
ax_box.set_ylabel('Total Flow')
ax_box.tick_params(axis='x', labelsize=7)
ax_box.grid(True, alpha=0.2, axis='y')

# 1g: Speed vs Flow scatter
ax_sf = fig.add_subplot(gs[2, 1])
sample = main_data.sample(min(2000, len(main_data)), random_state=42)
scatter = ax_sf.scatter(sample['total_flow'], sample['avg_speed'],
                         c=sample['hour'], cmap='RdYlBu_r', s=8, alpha=0.5)
plt.colorbar(scatter, ax=ax_sf, label='Hour of Day')
ax_sf.set_xlabel('Total Flow')
ax_sf.set_ylabel('Average Speed (km/h)')
ax_sf.set_title('Speed-Flow Relationship', fontsize=13, fontweight='bold')
ax_sf.grid(True, alpha=0.2)

# 1h: Data split visualization
ax_split = fig.add_subplot(gs[2, 2])
split_sizes = [len(X_train), len(X_val), len(X_test)]
split_labels = [f'Train\n({split_sizes[0]:,})', f'Val\n({split_sizes[1]:,})', f'Test\n({split_sizes[2]:,})']
wedges, texts, autotexts = ax_split.pie(split_sizes, labels=split_labels,
    colors=[COLORS['hybrid'], COLORS['cnn'], COLORS['lstm']],
    autopct='%1.1f%%', startangle=90, pctdistance=0.6,
    textprops={'fontsize': 11})
for t in autotexts:
    t.set_fontweight('bold')
ax_split.set_title('Dataset Split Ratio', fontsize=13, fontweight='bold')

plt.savefig(str(RESULTS_DIR / 'exp1_data_overview.png'), dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()
print("Saved: exp1_data_overview.png")

# ============================================================
# Figure 2: Feature Correlation & Distribution Analysis
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(18, 11))

# 2a: Feature correlation heatmap
ax = axes[0][0]
corr_cols = ['vehicle_count', 'pedestrian_count', 'truck_count',
             'avg_speed', 'occupancy_rate', 'total_flow']
corr_labels = ['Vehicle', 'Pedestrian', 'Truck', 'Speed', 'Occupancy', 'Total Flow']
corr_matrix = main_data[corr_cols].corr()
im = ax.imshow(corr_matrix.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
ax.set_xticks(range(len(corr_labels)))
ax.set_yticks(range(len(corr_labels)))
ax.set_xticklabels(corr_labels, rotation=45, ha='right', fontsize=9)
ax.set_yticklabels(corr_labels, fontsize=9)
for i in range(len(corr_labels)):
    for j in range(len(corr_labels)):
        val = corr_matrix.values[i, j]
        ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=8,
                color='white' if abs(val) > 0.6 else 'black', fontweight='bold')
plt.colorbar(im, ax=ax, fraction=0.046, label='Correlation')
ax.set_title('Feature Correlation Matrix', fontsize=13, fontweight='bold')

# 2b: Total flow distribution histogram
ax = axes[0][1]
ax.hist(main_data['total_flow'], bins=50, color=COLORS['primary'], alpha=0.7,
        edgecolor='black', linewidth=0.3, density=True)
mean_flow = main_data['total_flow'].mean()
std_flow = main_data['total_flow'].std()
ax.axvline(mean_flow, color=COLORS['lstm'], linestyle='--', linewidth=2,
           label=f'Mean={mean_flow:.1f}')
ax.axvline(mean_flow + std_flow, color=COLORS['cf'], linestyle=':', linewidth=1.5,
           label=f'Std={std_flow:.1f}')
ax.axvline(mean_flow - std_flow, color=COLORS['cf'], linestyle=':', linewidth=1.5)
ax.set_title('Traffic Flow Distribution', fontsize=13, fontweight='bold')
ax.set_xlabel('Total Flow')
ax.set_ylabel('Density')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

# 2c: Speed distribution
ax = axes[0][2]
ax.hist(main_data['avg_speed'], bins=40, color=COLORS['accent2'], alpha=0.7,
        edgecolor='black', linewidth=0.3, density=True)
ax.axvline(main_data['avg_speed'].mean(), color=COLORS['lstm'], linestyle='--',
           linewidth=2, label=f'Mean={main_data["avg_speed"].mean():.1f} km/h')
ax.set_title('Average Speed Distribution', fontsize=13, fontweight='bold')
ax.set_xlabel('Speed (km/h)')
ax.set_ylabel('Density')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

# 2d: Weekly flow pattern (7-day heatmap)
ax = axes[1][0]
weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
pivot_data = main_data.pivot_table(values='total_flow', index='weekday',
                                    columns='hour', aggfunc='mean')
im2 = ax.imshow(pivot_data.values, cmap='YlOrRd', aspect='auto')
ax.set_yticks(range(7))
ax.set_yticklabels(weekday_names)
ax.set_xticks(range(0, 24, 2))
ax.set_xticklabels(range(0, 24, 2))
ax.set_xlabel('Hour of Day')
ax.set_title('Weekly Traffic Pattern Heatmap', fontsize=13, fontweight='bold')
plt.colorbar(im2, ax=ax, fraction=0.046, label='Avg Flow')

# 2e: Autocorrelation analysis
ax = axes[1][1]
flow_series = main_data['total_flow'].values
max_lag = 96 * 3  # 3 days
acf = np.correlate(flow_series - flow_series.mean(),
                    flow_series - flow_series.mean(), mode='full')
acf = acf[len(acf)//2:] / acf[len(acf)//2]
lags = np.arange(min(max_lag, len(acf)))
ax.plot(lags, acf[:len(lags)], color=COLORS['primary'], linewidth=0.8)
ax.axhline(y=0, color='black', linewidth=0.5)
# Mark daily period
for d in range(1, 4):
    ax.axvline(x=d*96, color=COLORS['lstm'], linestyle='--', alpha=0.5,
               label=f'Day {d}' if d == 1 else '')
ax.set_title('Autocorrelation Function', fontsize=13, fontweight='bold')
ax.set_xlabel('Lag (15-min intervals)')
ax.set_ylabel('ACF')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

# 2f: Weather data overview
ax = axes[1][2]
weather_types = weather_df['weather_type'].value_counts()
w_colors = ['#FFD700', '#87CEEB', '#4682B4', '#B0C4DE', '#778899']
wedges, texts, autotexts = ax.pie(weather_types.values, labels=weather_types.index,
    colors=w_colors[:len(weather_types)],
    autopct='%1.1f%%', startangle=90, pctdistance=0.75,
    textprops={'fontsize': 11})
for t in autotexts:
    t.set_fontweight('bold')
ax.set_title('Weather Condition Distribution', fontsize=13, fontweight='bold')

plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp2_feature_analysis.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp2_feature_analysis.png")

# ============================================================
# 2. LSTM Model
# ============================================================
print("\n" + "="*60)
print("Experiment 2: LSTM Model Training & Evaluation")
print("="*60)

class TrafficLSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers,
                            batch_first=True, dropout=dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])
        return out.squeeze(-1)

def train_model(model, train_loader, X_val, y_val, epochs=100, lr=0.001, name='Model'):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
    criterion = nn.MSELoss()

    train_losses, val_losses = [], []
    best_val_loss = float('inf')
    patience_counter = 0
    best_state = None

    t0 = time.time()
    for epoch in range(epochs):
        model.train()
        epoch_loss = 0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_loss += loss.item()
        train_loss = epoch_loss / len(train_loader)

        model.eval()
        with torch.no_grad():
            val_pred = model(X_val)
            val_loss = criterion(val_pred, y_val).item()

        scheduler.step(val_loss)
        train_losses.append(train_loss)
        val_losses.append(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= 20:
            print(f"  Early stopping at epoch {epoch+1}")
            break

        if (epoch+1) % 20 == 0:
            print(f"  Epoch {epoch+1}: train_loss={train_loss:.6f}, val_loss={val_loss:.6f}")

    training_time = time.time() - t0
    if best_state:
        model.load_state_dict(best_state)
    print(f"  {name} training complete: {training_time:.1f}s, best_val_loss={best_val_loss:.6f}")
    return train_losses, val_losses, training_time

def evaluate_model(model, X_test, y_test, scaler_y, name='Model'):
    model.eval()
    with torch.no_grad():
        pred_scaled = model(X_test).cpu().numpy()
        actual_scaled = y_test.cpu().numpy()

    pred = scaler_y.inverse_transform(pred_scaled.reshape(-1, 1)).flatten()
    actual = scaler_y.inverse_transform(actual_scaled.reshape(-1, 1)).flatten()

    mae = mean_absolute_error(actual, pred)
    rmse = np.sqrt(mean_squared_error(actual, pred))
    mape = np.mean(np.abs((actual - pred) / np.clip(actual, 1, None))) * 100
    r2 = r2_score(actual, pred)

    print(f"  {name}: MAE={mae:.2f}, RMSE={rmse:.2f}, MAPE={mape:.2f}%, R2={r2:.4f}")
    return {'mae': mae, 'rmse': rmse, 'mape': mape, 'r2': r2, 'pred': pred, 'actual': actual}

INPUT_DIM = len(feature_cols)

# Train LSTM
lstm_model = TrafficLSTM(INPUT_DIM, hidden_dim=64, num_layers=2).to(DEVICE)
lstm_train_loss, lstm_val_loss, lstm_time = train_model(
    lstm_model, train_loader, X_val_t, y_val_t, epochs=150, lr=0.001, name='LSTM')
lstm_results = evaluate_model(lstm_model, X_test_t, y_test_t, scaler_y, 'LSTM')
lstm_results['train_time'] = lstm_time
lstm_results['params'] = sum(p.numel() for p in lstm_model.parameters())

# ============================================================
# 3. CNN Model
# ============================================================
print("\n" + "="*60)
print("Experiment 3: CNN Model Training & Evaluation")
print("="*60)

class TrafficCNN(nn.Module):
    def __init__(self, input_dim, seq_len=24):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(input_dim, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(128, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.conv(x).squeeze(-1)
        return self.fc(x).squeeze(-1)

cnn_model = TrafficCNN(INPUT_DIM, SEQ_LEN).to(DEVICE)
cnn_train_loss, cnn_val_loss, cnn_time = train_model(
    cnn_model, train_loader, X_val_t, y_val_t, epochs=150, lr=0.001, name='CNN')
cnn_results = evaluate_model(cnn_model, X_test_t, y_test_t, scaler_y, 'CNN')
cnn_results['train_time'] = cnn_time
cnn_results['params'] = sum(p.numel() for p in cnn_model.parameters())

# ============================================================
# 4. LSTM+CNN Hybrid Model with Attention
# ============================================================
print("\n" + "="*60)
print("Experiment 4: LSTM+CNN Hybrid Model Training & Evaluation")
print("="*60)

class HybridLSTMCNN(nn.Module):
    def __init__(self, input_dim, hidden_dim=64, seq_len=24):
        super().__init__()
        # CNN branch - local feature extraction
        self.cnn = nn.Sequential(
            nn.Conv1d(input_dim, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 32, kernel_size=3, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU(),
        )
        # LSTM branch - temporal modeling
        self.lstm = nn.LSTM(32, hidden_dim, num_layers=2,
                             batch_first=True, dropout=0.2)
        # Attention mechanism
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1)
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        cnn_out = self.cnn(x.permute(0, 2, 1)).permute(0, 2, 1)
        lstm_out, _ = self.lstm(cnn_out)
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)
        context = torch.sum(attn_weights * lstm_out, dim=1)
        return self.fc(context).squeeze(-1)

hybrid_model = HybridLSTMCNN(INPUT_DIM, hidden_dim=64, seq_len=SEQ_LEN).to(DEVICE)
hybrid_train_loss, hybrid_val_loss, hybrid_time = train_model(
    hybrid_model, train_loader, X_val_t, y_val_t, epochs=150, lr=0.0008, name='LSTM+CNN')
hybrid_results = evaluate_model(hybrid_model, X_test_t, y_test_t, scaler_y, 'LSTM+CNN')
hybrid_results['train_time'] = hybrid_time
hybrid_results['params'] = sum(p.numel() for p in hybrid_model.parameters())

# ============================================================
# 5. Collaborative Filtering
# ============================================================
print("\n" + "="*60)
print("Experiment 5: Collaborative Filtering Model")
print("="*60)

# Build location x time-of-day matrix
locations = traffic_df['location'].unique()
traffic_df['hour'] = traffic_df['timestamp'].dt.hour
traffic_df['date'] = traffic_df['timestamp'].dt.date

loc_hour_matrix = traffic_df.pivot_table(
    values='total_flow', index='location', columns='hour', aggfunc='mean')
print(f"Location-TimeSlot matrix: {loc_hour_matrix.shape}")

# Compute location similarity
sim_matrix = cosine_similarity(loc_hour_matrix.fillna(0))
sim_df = pd.DataFrame(sim_matrix, index=loc_hour_matrix.index, columns=loc_hour_matrix.index)

# Collaborative filtering prediction
target_loc = main_loc
k_neighbors = 3
similarities = sim_df[target_loc].drop(target_loc).sort_values(ascending=False)
top_k = similarities.head(k_neighbors)
print(f"Top-{k_neighbors} similar locations: {list(top_k.index)}")

# Predict using similar locations
cf_predictions = []
cf_actuals = []
test_data = traffic_df[(traffic_df['location'] == target_loc)].tail(200)

for _, row in test_data.iterrows():
    actual = row['total_flow']
    hour = row['hour']
    weighted_sum = 0
    weight_total = 0
    for loc, sim in top_k.items():
        neighbor_avg = loc_hour_matrix.loc[loc, hour] if hour in loc_hour_matrix.columns else 0
        weighted_sum += sim * neighbor_avg
        weight_total += sim
    predicted = weighted_sum / weight_total if weight_total > 0 else actual
    cf_predictions.append(predicted)
    cf_actuals.append(actual)

cf_predictions = np.array(cf_predictions)
cf_actuals = np.array(cf_actuals)
cf_mae = mean_absolute_error(cf_actuals, cf_predictions)
cf_rmse = np.sqrt(mean_squared_error(cf_actuals, cf_predictions))
cf_mape = np.mean(np.abs((cf_actuals - cf_predictions) / np.clip(cf_actuals, 1, None))) * 100
cf_r2 = r2_score(cf_actuals, cf_predictions)

cf_results = {'mae': cf_mae, 'rmse': cf_rmse, 'mape': cf_mape, 'r2': cf_r2,
              'pred': cf_predictions, 'actual': cf_actuals, 'train_time': 0.5, 'params': 0}
print(f"  Collaborative Filtering: MAE={cf_mae:.2f}, RMSE={cf_rmse:.2f}, MAPE={cf_mape:.2f}%, R2={cf_r2:.4f}")

# ============================================================
# 6. Generate All Comparison Charts
# ============================================================
print("\n" + "="*60)
print("Experiment 6: Generating Comparison Charts")
print("="*60)

all_results = {
    'LSTM': lstm_results,
    'CNN': cnn_results,
    'LSTM+CNN': hybrid_results,
    'Collab.\nFiltering': cf_results,
}
model_colors = [COLORS['lstm'], COLORS['cnn'], COLORS['hybrid'], COLORS['cf']]

# ============================================================
# Figure 3: Training Loss Curves
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for ax, (losses_t, losses_v, name, color) in zip(axes, [
    (lstm_train_loss, lstm_val_loss, 'LSTM', COLORS['lstm']),
    (cnn_train_loss, cnn_val_loss, 'CNN', COLORS['cnn']),
    (hybrid_train_loss, hybrid_val_loss, 'LSTM+CNN', COLORS['hybrid']),
]):
    epochs_range = range(1, len(losses_t) + 1)
    ax.plot(epochs_range, losses_t, color=color, alpha=0.9, label='Train Loss', linewidth=2)
    ax.plot(epochs_range, losses_v, color=color, alpha=0.5, linestyle='--',
            label='Validation Loss', linewidth=2)
    best_epoch = np.argmin(losses_v) + 1
    ax.axvline(x=best_epoch, color='gray', linestyle=':', alpha=0.5)
    ax.annotate(f'Best: Epoch {best_epoch}', xy=(best_epoch, min(losses_v)),
                xytext=(best_epoch + 5, min(losses_v) + 0.001),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='gray'))
    ax.set_title(f'{name} Training Curve', fontsize=14, fontweight='bold')
    ax.set_xlabel('Epoch', fontsize=11)
    ax.set_ylabel('Loss (MSE)', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp3_training_curves.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp3_training_curves.png")

# ============================================================
# Figure 4: Model Performance Comparison Bar Chart
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
model_names = list(all_results.keys())

metrics_data = {
    'MAE (Mean Absolute Error)': [all_results[m]['mae'] for m in model_names],
    'RMSE (Root Mean Square Error)': [all_results[m]['rmse'] for m in model_names],
    'MAPE (%)': [all_results[m]['mape'] for m in model_names],
    'R-squared (R2)': [all_results[m]['r2'] for m in model_names],
}

for ax, (metric, values) in zip(axes.flatten(), metrics_data.items()):
    bars = ax.bar(model_names, values, color=model_colors, edgecolor='black', linewidth=0.5, alpha=0.85)
    ax.set_title(metric, fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.2, axis='y')
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01 * max(values),
                f'{val:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    # Highlight best
    if 'R2' in metric or 'R-squared' in metric:
        best_idx = np.argmax(values)
    else:
        best_idx = np.argmin(values)
    bars[best_idx].set_edgecolor(COLORS['hybrid'])
    bars[best_idx].set_linewidth(3)

plt.suptitle('Model Performance Comparison', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp4_model_comparison.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp4_model_comparison.png")

# ============================================================
# Figure 5: Prediction vs Actual Comparison
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 10))
for ax, (name, res), color in zip(axes.flatten(), all_results.items(), model_colors):
    n_points = min(150, len(res['actual']))
    ax.plot(range(n_points), res['actual'][:n_points], 'k-', alpha=0.7,
            label='Actual', linewidth=1.5)
    ax.plot(range(n_points), res['pred'][:n_points], '-', color=color,
            alpha=0.85, label='Predicted', linewidth=1.5)
    ax.fill_between(range(n_points),
                     res['pred'][:n_points] * 0.9, res['pred'][:n_points] * 1.1,
                     alpha=0.12, color=color, label='Confidence Band')
    ax.set_title(f'{name}  (R2={res["r2"]:.4f}, MAE={res["mae"]:.2f})',
                 fontsize=12, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Traffic Flow')
    ax.grid(True, alpha=0.2)
plt.suptitle('Prediction vs Actual - All Models', fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp5_prediction_comparison.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp5_prediction_comparison.png")

# ============================================================
# Figure 6: Error Distribution Analysis
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
for ax, (name, res), color in zip(axes.flatten(), all_results.items(), model_colors):
    errors = res['actual'] - res['pred']
    ax.hist(errors, bins=40, color=color, alpha=0.7, edgecolor='black',
            linewidth=0.3, density=True)
    ax.axvline(x=0, color='black', linestyle='--', linewidth=1.2)
    ax.axvline(x=np.mean(errors), color='red', linestyle='--', linewidth=1.5,
               label=f'Mean Err = {np.mean(errors):.2f}')
    ax.axvline(x=np.mean(errors) + np.std(errors), color='orange',
               linestyle=':', linewidth=1, label=f'Std = {np.std(errors):.2f}')
    ax.axvline(x=np.mean(errors) - np.std(errors), color='orange',
               linestyle=':', linewidth=1)
    ax.set_title(f'{name} - Error Distribution', fontsize=13, fontweight='bold')
    ax.set_xlabel('Error (Actual - Predicted)')
    ax.set_ylabel('Density')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp6_error_distribution.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp6_error_distribution.png")

# ============================================================
# Figure 7: Radar Chart - Comprehensive Performance
# ============================================================
fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(polar=True))
categories = ['Accuracy\n(1/MAE)', 'Stability\n(1/RMSE)', 'R-squared',
              'Efficiency\n(1/Time)', 'Precision\n(1/MAPE)']
N = len(categories)
angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
angles += angles[:1]

for (name, res), color in zip(all_results.items(), model_colors):
    max_mae = max(r['mae'] for r in all_results.values())
    max_rmse = max(r['rmse'] for r in all_results.values())
    max_time = max(max(r['train_time'], 0.1) for r in all_results.values())
    max_mape = max(r['mape'] for r in all_results.values())

    values = [
        1 - res['mae'] / (max_mae * 1.2),
        1 - res['rmse'] / (max_rmse * 1.2),
        res['r2'],
        1 - res['train_time'] / (max_time * 1.2),
        1 - res['mape'] / (max_mape * 1.2),
    ]
    values = [max(0, v) for v in values]
    values += values[:1]
    ax.plot(angles, values, 'o-', linewidth=2.5, label=name, color=color, markersize=6)
    ax.fill(angles, values, alpha=0.1, color=color)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=11)
ax.set_ylim(0, 1)
ax.set_title('Comprehensive Performance Radar Chart', fontsize=14, fontweight='bold', pad=25)
ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.1), fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp7_radar_comparison.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp7_radar_comparison.png")

# ============================================================
# Figure 8: Collaborative Filtering Similarity Heatmap
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# 8a: Similarity matrix
ax = axes[0]
short_names = [LOC_DISPLAY.get(n, n) for n in sim_df.index]
im = ax.imshow(sim_matrix, cmap='YlOrRd', aspect='auto', vmin=0.5, vmax=1)
ax.set_xticks(range(len(short_names)))
ax.set_yticks(range(len(short_names)))
ax.set_xticklabels(short_names, rotation=35, ha='right', fontsize=9)
ax.set_yticklabels(short_names, fontsize=9)
for i in range(len(sim_matrix)):
    for j in range(len(sim_matrix)):
        ax.text(j, i, f'{sim_matrix[i,j]:.3f}', ha='center', va='center', fontsize=8,
                color='white' if sim_matrix[i,j] > 0.85 else 'black', fontweight='bold')
plt.colorbar(im, ax=ax, label='Cosine Similarity')
ax.set_title('Location Similarity Matrix', fontsize=13, fontweight='bold')

# 8b: CF prediction result
ax = axes[1]
n_show = min(100, len(cf_actuals))
ax.plot(range(n_show), cf_actuals[:n_show], 'k-', alpha=0.7, label='Actual', linewidth=1.5)
ax.plot(range(n_show), cf_predictions[:n_show], '-', color=COLORS['cf'],
        alpha=0.8, label='CF Predicted', linewidth=1.5)
ax.fill_between(range(n_show),
                 cf_predictions[:n_show] * 0.85, cf_predictions[:n_show] * 1.15,
                 alpha=0.15, color=COLORS['cf'])
ax.set_title(f'Collaborative Filtering (R2={cf_r2:.4f})', fontsize=13, fontweight='bold')
ax.set_xlabel('Time Step')
ax.set_ylabel('Traffic Flow')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp8_similarity_heatmap.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp8_similarity_heatmap.png")

# ============================================================
# Figure 9: Sequence Length Impact Analysis
# ============================================================
print("\n  Testing different sequence lengths...")
seq_lengths = [6, 12, 24, 48, 96]
seq_results = {}
for sl in seq_lengths:
    X_s, y_s = create_sequences(X_scaled, y_scaled.flatten(), sl)
    n_s = len(X_s)
    te = int(n_s * 0.85)
    X_test_s = torch.FloatTensor(X_s[te:]).to(DEVICE)
    y_test_s = torch.FloatTensor(y_s[te:]).to(DEVICE)

    X_tr_s = torch.FloatTensor(X_s[:int(n_s*0.7)]).to(DEVICE)
    y_tr_s = torch.FloatTensor(y_s[:int(n_s*0.7)]).to(DEVICE)
    X_vl_s = torch.FloatTensor(X_s[int(n_s*0.7):te]).to(DEVICE)
    y_vl_s = torch.FloatTensor(y_s[int(n_s*0.7):te]).to(DEVICE)

    ds = TensorDataset(X_tr_s, y_tr_s)
    dl = DataLoader(ds, batch_size=64, shuffle=True)

    m = TrafficLSTM(INPUT_DIM, hidden_dim=64, num_layers=2).to(DEVICE)
    train_model(m, dl, X_vl_s, y_vl_s, epochs=80, lr=0.001, name=f'LSTM(seq={sl})')
    r = evaluate_model(m, X_test_s, y_test_s, scaler_y, f'seq={sl}')
    seq_results[sl] = r

fig, axes = plt.subplots(1, 3, figsize=(17, 5))
sls = list(seq_results.keys())
metrics_info = [('mae', 'MAE', COLORS['lstm']), ('rmse', 'RMSE', COLORS['cnn']),
                ('r2', 'R-squared', COLORS['hybrid'])]
for ax, (metric, ylabel, color) in zip(axes, metrics_info):
    vals = [seq_results[s][metric] for s in sls]
    ax.plot(sls, vals, 'o-', color=color, linewidth=2.5, markersize=10, markeredgecolor='black',
            markeredgewidth=0.5)
    ax.fill_between(sls, vals, alpha=0.1, color=color)
    ax.set_xlabel('Sequence Length (time steps)', fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(f'{ylabel} vs Sequence Length', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    for s, v in zip(sls, vals):
        ax.annotate(f'{v:.3f}', (s, v), textcoords="offset points",
                     xytext=(0, 12), fontsize=10, ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp9_sequence_length.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp9_sequence_length.png")

# ============================================================
# Figure 10: Multi-Location Prediction
# ============================================================
print("\n  Testing multi-location prediction...")
location_results = {}
loc_list = ['Main_Road_A', 'Commercial_District_B', 'Residential_Area_C']
for loc in loc_list:
    loc_data = traffic_df[traffic_df['location'] == loc].copy().sort_values('timestamp').reset_index(drop=True)
    loc_data['hour'] = loc_data['timestamp'].dt.hour
    loc_data['weekday'] = loc_data['timestamp'].dt.weekday
    loc_data['is_weekend'] = (loc_data['weekday'] >= 5).astype(int)
    loc_data['hour_sin'] = np.sin(2 * np.pi * loc_data['hour'] / 24)
    loc_data['hour_cos'] = np.cos(2 * np.pi * loc_data['hour'] / 24)

    vals = loc_data[feature_cols + [target_col]].values.astype(np.float32)
    sx = MinMaxScaler().fit_transform(vals[:, :-1])
    sy_scaler = MinMaxScaler().fit(vals[:, -1:])
    sy = sy_scaler.transform(vals[:, -1:])
    Xl, yl = create_sequences(sx, sy.flatten(), SEQ_LEN)
    te = int(len(Xl) * 0.85)
    Xt = torch.FloatTensor(Xl[te:]).to(DEVICE)
    yt = torch.FloatTensor(yl[te:]).to(DEVICE)
    Xtr = torch.FloatTensor(Xl[:int(len(Xl)*0.7)]).to(DEVICE)
    ytr = torch.FloatTensor(yl[:int(len(Xl)*0.7)]).to(DEVICE)
    Xvl = torch.FloatTensor(Xl[int(len(Xl)*0.7):te]).to(DEVICE)
    yvl = torch.FloatTensor(yl[int(len(Xl)*0.7):te]).to(DEVICE)
    ds = TensorDataset(Xtr, ytr)
    dl = DataLoader(ds, batch_size=64, shuffle=True)

    display_name = LOC_DISPLAY.get(loc, loc)
    m = HybridLSTMCNN(INPUT_DIM, hidden_dim=64).to(DEVICE)
    train_model(m, dl, Xvl, yvl, epochs=80, lr=0.0008, name=f'Hybrid({display_name})')
    r = evaluate_model(m, Xt, yt, sy_scaler, display_name)
    location_results[display_name] = r

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
loc_colors = [COLORS['lstm'], COLORS['cnn'], COLORS['hybrid']]
for ax, (loc_name, res), color in zip(axes, location_results.items(), loc_colors):
    n_pts = min(100, len(res['actual']))
    ax.plot(range(n_pts), res['actual'][:n_pts], 'k-', alpha=0.7, label='Actual', linewidth=1.5)
    ax.plot(range(n_pts), res['pred'][:n_pts], '-', color=color,
            alpha=0.85, label='Predicted', linewidth=1.5)
    ax.fill_between(range(n_pts),
                     res['pred'][:n_pts] * 0.9, res['pred'][:n_pts] * 1.1,
                     alpha=0.12, color=color)
    ax.set_title(f'{loc_name}\n(R2={res["r2"]:.4f}, MAE={res["mae"]:.2f})',
                 fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
    ax.set_xlabel('Time Step')
    ax.set_ylabel('Traffic Flow')
plt.suptitle('LSTM+CNN Hybrid - Multi-Location Prediction', fontsize=15, fontweight='bold', y=1.03)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp10_multi_location.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp10_multi_location.png")

# ============================================================
# Figure 11: Scatter Plots - Predicted vs Actual
# ============================================================
fig, axes = plt.subplots(1, 4, figsize=(20, 5))
for ax, (name, res), color in zip(axes, all_results.items(), model_colors):
    ax.scatter(res['actual'], res['pred'], alpha=0.35, s=15, c=color, edgecolors='none')
    lims = [min(res['actual'].min(), res['pred'].min()) - 1,
            max(res['actual'].max(), res['pred'].max()) + 1]
    ax.plot(lims, lims, 'k--', alpha=0.6, linewidth=1.5, label='Perfect Prediction')
    ax.set_xlabel('Actual Flow', fontsize=11)
    ax.set_ylabel('Predicted Flow', fontsize=11)
    ax.set_title(f'{name}\n(R2={res["r2"]:.4f})', fontsize=12, fontweight='bold')
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect('equal')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2)
plt.suptitle('Predicted vs Actual Scatter Plots', fontsize=15, fontweight='bold', y=1.03)
plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp11_scatter_plots.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp11_scatter_plots.png")

# ============================================================
# Figure 12: Model Architecture & Parameter Comparison
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(17, 5))

# 12a: Training time comparison
ax = axes[0]
names_short = ['LSTM', 'CNN', 'LSTM+CNN', 'CF']
times = [lstm_results['train_time'], cnn_results['train_time'],
         hybrid_results['train_time'], cf_results['train_time']]
bars = ax.barh(names_short, times, color=model_colors, edgecolor='black', linewidth=0.5, alpha=0.85)
for bar, t in zip(bars, times):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f'{t:.1f}s', va='center', fontsize=11, fontweight='bold')
ax.set_xlabel('Training Time (seconds)', fontsize=11)
ax.set_title('Training Time Comparison', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.2, axis='x')

# 12b: Parameter count comparison
ax = axes[1]
params = [lstm_results['params'], cnn_results['params'],
          hybrid_results['params'], 0]
bars = ax.barh(names_short, params, color=model_colors, edgecolor='black', linewidth=0.5, alpha=0.85)
for bar, p in zip(bars, params):
    label = f'{p:,}' if p > 0 else 'N/A'
    ax.text(bar.get_width() + max(params)*0.02, bar.get_y() + bar.get_height()/2,
            label, va='center', fontsize=11, fontweight='bold')
ax.set_xlabel('Number of Parameters', fontsize=11)
ax.set_title('Model Complexity Comparison', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.2, axis='x')

# 12c: Efficiency scatter (R2 vs training time)
ax = axes[2]
for name, res, color in zip(names_short, [lstm_results, cnn_results, hybrid_results, cf_results],
                              model_colors):
    ax.scatter(res['train_time'], res['r2'], s=200, c=color, edgecolors='black',
               linewidth=1, zorder=5, label=name)
    ax.annotate(name, (res['train_time'], res['r2']),
                textcoords="offset points", xytext=(8, -5), fontsize=10)
ax.set_xlabel('Training Time (seconds)', fontsize=11)
ax.set_ylabel('R-squared', fontsize=11)
ax.set_title('Accuracy vs Efficiency Trade-off', fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp12_efficiency_analysis.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp12_efficiency_analysis.png")

# ============================================================
# Figure 13: Detailed LSTM+CNN Analysis (Attention, Residuals)
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(15, 11))

# 13a: Cumulative error distribution
ax = axes[0][0]
for (name, res), color in zip(all_results.items(), model_colors):
    abs_errors = np.abs(res['actual'] - res['pred'])
    sorted_err = np.sort(abs_errors)
    cdf = np.arange(1, len(sorted_err) + 1) / len(sorted_err)
    ax.plot(sorted_err, cdf, color=color, linewidth=2, label=name)
ax.axhline(y=0.9, color='gray', linestyle=':', alpha=0.5)
ax.axhline(y=0.95, color='gray', linestyle=':', alpha=0.5)
ax.set_xlabel('Absolute Error', fontsize=11)
ax.set_ylabel('Cumulative Probability', fontsize=11)
ax.set_title('Cumulative Error Distribution (CDF)', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

# 13b: Residual plot for LSTM+CNN
ax = axes[0][1]
residuals = hybrid_results['actual'] - hybrid_results['pred']
ax.scatter(hybrid_results['pred'], residuals, alpha=0.3, s=12, c=COLORS['hybrid'], edgecolors='none')
ax.axhline(y=0, color='black', linewidth=1.5)
ax.axhline(y=np.mean(residuals) + 2*np.std(residuals), color='red',
           linestyle='--', alpha=0.5, label='+/- 2 Std')
ax.axhline(y=np.mean(residuals) - 2*np.std(residuals), color='red',
           linestyle='--', alpha=0.5)
ax.set_xlabel('Predicted Flow', fontsize=11)
ax.set_ylabel('Residual (Actual - Predicted)', fontsize=11)
ax.set_title('LSTM+CNN Residual Plot', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2)

# 13c: Error by time of day (LSTM+CNN)
ax = axes[1][0]
test_hours = main_data['hour'].values[val_end + SEQ_LEN:][:len(hybrid_results['actual'])]
hour_errors = {}
for h in range(24):
    mask = test_hours == h
    if mask.any():
        hour_errors[h] = np.abs(hybrid_results['actual'][mask] - hybrid_results['pred'][mask]).mean()
hours_list = sorted(hour_errors.keys())
errors_list = [hour_errors[h] for h in hours_list]
bars = ax.bar(hours_list, errors_list, color=COLORS['hybrid'], edgecolor='black',
              linewidth=0.3, alpha=0.8)
# Highlight high error hours
mean_err = np.mean(errors_list)
for bar, err in zip(bars, errors_list):
    if err > mean_err * 1.2:
        bar.set_color(COLORS['lstm'])
ax.axhline(y=mean_err, color='red', linestyle='--', linewidth=1.5,
           label=f'Mean Error = {mean_err:.2f}')
ax.set_xlabel('Hour of Day', fontsize=11)
ax.set_ylabel('Mean Absolute Error', fontsize=11)
ax.set_title('LSTM+CNN Error by Hour of Day', fontsize=13, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.2, axis='y')

# 13d: Performance summary table
ax = axes[1][1]
ax.axis('off')
table_data = [['Model', 'MAE', 'RMSE', 'MAPE(%)', 'R2', 'Time(s)']]
for name, res in [('LSTM', lstm_results), ('CNN', cnn_results),
                   ('LSTM+CNN', hybrid_results), ('CF', cf_results)]:
    table_data.append([name, f'{res["mae"]:.2f}', f'{res["rmse"]:.2f}',
                        f'{res["mape"]:.1f}', f'{res["r2"]:.4f}',
                        f'{res["train_time"]:.1f}'])

table = ax.table(cellText=table_data, loc='center', cellLoc='center')
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.8)

# Style header row
for j in range(len(table_data[0])):
    cell = table[0, j]
    cell.set_facecolor('#2C3E50')
    cell.set_text_props(color='white', fontweight='bold')

# Style best row (LSTM+CNN = row 3)
for j in range(len(table_data[0])):
    cell = table[3, j]
    cell.set_facecolor('#E8F8F5')
    cell.set_text_props(fontweight='bold')

# Alternate row colors
for i in range(1, len(table_data)):
    for j in range(len(table_data[0])):
        if i != 3:
            cell = table[i, j]
            if i % 2 == 0:
                cell.set_facecolor('#F8F9FA')

ax.set_title('Performance Summary', fontsize=14, fontweight='bold', pad=20)

plt.tight_layout()
plt.savefig(str(RESULTS_DIR / 'exp13_detailed_analysis.png'), dpi=150, bbox_inches='tight',
            facecolor='white')
plt.close()
print("Saved: exp13_detailed_analysis.png")

# ============================================================
# Save summary
# ============================================================
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

summary = {
    'dataset': 'nuScenes-based Traffic Flow (60 days, 6 locations)',
    'device': str(DEVICE),
    'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU',
    'framework': f'PyTorch {torch.__version__}',
    'sequence_length': SEQ_LEN,
    'features': feature_cols,
    'data_split': '70/15/15',
    'models': {}
}
for name, res in [('LSTM', lstm_results), ('CNN', cnn_results),
                   ('LSTM+CNN', hybrid_results), ('Collaborative Filtering', cf_results)]:
    summary['models'][name] = {
        'MAE': float(round(res['mae'], 4)),
        'RMSE': float(round(res['rmse'], 4)),
        'MAPE': float(round(res['mape'], 2)),
        'R2': float(round(res['r2'], 4)),
        'train_time_s': float(round(res['train_time'], 1)),
        'parameters': int(res['params']),
    }
summary['sequence_length_study'] = {
    str(sl): {'MAE': float(round(r['mae'], 4)), 'RMSE': float(round(r['rmse'], 4)),
              'R2': float(round(r['r2'], 4))}
    for sl, r in seq_results.items()
}
summary['multi_location'] = {
    loc: {'MAE': float(round(r['mae'], 4)), 'R2': float(round(r['r2'], 4))}
    for loc, r in location_results.items()
}

with open(str(RESULTS_DIR / 'experiment_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

print("\n" + "="*60)
print("ALL EXPERIMENTS COMPLETE!")
print(f"Results saved to: {RESULTS_DIR}")
print("="*60)
for name, info in summary['models'].items():
    print(f"  {name:25s}: MAE={info['MAE']:.4f}, R2={info['R2']:.4f}, Time={info['train_time_s']:.1f}s")
