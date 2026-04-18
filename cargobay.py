# -*- coding:utf-8 -*-
"""
cargobay.py — 货舱几何模型

描述货舱的长、宽、高三维尺寸，提供：
- 尺寸的 getter/setter
- 一点是否在货舱内部（isinbay）
- 尺寸校验

v5.0 变更：
- 增加 type hints
- 去除无用的 `detectorSeries` 属性（从未被使用）
- 增加 volume 属性
- 增加 __repr__
"""
from __future__ import annotations

from typing import Tuple


class CargoBay:
    """
    货舱几何模型。

    坐标系（右手系）：
        X 轴：沿货舱长度方向（航向）
        Y 轴：沿货舱宽度方向（展向）
        Z 轴：沿货舱高度方向（垂向）

    Attributes:
        width_mm  (float):  货舱宽度  (Y)，单位 mm
        length_mm (float):  货舱长度  (X)，单位 mm
        height_mm (float):  货舱高度  (Z)，单位 mm
    """

    def __init__(
        self,
        width_mm:  float = 1000.0,
        length_mm: float = 5000.0,
        height_mm: float = 5000.0,
    ):
        if width_mm  <= 0: raise ValueError("width_mm  must be > 0")
        if length_mm <= 0: raise ValueError("length_mm must be > 0")
        if height_mm <= 0: raise ValueError("height_mm must be > 0")

        self._width  = width_mm
        self._length = length_mm
        self._height = height_mm

    # ------------------------------------------------------------------
    # 尺寸访问
    # ------------------------------------------------------------------
    def get_dimension(self) -> Tuple[float, float, float]:
        """
        返回货舱尺寸 (width, length, height)，单位 mm。
        与 inputs.json 的 bay_dimension [width, length, height] 完全对应。
        """
        return (self._width, self._length, self._height)

    def set_dimension(self, width_mm: float, length_mm: float, height_mm: float) -> None:
        """一次性设置三个尺寸，无校验（保留原行为）"""
        self._width  = width_mm
        self._length = length_mm
        self._height = height_mm

    def set_prop(self, cargo_prop: dict) -> None:
        """
        从 dict 设置尺寸（兼容旧接口）。

        Expected keys: 'width', 'length', 'height'（单位 mm）
        """
        self._width  = cargo_prop["width"]
        self._length = cargo_prop["length"]
        self._height = cargo_prop["height"]

    # ------------------------------------------------------------------
    # 派生属性
    # ------------------------------------------------------------------
    @property
    def volume_mm3(self) -> float:
        """货舱容积，单位 mm³"""
        return self._width * self._length * self._height

    @property
    def width_mm(self) -> float:
        return self._width

    @property
    def length_mm(self) -> float:
        return self._length

    @property
    def height_mm(self) -> float:
        return self._height

    # ------------------------------------------------------------------
    # 几何操作
    # ------------------------------------------------------------------
    def isinbay(self, pos) -> bool:
        """
        判断二维点 (x, y) 是否在货舱平面投影范围内。

        Args:
            pos: (x, y) 坐标，单位 mm

        Returns:
            True  — x < length AND y < width（在货舱范围内）
            False — 超出范围
        """
        return pos[0] < self._length and pos[1] < self._width

    def __repr__(self):
        return (f"<CargoBay {self._length}x{self._width}x{self._height} mm "
                f"vol={self.volume_mm3/1e9:.2f}m³>")
