"""
CNN 及 CNN-LSTM 混合交通特征提取与预测模型模块。

本模块基于 TensorFlow/Keras 实现了以下两个模型类：

1. **TrafficCNN** — 一维卷积网络 (1D-CNN)，用于从交通流量时间序列中提取
   时空特征，并可独立完成流量预测任务。
2. **HybridLSTMCNN** — CNN 与 LSTM 的混合模型，先利用 CNN 提取局部时序
   特征，再送入 LSTM 进行长期依赖建模，实现更精准的交通流量预测。

典型用法示例：

    cnn = TrafficCNN(sequence_length=24, n_features=1)
    cnn.build_model()
    cnn.train(X_train, y_train, epochs=50)

    hybrid = HybridLSTMCNN(sequence_length=24, n_features=1)
    hybrid.build_model()
    hybrid.train(X_train, y_train, epochs=50)
"""

from __future__ import annotations

import logging
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, callbacks, optimizers, Model

    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False
    warnings.warn(
        "TensorFlow 未安装。请运行 `pip install tensorflow` 以使用 CNN/Hybrid 模型。",
        ImportWarning,
        stacklevel=2,
    )

logger = logging.getLogger(__name__)


def _require_tf() -> None:
    """检查 TensorFlow 是否可用，不可用时抛出异常。"""
    if not _TF_AVAILABLE:
        raise RuntimeError(
            "TensorFlow 未安装，无法使用 CNN 模型。"
            "请运行 `pip install tensorflow` 安装。"
        )


# ======================================================================
# 公用工具
# ======================================================================

class _BaseTrafficModel:
    """交通预测模型的公共基类，封装归一化与评估逻辑。"""

    def __init__(self) -> None:
        self.model: Optional[keras.Model] = None
        self.scaler: MinMaxScaler = MinMaxScaler(feature_range=(0, 1))
        self.history: Optional[keras.callbacks.History] = None
        self._is_scaler_fitted: bool = False

    # ---------- 归一化 ----------

    def fit_scaler(self, data: np.ndarray) -> np.ndarray:
        """拟合归一化器并转换数据。

        Args:
            data: 形状为 (n_samples,) 或 (n_samples, n_features) 的原始数据。

        Returns:
            归一化后的数据。
        """
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        scaled = self.scaler.fit_transform(data)
        self._is_scaler_fitted = True
        return scaled

    def transform(self, data: np.ndarray) -> np.ndarray:
        """使用已拟合的归一化器转换数据。"""
        if not self._is_scaler_fitted:
            return self.fit_scaler(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return self.scaler.transform(data)

    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        """将归一化数据还原为原始尺度。"""
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return self.scaler.inverse_transform(data)

    # ---------- 序列创建 ----------

    def create_sequences(
        self,
        data: np.ndarray,
        sequence_length: int,
        fit_scaler: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """将一维时间序列转换为滑动窗口样本。

        Args:
            data: 原始时间序列。
            sequence_length: 滑动窗口长度。
            fit_scaler: 是否拟合归一化器。

        Returns:
            (X, y) 元组。
        """
        scaled = self.fit_scaler(data) if fit_scaler else self.transform(data)
        X: List[np.ndarray] = []
        y: List[float] = []
        for i in range(len(scaled) - sequence_length):
            X.append(scaled[i : i + sequence_length])
            y.append(scaled[i + sequence_length, 0])
        return np.array(X), np.array(y)

    # ---------- 评估 ----------

    def _compute_metrics(
        self, y_true: np.ndarray, y_pred: np.ndarray
    ) -> Dict[str, float]:
        """计算回归评估指标（MAE / RMSE / MAPE / R2）。"""
        mae = mean_absolute_error(y_true, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = r2_score(y_true, y_pred)

        nonzero = y_true != 0
        if nonzero.any():
            mape = float(
                np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero]))
                * 100
            )
        else:
            mape = float("inf")

        return {"MAE": mae, "RMSE": rmse, "MAPE": mape, "R2": r2}


# ======================================================================
# TrafficCNN
# ======================================================================

