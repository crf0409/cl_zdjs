"""
LSTM 交通流量预测模型模块。

本模块基于 TensorFlow/Keras 实现了 LSTM (长短期记忆网络) 模型，
用于对交通流量时间序列数据进行预测。支持多层 LSTM 网络结构，
包含数据预处理（MinMaxScaler 归一化）、模型训练、预测、评估以及
模型的保存与加载功能。

典型用法示例：

    model = TrafficLSTM(sequence_length=12, input_dim=1, hidden_units=64)
    model.build_model()
    model.train(X_train, y_train, epochs=50)
    predictions = model.predict(X_test)
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
    from tensorflow.keras import layers, callbacks, optimizers

    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False
    warnings.warn(
        "TensorFlow 未安装。请运行 `pip install tensorflow` 以使用 LSTM 模型。",
        ImportWarning,
        stacklevel=2,
    )

logger = logging.getLogger(__name__)


def _require_tf() -> None:
    """检查 TensorFlow 是否可用，不可用时抛出异常。"""
    if not _TF_AVAILABLE:
        raise RuntimeError(
            "TensorFlow 未安装，无法使用 LSTM 模型。"
            "请运行 `pip install tensorflow` 安装。"
        )


class TrafficLSTM:
    """基于 LSTM 的交通流量预测模型。

    该模型接收固定长度的交通流量时间序列窗口，预测下一时刻的交通流量值。
    内部集成了 MinMaxScaler 用于数据归一化，支持多层 LSTM 及 Dropout 正则化。

    Attributes:
        sequence_length: 输入时间序列的窗口长度（时间步数）。
        input_dim: 每个时间步的特征维度。
        hidden_units: 每层 LSTM 的隐藏单元数。
        num_layers: LSTM 层数。
        dropout: Dropout 比率，用于防止过拟合。
        learning_rate: Adam 优化器的学习率。
        model: 构建完成的 Keras 模型实例。
        scaler: MinMaxScaler 实例，用于数据归一化。
        history: 训练历史记录。
    """

    def __init__(
        self,
        sequence_length: int = 12,
        input_dim: int = 1,
        hidden_units: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        learning_rate: float = 1e-3,
    ) -> None:
        """初始化 TrafficLSTM 模型。

        Args:
            sequence_length: 输入序列的时间步长度，默认为 12。
            input_dim: 每个时间步的输入特征维度，默认为 1。
            hidden_units: LSTM 隐藏单元数量，默认为 64。
            num_layers: LSTM 网络层数，默认为 2。
            dropout: Dropout 比率 (0~1)，默认为 0.2。
            learning_rate: 优化器学习率，默认为 1e-3。
        """
        _require_tf()
        self.sequence_length = sequence_length
        self.input_dim = input_dim
        self.hidden_units = hidden_units
        self.num_layers = num_layers
        self.dropout = dropout
        self.learning_rate = learning_rate

        self.model: Optional[keras.Model] = None
        self.scaler: MinMaxScaler = MinMaxScaler(feature_range=(0, 1))
        self.history: Optional[keras.callbacks.History] = None
        self._is_scaler_fitted: bool = False

    # ------------------------------------------------------------------
    # 数据预处理
    # ------------------------------------------------------------------

    def _fit_scaler(self, data: np.ndarray) -> np.ndarray:
        """拟合归一化器并转换数据。

        Args:
            data: 原始数据，形状为 (n_samples,) 或 (n_samples, n_features)。

        Returns:
            归一化后的数据，形状同输入。
        """
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        scaled = self.scaler.fit_transform(data)
        self._is_scaler_fitted = True
        return scaled

    def _transform(self, data: np.ndarray) -> np.ndarray:
        """使用已拟合的归一化器转换数据。

        Args:
            data: 原始数据。

        Returns:
            归一化后的数据。
        """
        if not self._is_scaler_fitted:
            return self._fit_scaler(data)
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return self.scaler.transform(data)

    def _inverse_transform(self, data: np.ndarray) -> np.ndarray:
        """将归一化数据还原为原始尺度。

        Args:
            data: 归一化后的数据。

        Returns:
            还原后的数据。
        """
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        return self.scaler.inverse_transform(data)

    def create_sequences(
        self, data: np.ndarray, fit_scaler: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """将一维时间序列转换为监督学习格式的滑动窗口样本。

        Args:
            data: 原始时间序列数据，形状为 (n_samples,) 或 (n_samples, 1)。
            fit_scaler: 是否拟合归一化器。训练集应为 True，测试集应为 False。

        Returns:
            X: 输入序列，形状为 (n_windows, sequence_length, input_dim)。
            y: 目标值，形状为 (n_windows,)。
        """
        if fit_scaler:
            scaled = self._fit_scaler(data)
        else:
            scaled = self._transform(data)

        X: List[np.ndarray] = []
        y: List[float] = []
        for i in range(len(scaled) - self.sequence_length):
            X.append(scaled[i : i + self.sequence_length])
            y.append(scaled[i + self.sequence_length, 0])
        return np.array(X), np.array(y)

    # ------------------------------------------------------------------
    # 模型构建
    # ------------------------------------------------------------------

    def build_model(self) -> keras.Model:
        """构建 LSTM 模型。

        构建包含多层 LSTM 和 Dropout 的序列模型，最终通过全连接层输出预测值。

        Returns:
            构建完成的 Keras Sequential 模型。
        """
        model = keras.Sequential(name="TrafficLSTM")

        for i in range(self.num_layers):
            return_sequences = i < self.num_layers - 1
            if i == 0:
                model.add(
                    layers.LSTM(
                        units=self.hidden_units,
                        return_sequences=return_sequences,
                        input_shape=(self.sequence_length, self.input_dim),
                        name=f"lstm_{i}",
                    )
                )
            else:
                model.add(
                    layers.LSTM(
                        units=self.hidden_units,
                        return_sequences=return_sequences,
                        name=f"lstm_{i}",
                    )
                )
            model.add(layers.Dropout(self.dropout, name=f"dropout_{i}"))

        model.add(layers.Dense(32, activation="relu", name="dense_hidden"))
        model.add(layers.Dense(1, name="dense_output"))

        optimizer = optimizers.Adam(learning_rate=self.learning_rate)
        model.compile(optimizer=optimizer, loss="mse", metrics=["mae"])

        self.model = model
        logger.info("LSTM 模型构建完成，参数量: %d", model.count_params())
        return model

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
        """训练 LSTM 模型。

        Args:
            X_train: 训练集输入，形状 (n_samples, sequence_length, input_dim)。
            y_train: 训练集目标，形状 (n_samples,)。
            X_val: 验证集输入（可选）。
            y_val: 验证集目标（可选）。
            epochs: 最大训练轮数，默认 100。
            batch_size: 批次大小，默认 32。
            patience: EarlyStopping 的耐心值，默认 10。
            verbose: 日志详细程度 (0=静默, 1=进度条, 2=每轮一行)。

        Returns:
            训练历史 History 对象。

        Raises:
            RuntimeError: 模型尚未构建时抛出。
        """
        if self.model is None:
            raise RuntimeError("请先调用 build_model() 构建模型。")

        callback_list: List[callbacks.Callback] = [
            callbacks.EarlyStopping(
                monitor="val_loss" if X_val is not None else "loss",
                patience=patience,
                restore_best_weights=True,
                verbose=1,
            ),
            callbacks.ReduceLROnPlateau(
                monitor="val_loss" if X_val is not None else "loss",
                factor=0.5,
                patience=patience // 2,
                min_lr=1e-6,
                verbose=1,
            ),
        ]

        validation_data = (X_val, y_val) if X_val is not None else None

        self.history = self.model.fit(
            X_train,
            y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=validation_data,
            callbacks=callback_list,
            verbose=verbose,
        )
        logger.info("模型训练完成，共训练 %d 轮。", len(self.history.history["loss"]))
        return self.history

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------

    def predict(
        self, X: np.ndarray, inverse: bool = True
    ) -> np.ndarray:
        """使用训练好的模型进行预测。

        Args:
            X: 输入数据，形状 (n_samples, sequence_length, input_dim)。
            inverse: 是否将预测结果逆归一化还原为原始尺度，默认 True。

        Returns:
            预测结果数组，形状 (n_samples,)。

        Raises:
            RuntimeError: 模型尚未构建时抛出。
        """
        if self.model is None:
            raise RuntimeError("请先构建并训练模型。")

        predictions = self.model.predict(X, verbose=0)

        if inverse and self._is_scaler_fitted:
            predictions = self._inverse_transform(predictions).flatten()
        else:
            predictions = predictions.flatten()

        return predictions

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------

    def evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        inverse: bool = True,
    ) -> Dict[str, float]:
        """评估模型性能。

        使用 MAE、RMSE、MAPE 和 R2 四个指标评估模型。

        Args:
            X_test: 测试集输入，形状 (n_samples, sequence_length, input_dim)。
            y_test: 测试集真实值，形状 (n_samples,)。
            inverse: 是否将数据逆归一化后再计算指标，默认 True。

        Returns:
            包含 MAE、RMSE、MAPE、R2 的字典。
        """
        predictions = self.predict(X_test, inverse=False)

        if inverse and self._is_scaler_fitted:
            predictions_orig = self._inverse_transform(predictions).flatten()
            y_test_orig = self._inverse_transform(y_test).flatten()
        else:
            predictions_orig = predictions
            y_test_orig = y_test

        mae = mean_absolute_error(y_test_orig, predictions_orig)
        rmse = float(np.sqrt(mean_squared_error(y_test_orig, predictions_orig)))
        r2 = r2_score(y_test_orig, predictions_orig)

        # MAPE: 仅在真实值非零时计算
        nonzero_mask = y_test_orig != 0
        if nonzero_mask.any():
            mape = float(
                np.mean(
                    np.abs(
                        (y_test_orig[nonzero_mask] - predictions_orig[nonzero_mask])
                        / y_test_orig[nonzero_mask]
                    )
                )
                * 100
            )
        else:
            mape = float("inf")

        metrics = {"MAE": mae, "RMSE": rmse, "MAPE": mape, "R2": r2}
        logger.info("评估结果 — MAE: %.4f, RMSE: %.4f, MAPE: %.2f%%, R2: %.4f",
                     mae, rmse, mape, r2)
        return metrics

    # ------------------------------------------------------------------
    # 模型保存与加载
    # ------------------------------------------------------------------

    def save_model(self, filepath: str) -> None:
        """保存模型及归一化器到指定路径。

        Args:
            filepath: 模型保存路径（目录），例如 ``./saved_models/lstm``。
        """
        if self.model is None:
            raise RuntimeError("没有可保存的模型，请先构建并训练。")

        os.makedirs(filepath, exist_ok=True)
        model_path = os.path.join(filepath, "model.keras")
        self.model.save(model_path)

        # 保存归一化器参数
        scaler_path = os.path.join(filepath, "scaler_params.npz")
        if self._is_scaler_fitted:
            np.savez(
                scaler_path,
                data_min=self.scaler.data_min_,
                data_max=self.scaler.data_max_,
                scale=self.scaler.scale_,
                min_val=self.scaler.min_,
                data_range=self.scaler.data_range_,
            )

        logger.info("模型已保存至: %s", filepath)

    def load_model(self, filepath: str) -> None:
        """从指定路径加载模型及归一化器。

        Args:
            filepath: 模型保存路径（目录）。
        """
        model_path = os.path.join(filepath, "model.keras")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"未找到模型文件: {model_path}")

        self.model = keras.models.load_model(model_path)

        scaler_path = os.path.join(filepath, "scaler_params.npz")
        if os.path.exists(scaler_path):
            params = np.load(scaler_path)
            self.scaler = MinMaxScaler(feature_range=(0, 1))
            self.scaler.data_min_ = params["data_min"]
            self.scaler.data_max_ = params["data_max"]
            self.scaler.scale_ = params["scale"]
            self.scaler.min_ = params["min_val"]
            self.scaler.data_range_ = params["data_range"]
            self.scaler.n_features_in_ = len(params["data_min"])
            self._is_scaler_fitted = True

        logger.info("模型已从 %s 加载。", filepath)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def summary(self) -> None:
        """打印模型结构摘要。"""
        if self.model is not None:
            self.model.summary()
        else:
            print("模型尚未构建。")

    def __repr__(self) -> str:
        return (
            f"TrafficLSTM(sequence_length={self.sequence_length}, "
            f"input_dim={self.input_dim}, hidden_units={self.hidden_units}, "
            f"num_layers={self.num_layers}, dropout={self.dropout})"
        )


# ======================================================================
# 测试入口
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("=" * 60)
    print("TrafficLSTM 模型测试")
    print("=" * 60)

    # 生成模拟交通流量数据（带有周期性模式的正弦波 + 噪声）
    np.random.seed(42)
    timesteps = 1000
    t = np.arange(timesteps)
    traffic_flow = (
        200
        + 80 * np.sin(2 * np.pi * t / 24)       # 日周期
        + 30 * np.sin(2 * np.pi * t / 168)      # 周周期
        + np.random.normal(0, 10, timesteps)     # 随机噪声
    )
    traffic_flow = np.clip(traffic_flow, 0, None)

    # 初始化模型
    seq_len = 12
    model = TrafficLSTM(
        sequence_length=seq_len,
        input_dim=1,
        hidden_units=32,
        num_layers=2,
        dropout=0.1,
        learning_rate=1e-3,
    )
    print(f"\n模型配置: {model}")

    # 数据预处理：创建滑动窗口
    split_idx = int(len(traffic_flow) * 0.8)
    train_data = traffic_flow[:split_idx]
    test_data = traffic_flow[split_idx - seq_len:]  # 包含前 seq_len 个点以构造完整窗口

    X_train, y_train = model.create_sequences(train_data, fit_scaler=True)
    X_test, y_test = model.create_sequences(test_data, fit_scaler=False)

    print(f"训练集形状: X={X_train.shape}, y={y_train.shape}")
    print(f"测试集形状: X={X_test.shape}, y={y_test.shape}")

    # 构建并训练模型
    model.build_model()
    model.summary()

    print("\n开始训练...")
    history = model.train(
        X_train, y_train,
        X_val=(X_test, y_test),
        epochs=20,
        batch_size=32,
        patience=5,
        verbose=1,
    )

    # 评估
    print("\n评估结果:")
    metrics = model.evaluate(X_test, y_test, inverse=True)
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")

    # 预测
    predictions = model.predict(X_test[:5], inverse=True)
    y_actual = model._inverse_transform(y_test[:5]).flatten()
    print("\n预测 vs 真实（前5条）:")
    for i, (pred, actual) in enumerate(zip(predictions, y_actual)):
        print(f"  [{i}] 预测={pred:.2f}, 真实={actual:.2f}")

    print("\n测试完成。")
