"""
交通模式协同过滤推荐模块。

本模块实现了基于协同过滤的交通模式分析与推荐系统，可用于：
- 发现不同监测点位之间的交通流量模式相似性
- 为缺失数据的监测点位推荐（插补）交通流量
- 识别具有相似时段特征的交通模式

支持两种协同过滤策略：
1. **基于位置的协同过滤 (Location-based / User-based)**：
   以监测点位为"用户"，以时段为"物品"，找出流量模式相似的点位。
2. **基于时段的协同过滤 (Time-based / Item-based)**：
   以时段为"用户"，以点位为"物品"，找出流量模式相似的时段。

典型用法示例：

    cf = TrafficCollaborativeFilter(method='location', similarity='cosine')
    cf.fit(traffic_matrix)
    predicted_flow = cf.predict(location_id=3, time_slot=14)
    similar = cf.recommend_similar_patterns(query_id=3, top_k=5)
"""

from __future__ import annotations

import logging
import warnings
from typing import Dict, List, Literal, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def _pearson_similarity(matrix: np.ndarray) -> np.ndarray:
    """计算行向量之间的皮尔逊相关系数矩阵。

    对矩阵的每一行先进行均值中心化，再计算余弦相似度，
    等价于皮尔逊相关系数。缺失值 (NaN) 在中心化时被忽略。

    Args:
        matrix: 形状为 (n_entities, n_items) 的评分矩阵，
                可包含 NaN 表示缺失值。

    Returns:
        形状为 (n_entities, n_entities) 的相似度矩阵，值域 [-1, 1]。
    """
    # 将 NaN 替换为行均值，确保中心化后 NaN 位置为 0（不影响相似度）
    mat = matrix.copy()
    row_means = np.nanmean(mat, axis=1, keepdims=True)
    # 对于全 NaN 的行，均值设为 0
    row_means = np.where(np.isnan(row_means), 0, row_means)
    centered = np.where(np.isnan(mat), 0, mat - row_means)

    # 计算余弦相似度 (中心化后等价于皮尔逊相关)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)  # 避免除零
    normalized = centered / norms
    sim = normalized @ normalized.T
    return sim


