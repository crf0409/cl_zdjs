"""
模型评估指标工具
"""
import numpy as np


def calculate_mae(actual, predicted):
    """计算平均绝对误差 MAE"""
    actual, predicted = np.array(actual), np.array(predicted)
    return float(np.mean(np.abs(actual - predicted)))


def calculate_rmse(actual, predicted):
    """计算均方根误差 RMSE"""
    actual, predicted = np.array(actual), np.array(predicted)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def calculate_mape(actual, predicted):
    """计算平均绝对百分比误差 MAPE"""
    actual, predicted = np.array(actual, dtype=float), np.array(predicted, dtype=float)
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def calculate_r2(actual, predicted):
    """计算R²决定系数"""
    actual, predicted = np.array(actual), np.array(predicted)
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    if ss_tot == 0:
        return 1.0
    return float(1 - ss_res / ss_tot)


def evaluate_model(actual, predicted):
    """综合评估模型性能"""
    return {
        'mae': round(calculate_mae(actual, predicted), 4),
        'rmse': round(calculate_rmse(actual, predicted), 4),
        'mape': round(calculate_mape(actual, predicted), 2),
        'r2': round(calculate_r2(actual, predicted), 4),
    }