class TrafficCNN(_BaseTrafficModel):
    """基于一维卷积网络 (1D-CNN) 的交通流量预测模型。

    模型结构: Conv1D -> MaxPool -> Conv1D -> MaxPool -> Flatten -> Dense -> Output

    Attributes:
        sequence_length: 输入序列的时间步长度。
        n_features: 每个时间步的特征数。
        filters: 各 Conv1D 层的滤波器数量列表。
        kernel_sizes: 各 Conv1D 层的卷积核大小列表。
        pool_size: MaxPooling1D 的池化窗口大小。
        dense_units: 全连接隐藏层的单元数。
        dropout: Dropout 比率。
        learning_rate: 优化器学习率。
    """

    def __init__(
        self,
        sequence_length: int = 24,
        n_features: int = 1,
        filters: Optional[List[int]] = None,
        kernel_sizes: Optional[List[int]] = None,
        pool_size: int = 2,
        dense_units: int = 64,
        dropout: float = 0.2,
        learning_rate: float = 1e-3,
    ) -> None:
        """初始化 TrafficCNN 模型。

        Args:
            sequence_length: 输入时间窗口长度，默认 24。
            n_features: 特征维度，默认 1。
            filters: 卷积层滤波器列表，默认 [64, 128]。
            kernel_sizes: 卷积核大小列表，默认 [3, 3]。
            pool_size: 池化窗口大小，默认 2。
            dense_units: 全连接层单元数，默认 64。
            dropout: Dropout 比率，默认 0.2。
            learning_rate: 学习率，默认 1e-3。
        """
        _require_tf()
        super().__init__()
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.filters = filters or [64, 128]
        self.kernel_sizes = kernel_sizes or [3, 3]
        self.pool_size = pool_size
        self.dense_units = dense_units
        self.dropout = dropout
        self.learning_rate = learning_rate

        self._feature_extractor: Optional[keras.Model] = None

    # ------------------------------------------------------------------
    # 模型构建
    # ------------------------------------------------------------------

    def build_model(self) -> keras.Model:
        """构建 1D-CNN 模型。

        Returns:
            构建完成的 Keras 模型。
        """
        inputs = layers.Input(
            shape=(self.sequence_length, self.n_features), name="input"
        )
        x = inputs

        for i, (f, k) in enumerate(zip(self.filters, self.kernel_sizes)):
            x = layers.Conv1D(
                filters=f,
                kernel_size=k,
                activation="relu",
                padding="same",
                name=f"conv1d_{i}",
            )(x)
            x = layers.BatchNormalization(name=f"bn_{i}")(x)
            # 仅在序列长度足够时池化
            if x.shape[1] is not None and x.shape[1] >= self.pool_size:
                x = layers.MaxPooling1D(
                    pool_size=self.pool_size, name=f"maxpool_{i}"
                )(x)

        feature_output = layers.GlobalAveragePooling1D(name="global_avg_pool")(x)
        x = layers.Dense(self.dense_units, activation="relu", name="dense_hidden")(
            feature_output
        )
        x = layers.Dropout(self.dropout, name="dropout")(x)
        outputs = layers.Dense(1, name="dense_output")(x)

        self.model = Model(inputs=inputs, outputs=outputs, name="TrafficCNN")
        self.model.compile(
            optimizer=optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        # 构建特征提取子模型（共享权重）
        self._feature_extractor = Model(
            inputs=inputs, outputs=feature_output, name="CNN_FeatureExtractor"
        )

        logger.info(
            "CNN 模型构建完成，参数量: %d", self.model.count_params()
        )
        return self.model

    # ------------------------------------------------------------------
    # 训练
    # ------------------------------------------------------------------

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 32,
        patience: int = 10,
        verbose: int = 1,
    ) -> keras.callbacks.History:
        """训练 CNN 模型。

        Args:
            X_train: 训练输入，形状 (n, sequence_length, n_features)。
            y_train: 训练目标，形状 (n,)。
            X_val: 验证输入（可选）。
            y_val: 验证目标（可选）。
            epochs: 最大训练轮数。
            batch_size: 批次大小。
            patience: EarlyStopping 耐心值。
            verbose: 日志详细程度。

        Returns:
            训练历史 History 对象。
        """
        if self.model is None:
            raise RuntimeError("请先调用 build_model() 构建模型。")

        monitor = "val_loss" if X_val is not None else "loss"
        cb = [
            callbacks.EarlyStopping(
                monitor=monitor, patience=patience,
                restore_best_weights=True, verbose=1,
            ),
            callbacks.ReduceLROnPlateau(
                monitor=monitor, factor=0.5,
                patience=max(1, patience // 2), min_lr=1e-6, verbose=1,
            ),
        ]

        validation_data = (X_val, y_val) if X_val is not None else None
        self.history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            callbacks=cb,
            verbose=verbose,
        )
        logger.info("CNN 训练完成，共 %d 轮。", len(self.history.history["loss"]))
        return self.history

    # ------------------------------------------------------------------
    # 预测与评估
    # ------------------------------------------------------------------

    def predict(self, X: np.ndarray, inverse: bool = True) -> np.ndarray:
        """预测交通流量。

        Args:
            X: 输入数据，形状 (n, sequence_length, n_features)。
            inverse: 是否逆归一化，默认 True。

        Returns:
            预测值数组。
        """
        if self.model is None:
            raise RuntimeError("请先构建并训练模型。")
        preds = self.model.predict(X, verbose=0)
        if inverse and self._is_scaler_fitted:
            preds = self.inverse_transform(preds).flatten()
        else:
            preds = preds.flatten()
        return preds

    def evaluate(
        self, X_test: np.ndarray, y_test: np.ndarray, inverse: bool = True
    ) -> Dict[str, float]:
        """评估模型性能。

        Args:
            X_test: 测试输入。
            y_test: 测试目标。
            inverse: 是否逆归一化，默认 True。

        Returns:
            包含 MAE、RMSE、MAPE、R2 的指标字典。
        """
        preds = self.predict(X_test, inverse=False)
        if inverse and self._is_scaler_fitted:
            preds_orig = self.inverse_transform(preds).flatten()
            y_orig = self.inverse_transform(y_test).flatten()
        else:
            preds_orig = preds
            y_orig = y_test

        metrics = self._compute_metrics(y_orig, preds_orig)
        logger.info(
            "CNN 评估 — MAE: %.4f, RMSE: %.4f, MAPE: %.2f%%, R2: %.4f",
            metrics["MAE"], metrics["RMSE"], metrics["MAPE"], metrics["R2"],
        )
        return metrics

    # ------------------------------------------------------------------
    # 特征提取
    # ------------------------------------------------------------------

    def extract_features(self, X: np.ndarray) -> np.ndarray:
        """使用 CNN 提取时序特征向量。

        提取全局平均池化层之前的特征表示，可用于下游任务（如聚类、
        与 LSTM 组合等）。

        Args:
            X: 输入数据，形状 (n, sequence_length, n_features)。

        Returns:
            特征向量数组，形状 (n, feature_dim)。
        """
        if self._feature_extractor is None:
            raise RuntimeError("请先调用 build_model() 构建模型。")
        features: np.ndarray = self._feature_extractor.predict(X, verbose=0)
        logger.info("提取特征完成，形状: %s", features.shape)
        return features

    def __repr__(self) -> str:
        return (
            f"TrafficCNN(sequence_length={self.sequence_length}, "
            f"n_features={self.n_features}, filters={self.filters}, "
            f"kernel_sizes={self.kernel_sizes})"
        )