class TrafficCollaborativeFilter:
    """交通模式协同过滤推荐器。

    使用协同过滤算法分析交通流量矩阵中不同监测点位和时段之间的
    模式相似性，并基于相似性进行流量预测和模式推荐。

    数据格式约定：
        - 交通矩阵形状为 (n_locations, n_time_slots)
        - 行代表监测点位（类比推荐系统中的"用户"）
        - 列代表时段（类比推荐系统中的"物品"）
        - 矩阵值为交通流量，NaN 表示缺失

    Attributes:
        method: 协同过滤策略，``'location'`` 表示基于位置，
                ``'time'`` 表示基于时段。
        similarity_metric: 相似度度量方式，``'cosine'`` 或 ``'pearson'``。
        k_neighbors: 预测时使用的最近邻数量。
        traffic_matrix: 拟合后的交通流量矩阵。
        similarity_matrix: 计算得到的相似度矩阵。
        entity_ids: 实体标识列表（位置 ID 或时段 ID）。
        item_ids: 物品标识列表（时段 ID 或位置 ID）。
    """

    def __init__(
        self,
        method: Literal["location", "time"] = "location",
        similarity_metric: Literal["cosine", "pearson"] = "cosine",
        k_neighbors: int = 5,
    ) -> None:
        """初始化协同过滤器。

        Args:
            method: 过滤策略。``'location'`` = 基于位置（用户）的过滤，
                    ``'time'`` = 基于时段（物品）的过滤。默认 ``'location'``。
            similarity_metric: 相似度计算方法，``'cosine'`` 或 ``'pearson'``。
                               默认 ``'cosine'``。
            k_neighbors: 预测时使用的邻居数量，默认 5。
        """
        if method not in ("location", "time"):
            raise ValueError(f"method 必须为 'location' 或 'time'，收到: {method}")
        if similarity_metric not in ("cosine", "pearson"):
            raise ValueError(
                f"similarity_metric 必须为 'cosine' 或 'pearson'，"
                f"收到: {similarity_metric}"
            )

        self.method = method
        self.similarity_metric = similarity_metric
        self.k_neighbors = k_neighbors

        self.traffic_matrix: Optional[np.ndarray] = None
        self.similarity_matrix: Optional[np.ndarray] = None
        self.entity_ids: Optional[List[Union[int, str]]] = None
        self.item_ids: Optional[List[Union[int, str]]] = None
        self._is_fitted: bool = False

    # ------------------------------------------------------------------
    # 拟合
    # ------------------------------------------------------------------

    def fit(
        self,
        traffic_matrix: Union[np.ndarray, pd.DataFrame],
    ) -> "TrafficCollaborativeFilter":
        """拟合协同过滤模型。

        计算实体之间的相似度矩阵。

        Args:
            traffic_matrix: 交通流量矩阵。
                - 若为 ``np.ndarray``，形状 (n_locations, n_time_slots)。
                - 若为 ``pd.DataFrame``，行索引为位置 ID，列索引为时段 ID。
                - 可包含 NaN 表示缺失观测。

        Returns:
            拟合后的自身实例。
        """
        if isinstance(traffic_matrix, pd.DataFrame):
            self.entity_ids = list(traffic_matrix.index)
            self.item_ids = list(traffic_matrix.columns)
            matrix = traffic_matrix.values.astype(np.float64)
        else:
            matrix = traffic_matrix.astype(np.float64)
            self.entity_ids = list(range(matrix.shape[0]))
            self.item_ids = list(range(matrix.shape[1]))

        # 基于时段的过滤需要转置矩阵
        if self.method == "time":
            matrix = matrix.T
            self.entity_ids, self.item_ids = self.item_ids, self.entity_ids

        self.traffic_matrix = matrix
        self.similarity_matrix = self._compute_similarity(matrix)
        self._is_fitted = True

        logger.info(
            "协同过滤拟合完成 — 策略: %s, 相似度: %s, "
            "实体数: %d, 物品数: %d",
            self.method, self.similarity_metric,
            matrix.shape[0], matrix.shape[1],
        )
        return self

    def _compute_similarity(self, matrix: np.ndarray) -> np.ndarray:
        """计算相似度矩阵。

        Args:
            matrix: 评分矩阵 (n_entities, n_items)。

        Returns:
            相似度矩阵 (n_entities, n_entities)。
        """
        # 将 NaN 替换为 0 用于余弦相似度计算
        if self.similarity_metric == "cosine":
            filled = np.where(np.isnan(matrix), 0, matrix)
            sim = cosine_similarity(filled)
        else:  # pearson
            sim = _pearson_similarity(matrix)

        # 对角线置零（不与自身比较）
        np.fill_diagonal(sim, 0)
        return sim

    # ------------------------------------------------------------------
    # 预测
    # ------------------------------------------------------------------

    def predict(
        self,
        entity_id: Union[int, str],
        item_id: Union[int, str],
        k: Optional[int] = None,
    ) -> float:
        """预测指定实体-物品对的交通流量。

        在 ``location`` 模式下：entity_id = 位置, item_id = 时段。
        在 ``time`` 模式下：entity_id = 时段, item_id = 位置。

        使用 k 个最相似的邻居实体的加权平均进行预测。

        Args:
            entity_id: 目标实体 ID（位置或时段）。
            item_id: 目标物品 ID（时段或位置）。
            k: 使用的邻居数量，默认使用初始化时的 ``k_neighbors``。

        Returns:
            预测的交通流量值。

        Raises:
            RuntimeError: 模型未拟合时抛出。
            ValueError: ID 不存在时抛出。
        """
        self._check_fitted()
        k = k or self.k_neighbors

        entity_idx = self._get_index(entity_id, self.entity_ids, "entity")
        item_idx = self._get_index(item_id, self.item_ids, "item")

        # 获取与目标实体的相似度
        similarities = self.similarity_matrix[entity_idx].copy()

        # 仅保留在目标物品上有观测值的邻居
        item_values = self.traffic_matrix[:, item_idx]
        valid_mask = ~np.isnan(item_values)
        similarities[~valid_mask] = 0
        similarities[entity_idx] = 0  # 排除自身

        # 选取 top-k 邻居
        if np.sum(similarities > 0) == 0:
            # 没有有效邻居，返回物品维度的全局均值
            col_mean = np.nanmean(self.traffic_matrix[:, item_idx])
            return float(col_mean) if not np.isnan(col_mean) else 0.0

        top_k_indices = np.argsort(similarities)[::-1][:k]
        top_k_sims = similarities[top_k_indices]
        top_k_values = item_values[top_k_indices]

        # 再次过滤：仅使用正相似度的邻居
        pos_mask = top_k_sims > 0
        if not pos_mask.any():
            return float(np.nanmean(item_values[valid_mask]))

        top_k_sims = top_k_sims[pos_mask]
        top_k_values = top_k_values[pos_mask]

        # 加权平均预测
        prediction = float(np.dot(top_k_sims, top_k_values) / np.sum(top_k_sims))
        return prediction

    def predict_matrix(
        self, k: Optional[int] = None
    ) -> np.ndarray:
        """预测整个流量矩阵（填补缺失值）。

        对矩阵中的每个 NaN 位置使用协同过滤进行预测，
        非 NaN 位置保留原始值。

        Args:
            k: 邻居数量。

        Returns:
            补全后的矩阵，形状同原始矩阵。
        """
        self._check_fitted()
        result = self.traffic_matrix.copy()
        nan_positions = np.argwhere(np.isnan(result))

        for entity_idx, item_idx in nan_positions:
            entity_id = self.entity_ids[entity_idx]
            item_id = self.item_ids[item_idx]
            result[entity_idx, item_idx] = self.predict(entity_id, item_id, k=k)

        logger.info("矩阵补全完成，共填补 %d 个缺失值。", len(nan_positions))
        return result

    # ------------------------------------------------------------------
    # 推荐
    # ------------------------------------------------------------------

    def recommend_similar_patterns(
        self,
        query_id: Union[int, str],
        top_k: int = 5,
    ) -> List[Tuple[Union[int, str], float]]:
        """推荐与查询实体最相似的 top_k 个实体。

        在 ``location`` 模式下返回流量模式最相似的监测点位；
        在 ``time`` 模式下返回流量模式最相似的时段。

        Args:
            query_id: 查询实体的 ID。
            top_k: 返回的最相似实体数量，默认 5。

        Returns:
            按相似度降序排列的 (entity_id, similarity_score) 元组列表。
        """
        self._check_fitted()
        query_idx = self._get_index(query_id, self.entity_ids, "entity")
        similarities = self.similarity_matrix[query_idx].copy()
        similarities[query_idx] = -np.inf  # 排除自身

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = [
            (self.entity_ids[idx], float(similarities[idx]))
            for idx in top_indices
            if similarities[idx] > -np.inf
        ]

        logger.info(
            "为 %s (ID=%s) 推荐 %d 个相似模式。",
            "位置" if self.method == "location" else "时段",
            query_id, len(results),
        )
        return results

    def get_similarity(
        self,
        id_a: Union[int, str],
        id_b: Union[int, str],
    ) -> float:
        """获取两个实体之间的相似度分数。

        Args:
            id_a: 第一个实体 ID。
            id_b: 第二个实体 ID。

        Returns:
            相似度分数。
        """
        self._check_fitted()
        idx_a = self._get_index(id_a, self.entity_ids, "entity")
        idx_b = self._get_index(id_b, self.entity_ids, "entity")
        return float(self.similarity_matrix[idx_a, idx_b])

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------

    def evaluate(
        self,
        test_matrix: Union[np.ndarray, pd.DataFrame],
        k: Optional[int] = None,
    ) -> Dict[str, float]:
        """评估协同过滤的预测精度。

        对测试矩阵中的非 NaN 值进行预测，并与真实值比较。

        Args:
            test_matrix: 测试集流量矩阵，与训练矩阵同维度。
            k: 邻居数量。

        Returns:
            包含 MAE、RMSE、R2 的指标字典。
        """
        self._check_fitted()

        if isinstance(test_matrix, pd.DataFrame):
            test_mat = test_matrix.values.astype(np.float64)
        else:
            test_mat = test_matrix.astype(np.float64)

        if self.method == "time":
            test_mat = test_mat.T

        y_true_list: List[float] = []
        y_pred_list: List[float] = []

        non_nan_positions = np.argwhere(~np.isnan(test_mat))
        for entity_idx, item_idx in non_nan_positions:
            entity_id = self.entity_ids[entity_idx]
            item_id = self.item_ids[item_idx]
            try:
                pred = self.predict(entity_id, item_id, k=k)
                y_true_list.append(test_mat[entity_idx, item_idx])
                y_pred_list.append(pred)
            except (ValueError, IndexError):
                continue

        if not y_true_list:
            logger.warning("没有可评估的有效样本。")
            return {"MAE": float("inf"), "RMSE": float("inf"), "R2": float("-inf")}

        y_true = np.array(y_true_list)
        y_pred = np.array(y_pred_list)

        mae = mean_absolute_error(y_true, y_pred)
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot != 0 else 0.0

        metrics = {"MAE": mae, "RMSE": rmse, "R2": r2}
        logger.info("协同过滤评估 — MAE: %.4f, RMSE: %.4f, R2: %.4f", mae, rmse, r2)
        return metrics

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _check_fitted(self) -> None:
        """检查模型是否已拟合。"""
        if not self._is_fitted:
            raise RuntimeError("请先调用 fit() 拟合模型。")

    @staticmethod
    def _get_index(
        target_id: Union[int, str],
        id_list: List[Union[int, str]],
        label: str,
    ) -> int:
        """获取 ID 在列表中的索引位置。

        Args:
            target_id: 目标 ID。
            id_list: ID 列表。
            label: 描述性标签（用于错误消息）。

        Returns:
            索引值。

        Raises:
            ValueError: ID 不存在时抛出。
        """
        try:
            return id_list.index(target_id)
        except ValueError:
            raise ValueError(
                f"{label} ID '{target_id}' 不在已知列表中。"
                f"可用的 ID: {id_list[:10]}{'...' if len(id_list) > 10 else ''}"
            )

    def __repr__(self) -> str:
        status = "已拟合" if self._is_fitted else "未拟合"
        return (
            f"TrafficCollaborativeFilter(method='{self.method}', "
            f"similarity='{self.similarity_metric}', "
            f"k_neighbors={self.k_neighbors}, 状态={status})"
        )


