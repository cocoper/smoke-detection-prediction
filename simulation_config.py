# -*- coding:utf-8 -*-
"""
simulation_config.py — 仿真配置的类型化封装

将裸 dict + JSON 配置提升为强类型配置对象，
在构造时做完整校验，运行时通过属性访问，不再出现
bay_dimension[0]/[1]/[2] 谁是谁的困惑。

Schema（与 inputs.json 1:1 对应）：
{
    "type": str,                  # 机型名称（仅展示用）
    "sd_num": int,                # 烟雾探测器总数（必须为偶数）
    "bay": {
        "width_mm":  float,       # 货舱宽度  (Y轴)  mm
        "length_mm": float,       # 货舱长度  (X轴)  mm
        "height_mm": float,       # 货舱高度  (Z轴)  mm
    },
    "criteria_s": int,            # 报警时间阈值（秒），> 0
    "arrange": {
        "method":    str,          # "center" 或 "side"
        "fwd_mm":    int,          # 前壁板到第一个探测器的距离 (mm)
        "aft_mm":    int,          # 后壁板到最后一个探测器的距离 (mm)
        "displace_mm": int,        # 通道相对中线的偏移 (mm)
    }
}

用法：
    from simulation_config import SimulationConfig
    cfg = SimulationConfig.from_json('inputs.json')
    print(cfg.bay.length_mm)        # 不再是 cfg['bay_dimension'][1]
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Literal

# ------------------------------------------------------------------
# 内部子结构
# ------------------------------------------------------------------
@dataclass(frozen=True)
class BayConfig:
    width_mm:  float
    length_mm: float
    height_mm: float

    def __post_init__(self):
        if not self.width_mm  > 0: raise ValueError(f"width_mm  must be > 0, got {self.width_mm}")
        if not self.length_mm > 0: raise ValueError(f"length_mm must be > 0, got {self.length_mm}")
        if not self.height_mm > 0: raise ValueError(f"height_mm must be > 0, got {self.height_mm}")


@dataclass(frozen=True)
class ArrangeConfig:
    method:       Literal["center", "side"]
    fwd_mm:       int = 0
    aft_mm:       int = 0
    displace_mm:  int = 100

    def __post_init__(self):
        if self.method not in ("center", "side"):
            raise ValueError(f"method must be 'center' or 'side', got '{self.method}'")
        if self.fwd_mm < 0: raise ValueError(f"fwd_mm must be >= 0, got {self.fwd_mm}")
        if self.aft_mm < 0: raise ValueError(f"aft_mm must be >= 0, got {self.aft_mm}")
        if self.displace_mm < 0: raise ValueError(f"displace_mm must be >= 0, got {self.displace_mm}")


# ------------------------------------------------------------------
# 主配置
# ------------------------------------------------------------------
@dataclass
class SimulationConfig:
    """
    仿真完整配置。
    支持从 dict / JSON 文件构造，构造时即完成全部校验。
    """
    type_:       str           # 机型（仅展示用）
    sd_num:      int           # 探测器总数（偶数）
    bay:         BayConfig
    criteria_s:   int           # 报警阈值（秒）
    arrange:     ArrangeConfig

    # 内部使用，不暴露给 JSON 序列化
    _src_step_x_mm: int = field(default=1000, repr=False)   # movesrc 步长 X
    _src_step_y_mm: int = field(default=1000, repr=False)   # movesrc 步长 Y
    # 探测器尺寸（UI 专用，不写入 JSON）
    sd_length_mm: float = field(default=140.0, repr=False)
    sd_width_mm:  float = field(default=145.0, repr=False)
    # 自定义探测器布局（手动布放后由 GUI 注入，不参与 JSON 序列化）
    _custom_detectors: list = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------
    # 工厂方法
    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict) -> "SimulationConfig":
        """从裸字典构造（用于解析 inputs.json）"""
        bay = d.get("bay_dimension", [])
        arr = d.get("arrange", {})
        return cls(
            type_     = str(d.get("Type", "")),
            sd_num    = int(d["SD_num"]),
            bay      = BayConfig(
                width_mm  = float(bay[0]) if len(bay) > 0 else 0.0,
                length_mm = float(bay[1]) if len(bay) > 1 else 0.0,
                height_mm = float(bay[2]) if len(bay) > 2 else 0.0,
            ),
            criteria_s = int(d["criteria"]),
            arrange   = ArrangeConfig(
                method      = str(arr.get("method", "center")),
                fwd_mm      = int(arr.get("fwd space", 0)),
                aft_mm      = int(arr.get("aft space", 0)),
                displace_mm = int(arr.get("displace", 100)),
            ),
            sd_length_mm = float(arr.get("sd_length_mm", 140.0)),
            sd_width_mm  = float(arr.get("sd_width_mm", 145.0)),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "SimulationConfig":
        """从 inputs.json 文件路径构造"""
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls.from_dict(d)

    # ------------------------------------------------------------------
    # 派生属性
    # ------------------------------------------------------------------
    @property
    def sd_num_per_channel(self) -> int:
        """每个通道的探测器数量 = sd_num / 2"""
        return self.sd_num // 2

    @property
    def grid_points(self) -> int:
        """
        估算网格总点数（用于进度显示）。
        movesrc 在 length 方向外循环、width 方向内循环，
        所以 length 方向有 floor(length/step_x)+1 个点（含端点），
        width  方向有 floor(width /step_y)+1 个点。
        """
        nx = math.floor(self.bay.length_mm / self._src_step_x_mm) + 1
        ny = math.floor(self.bay.width_mm  / self._src_step_y_mm) + 1
        return nx * ny

    @property
    def steps(self) -> tuple[int, int]:
        """返回 movesrc 的步长 (step_x, step_y)"""
        return self._src_step_x_mm, self._src_step_y_mm

    # ------------------------------------------------------------------
    # 序列化（导出到 dict / JSON，保持 inputs.json 格式兼容）
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        """导出为 dict（兼容旧版 inputs.json 格式）"""
        return {
            "Type":        self.type_,
            "SD_num":     self.sd_num,
            "bay_dimension": [
                self.bay.width_mm,
                self.bay.length_mm,
                self.bay.height_mm,
            ],
            "criteria":   self.criteria_s,
            "arrange": {
                "method":       self.arrange.method,
                "fwd space":    self.arrange.fwd_mm,
                "aft space":    self.arrange.aft_mm,
                "displace":     self.arrange.displace_mm,
                "sd_length_mm": self.sd_length_mm,
                "sd_width_mm":  self.sd_width_mm,
            },
        }

    def to_json(self, path: str | Path, indent: int = 4) -> None:
        """导出为 JSON 文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def validate(self) -> list[str]:
        """
        完整校验，返回错误列表。空列表 = 全部通过。
        """
        errors = []
        if self.sd_num % 2 != 0:
            errors.append(f"sd_num must be even, got {self.sd_num}")
        if self.sd_num < 2:
            errors.append(f"sd_num must be >= 2, got {self.sd_num}")
        # 前向空间不能超过货舱长度
        total_fwd_aft = self.arrange.fwd_mm + self.arrange.aft_mm
        if total_fwd_aft >= self.bay.length_mm:
            errors.append(f"fwd_space + aft_space ({total_fwd_aft}) >= bay length ({self.bay.length_mm})")
        return errors

    def __repr__(self):
        return (f"SimulationConfig(type={self.type_!r}, sd_num={self.sd_num}, "
                f"bay={self.bay.length_mm}x{self.bay.width_mm}x{self.bay.height_mm}mm, "
                f"criteria={self.criteria_s}s, arrange={self.arrange.method})")