# ======================================================================
# HybridLSTMCNN
# ======================================================================

class HybridLSTMCNN(_BaseTrafficModel):
    """CNN + LSTM 混合模型，用于交通流量预测。

    模型架构:
        输入 -> Conv1D 特征提取 -> LSTM 时序建模 -> Dense 输出

    CNN 负责捕捉局部时序模式（如短期波动），LSTM 负责建模长期时序依赖。
    两者结合可兼顾细粒度特征与全局趋势。

    Attributes:
        sequence_length: 输入时间窗口长度。
        n_features: 每时间步特征数。
        cnn_filters: CNN 滤波器数量列表。
        cnn_kernel_sizes: CNN 卷积核大小列表。
        lstm_units: LSTM 隐藏单元数。
        lstm_layers: LSTM 层数。
        dense_units: 全连接隐藏层单元数。
        dropout: Dropout 比率。
        learning_rate: 优化器学习率。
    """

    def __init__(
        self,
        sequence_length: int = 24,
        n_features: int = 1,
        cnn_filters: Optional[List[int]] = None,
        cnn_kernel_sizes: Optional[List[int]] = None,
        lstm_units: int = 64,
        lstm_layers: int = 1,
        dense_units: int = 32,
        dropout: float = 0.2,
        learning_rate: float = 1e-3,
    ) -> None:
        """初始化 HybridLSTMCNN 混合模型。

        Args:
            sequence_length: 输入序列长度，默认 24。
            n_features: 特征维度，默认 1。
            cnn_filters: CNN 滤波器列表，默认 [64, 64]。
            cnn_kernel_sizes: 卷积核列表，默认 [3, 3]。
            lstm_units: LSTM 隐藏单元数，默认 64。
            lstm_layers: LSTM 层数，默认 1。
            dense_units: 全连接层单元数，默认 32。
            dropout: Dropout 比率，默认 0.2。
            learning_rate: 学习率，默认 1e-3。
        """
        _require_tf()
        super().__init__()
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.cnn_filters = cnn_filters or [64, 64]
        self.cnn_kernel_sizes = cnn_kernel_sizes or [3, 3]
        self.lstm_units = lstm_units
        self.lstm_layers = lstm_layers
        self.dense_units = dense_units
        self.dropout = dropout
        self.learning_rate = learning_rate

    # ------------------------------------------------------------------
    # 模型构建
    # ------------------------------------------------------------------

    def build_model(self) -> keras.Model:
        """构建 CNN-LSTM 混合模型。

        Returns:
            构建完成的 Keras 模型。
        """
        inputs = layers.Input(
            shape=(self.sequence_length, self.n_features), name="input"
        )
        x = inputs

        # --- CNN 特征提取阶段 ---
        for i, (f, k) in enumerate(
            zip(self.cnn_filters, self.cnn_kernel_sizes)
        ):
            x = layers.Conv1D(
                filters=f,
                kernel_size=k,
                activation="relu",
                padding="same",
                name=f"conv1d_{i}",
            )(x)
            x = layers.BatchNormalization(name=f"bn_{i}")(x)

        x = layers.Dropout(self.dropout, name="cnn_dropout")(x)

        # --- LSTM 时序建模阶段 ---
        for i in range(self.lstm_layers):
            return_seq = i < self.lstm_layers - 1
            x = layers.LSTM(
                units=self.lstm_units,
                return_sequences=return_seq,
                name=f"lstm_{i}",
            )(x)
            x = layers.Dropout(self.dropout, name=f"lstm_dropout_{i}")(x)

        # --- 全连接输出阶段 ---
        x = layers.Dense(self.dense_units, activation="relu", name="dense_hidden")(x)
        x = layers.Dropout(self.dropout, name="output_dropout")(x)
        outputs = layers.Dense(1, name="dense_output")(x)

        self.model = Model(inputs=inputs, outputs=outputs, name="HybridLSTMCNN")
        self.model.compile(
            optimizer=optimizers.Adam(learning_rate=self.learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        logger.info(
            "Hybrid CNN-LSTM 模型构建完成，参数量: %d", self.model.count_params()
        )
        return self.model

    # ------------------------------------------------------------------
    # 训练
    # ------------------------------------------------------------------

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 32,
        patience: int = 10,
        verbose: int = 1,
    ) -> keras.callbacks.History:
        """训练混合模型。

        Args:
            X_train: 训练输入。
            y_train: 训练目标。
            X_val: 验证输入（可选）。
            y_val: 验证目标（可选）。
            epochs: 最大轮数。
            batch_size: 批次大小。
            patience: EarlyStopping 耐心值。
            verbose: 日志级别。

        Returns:
            训练历史。
        """
        if self.model is None:
            raise RuntimeError("请先调用 build_model() 构建模型。")

        monitor = "val_loss" if X_val is not None else "loss"
        cb = [
            callbacks.EarlyStopping(
                monitor=monitor, patience=patience,
                restore_best_weights=True, verbose=1,
            ),
            callbacks.ReduceLROnPlateau(
                monitor=monitor, factor=0.5,
                patience=max(1, patience // 2), min_lr=1e-6, verbose=1,
            ),
        ]

        validation_data = (X_val, y_val) if X_val is not None else None
        self.history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            callbacks=cb,
            verbose=verbose,
        )
        logger.info(
            "Hybrid 训练完成，共 %d 轮。", len(self.history.history["loss"])
        )
        return self.history

    # ------------------------------------------------------------------
    # 预测与评估
    # ------------------------------------------------------------------

    def predict(self, X: np.ndarray, inverse: bool = True) -> np.ndarray:
        """预测交通流量。

        Args:
            X: 输入数据。
            inverse: 是否逆归一化。

        Returns:
            预测值数组。
        """
        if self.model is None:
            raise RuntimeError("请先构建并训练模型。")
        preds = self.model.predict(X, verbose=0)
        if inverse and self._is_scaler_fitted:
            preds = self.inverse_transform(preds).flatten()
        else:
            preds = preds.flatten()
        return preds

    def evaluate(
        self, X_test: np.ndarray, y_test: np.ndarray, inverse: bool = True
    ) -> Dict[str, float]:
        """评估模型性能。

        Args:
            X_test: 测试输入。
            y_test: 测试目标。
            inverse: 是否逆归一化。

        Returns:
            指标字典。
        """
        preds = self.predict(X_test, inverse=False)
        if inverse and self._is_scaler_fitted:
            preds_orig = self.inverse_transform(preds).flatten()
            y_orig = self.inverse_transform(y_test).flatten()
        else:
            preds_orig = preds
            y_orig = y_test

        metrics = self._compute_metrics(y_orig, preds_orig)
        logger.info(
            "Hybrid 评估 — MAE: %.4f, RMSE: %.4f, MAPE: %.2f%%, R2: %.4f",
            metrics["MAE"], metrics["RMSE"], metrics["MAPE"], metrics["R2"],
        )
        return metrics

    def __repr__(self) -> str:
        return (
            f"HybridLSTMCNN(sequence_length={self.sequence_length}, "
            f"cnn_filters={self.cnn_filters}, lstm_units={self.lstm_units}, "
            f"lstm_layers={self.lstm_layers})"
        )


# ======================================================================
# 测试入口
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("=" * 60)
    print("TrafficCNN & HybridLSTMCNN 模型测试")
    print("=" * 60)

    # 生成模拟数据
    np.random.seed(42)
    timesteps = 1000
    t = np.arange(timesteps)
    traffic_flow = (
        200
        + 80 * np.sin(2 * np.pi * t / 24)
        + 30 * np.sin(2 * np.pi * t / 168)
        + np.random.normal(0, 10, timesteps)
    )
    traffic_flow = np.clip(traffic_flow, 0, None)

    seq_len = 24

    # ------------------------------------------------------------------
    # 测试 TrafficCNN
    # ------------------------------------------------------------------
    print("\n--- TrafficCNN ---")
    cnn = TrafficCNN(
        sequence_length=seq_len, n_features=1,
        filters=[32, 64], kernel_sizes=[3, 3],
        dense_units=32, dropout=0.1,
    )
    print(f"模型配置: {cnn}")

    split = int(len(traffic_flow) * 0.8)
    X_train, y_train = cnn.create_sequences(
        traffic_flow[:split], seq_len, fit_scaler=True
    )
    X_test, y_test = cnn.create_sequences(
        traffic_flow[split - seq_len:], seq_len, fit_scaler=False
    )
    print(f"训练集: X={X_train.shape}, y={y_train.shape}")
    print(f"测试集: X={X_test.shape}, y={y_test.shape}")

    cnn.build_model()
    cnn.model.summary()

    print("\n开始训练 CNN...")
    cnn.train(X_train, y_train, X_val=(X_test, y_test), epochs=15, patience=5)

    metrics = cnn.evaluate(X_test, y_test)
    print("CNN 评估结果:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    features = cnn.extract_features(X_test[:3])
    print(f"提取特征形状: {features.shape}")

    # ------------------------------------------------------------------
    # 测试 HybridLSTMCNN
    # ------------------------------------------------------------------
    print("\n--- HybridLSTMCNN ---")
    hybrid = HybridLSTMCNN(
        sequence_length=seq_len, n_features=1,
        cnn_filters=[32, 32], cnn_kernel_sizes=[3, 3],
        lstm_units=32, lstm_layers=1,
        dense_units=16, dropout=0.1,
    )
    print(f"模型配置: {hybrid}")

    X_train_h, y_train_h = hybrid.create_sequences(
        traffic_flow[:split], seq_len, fit_scaler=True
    )
    X_test_h, y_test_h = hybrid.create_sequences(
        traffic_flow[split - seq_len:], seq_len, fit_scaler=False
    )

    hybrid.build_model()
    hybrid.model.summary()

    print("\n开始训练 Hybrid 模型...")
    hybrid.train(
        X_train_h, y_train_h,
        X_val=(X_test_h, y_test_h),
        epochs=15, patience=5,
    )

    metrics_h = hybrid.evaluate(X_test_h, y_test_h)
    print("Hybrid 评估结果:")
    for k, v in metrics_h.items():
        print(f"  {k}: {v:.4f}")

    print("\n测试完成。")