# ======================================================================
# 测试入口
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("=" * 60)
    print("TrafficCollaborativeFilter 模型测试")
    print("=" * 60)

    np.random.seed(42)

    # 模拟交通流量矩阵: 10 个监测点位 x 24 个时段
    n_locations = 10
    n_time_slots = 24
    location_ids = [f"L{i:02d}" for i in range(n_locations)]
    time_ids = [f"T{h:02d}" for h in range(n_time_slots)]

    # 基础模式：工作日交通（早晚高峰）
    base_pattern = np.array(
        [20, 15, 10, 8, 12, 30, 80, 150, 180, 160, 140, 130,
         135, 140, 135, 145, 170, 190, 160, 100, 60, 40, 30, 25],
        dtype=np.float64,
    )

    # 各点位在基础模式上添加偏移和噪声
    traffic_data = np.zeros((n_locations, n_time_slots))
    for i in range(n_locations):
        scale = 0.5 + np.random.random() * 1.5  # 流量倍率
        shift = np.random.randint(-2, 3)         # 时间偏移
        traffic_data[i] = np.roll(base_pattern * scale, shift)
        traffic_data[i] += np.random.normal(0, 5, n_time_slots)
        traffic_data[i] = np.clip(traffic_data[i], 0, None)

    df = pd.DataFrame(traffic_data, index=location_ids, columns=time_ids)

    # 随机掩盖 15% 数据作为缺失
    mask = np.random.random(df.shape) < 0.15
    df_missing = df.copy()
    df_missing.values[mask] = np.nan
    n_missing = mask.sum()

    print(f"\n交通矩阵形状: {df.shape}")
    print(f"缺失数据量: {n_missing} ({n_missing / df.size * 100:.1f}%)")

    # ------------------------------------------------------------------
    # 测试基于位置的协同过滤 (Cosine)
    # ------------------------------------------------------------------
    print("\n--- 基于位置的协同过滤 (Cosine 相似度) ---")
    cf_loc = TrafficCollaborativeFilter(
        method="location", similarity_metric="cosine", k_neighbors=3
    )
    print(f"配置: {cf_loc}")
    cf_loc.fit(df_missing)

    # 推荐相似位置
    query = "L00"
    similar = cf_loc.recommend_similar_patterns(query, top_k=5)
    print(f"\n与 {query} 最相似的位置:")
    for loc_id, score in similar:
        print(f"  {loc_id}: 相似度 = {score:.4f}")

    # 预测缺失值
    if mask[0].any():
        missing_times = np.where(mask[0])[0]
        t_idx = missing_times[0]
        t_id = time_ids[t_idx]
        pred_val = cf_loc.predict("L00", t_id)
        true_val = df.iloc[0, t_idx]
        print(f"\n预测 L00 在 {t_id} 的流量: {pred_val:.2f} (真实: {true_val:.2f})")

    # 评估
    metrics_loc = cf_loc.evaluate(df)
    print("评估结果:")
    for k, v in metrics_loc.items():
        print(f"  {k}: {v:.4f}")

    # ------------------------------------------------------------------
    # 测试基于时段的协同过滤 (Pearson)
    # ------------------------------------------------------------------
    print("\n--- 基于时段的协同过滤 (Pearson 相似度) ---")
    cf_time = TrafficCollaborativeFilter(
        method="time", similarity_metric="pearson", k_neighbors=3
    )
    print(f"配置: {cf_time}")
    cf_time.fit(df_missing)

    # 推荐相似时段
    query_time = "T08"
    similar_times = cf_time.recommend_similar_patterns(query_time, top_k=5)
    print(f"\n与 {query_time} 最相似的时段:")
    for t_id, score in similar_times:
        print(f"  {t_id}: 相似度 = {score:.4f}")

    # 评估
    metrics_time = cf_time.evaluate(df)
    print("评估结果:")
    for k, v in metrics_time.items():
        print(f"  {k}: {v:.4f}")

    # ------------------------------------------------------------------
    # 矩阵补全
    # ------------------------------------------------------------------
    print("\n--- 矩阵补全 ---")
    filled = cf_loc.predict_matrix(k=3)
    fill_mae = np.nanmean(np.abs(filled[mask] - df.values[mask]))
    print(f"缺失位置的补全 MAE: {fill_mae:.4f}")

    print("\n测试完成。")
