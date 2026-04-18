# -*- coding:utf-8 -*-
"""
Detector.py — 烟雾探测器模型

模拟单个烟雾探测器（Smoke Detector / SD）的行为：
- 接收烟雾源位置
- 计算到探测器的三维欧几里得距离
- 调用 ML 预测器返回报警时间

v5.0 变更：
- 增加 type hints
- 增加 alarm_time 为 numpy.ndarray 类型标注（原实现就是 ndarray）
- 去除多余的 set_x / set_y / set_z 公开方法（只通过 set_pos）
- 保留完整向后兼容
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, Any

import numpy as np


class Detector:
    """
    烟雾探测器。

    Attributes:
        x_pos (float):      X 坐标 (mm)，沿货舱长度方向
        y_pos (float):      Y 坐标 (mm)，沿货舱宽度方向
        z_pos (float):      Z 坐标 (mm)，沿货舱高度方向
        dimension (tuple):   探测器尺寸 (长, 宽) mm
        threshold (float|None): 报警阈值（秒），None 表示使用全局阈值
        SD_id (int):        探测器编号（1-based）
        name (str):         探测器名称（如 'SD1'）
        channel_id (int):    所属通道：0=Channel-A，1=Channel-B
        alarm_time (np.ndarray): 最近一次预测的报警时间（秒），shape (1,)
        dis (float):         最近一次计算的到烟雾源的距离（mm）
    """

    def __init__(
        self,
        predictor: Any = "None",
        x_pos: float = 0.0,
        y_pos: float = 0.0,
        z_pos: float = 0.0,
        dimension: Tuple[float, float] = (140.0, 145.0),
        threshold: Optional[float] = None,
        SD_id: int = 1,
        name: str = "SD",
        channel_id: int = 1,
    ):
        self.x_pos     = x_pos
        self.y_pos     = y_pos
        self.z_pos     = z_pos
        self.dimension = dimension
        self.threshold = threshold
        self.SD_id     = SD_id
        self.name      = name
        self.channel_id = channel_id
        self.pred      = predictor
        self.alarm_time: np.ndarray = np.array([0.0])
        self.dis       = 0.0

    # ------------------------------------------------------------------
    # 位置操作
    # ------------------------------------------------------------------
    def set_pos(self, x_pos: float, y_pos: float, z_pos: float) -> None:
        """一次性设置三维坐标"""
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.z_pos = z_pos

    def set_x(self, x_pos: float) -> None:
        """设置 X 坐标"""
        self.x_pos = x_pos

    def set_y(self, y_pos: float) -> None:
        """设置 Y 坐标"""
        self.y_pos = y_pos

    def set_z(self, z_pos: float) -> None:
        """设置 Z 坐标"""
        self.z_pos = z_pos

    def get_pos(self) -> Tuple[float, float, float]:
        """返回当前三维坐标"""
        return (self.x_pos, self.y_pos, self.z_pos)

    def get_dimension(self) -> Tuple[float, float]:
        """返回探测器尺寸（长, 宽）mm"""
        return self.dimension

    # ------------------------------------------------------------------
    # 阈值
    # ------------------------------------------------------------------
    def set_threshold(self, threshold: float) -> None:
        """设置报警阈值（秒）"""
        self.threshold = threshold

    def get_threshold(self) -> Optional[float]:
        """返回报警阈值（秒）"""
        return self.threshold

    # ------------------------------------------------------------------
    # 通道 & ID
    # ------------------------------------------------------------------
    def set_channel_id(self, channel_id: int) -> None:
        """设置所属通道：0=Channel-A，1=Channel-B"""
        self.channel_id = channel_id

    def set_SD_id(self, SD_id: int) -> None:
        """设置探测器编号（1-based）"""
        self.SD_id = SD_id

    # ------------------------------------------------------------------
    # 核心：报警计算
    # ------------------------------------------------------------------
    def alarm(self, src_pos: tuple | list) -> None:
        """
        计算到烟雾源的距离，并调用 ML 预测器返回报警时间。

        Args:
            src_pos: 烟雾源位置 (x, y, z)，单位 mm
        """
        self.dis = self._cal_distance(
            (self.x_pos, self.y_pos, self.z_pos),
            tuple(src_pos),
        )
        self.alarm_time = self.pred.predict(self.dis / 10.0)

    # ------------------------------------------------------------------
    # 私有
    # ------------------------------------------------------------------
    @staticmethod
    def _cal_distance(pos1: tuple, pos2: tuple) -> float:
        """
        计算两个三维点之间的欧几里得距离（单位：mm）。

        Formula: sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)
        """
        return math.sqrt(
            (pos1[0] - pos2[0]) ** 2
            + (pos1[1] - pos2[1]) ** 2
            + (pos1[2] - pos2[2]) ** 2
        )

    def __repr__(self):
        return (f"<Detector {self.name} id={self.SD_id} ch={self.channel_id} "
                f"pos=({self.x_pos:.1f},{self.y_pos:.1f},{self.z_pos:.1f})>")
