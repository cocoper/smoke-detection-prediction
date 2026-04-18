# -*- coding:utf-8 -*-
"""
simulation.py — 仿真核心引擎

将仿真逻辑从 GUI 解耦，独立的 SimulationEngine 可以：
- 不依赖 GUI 运行（支持单元测试）
- 支持单点仿真 / 全量网格扫描两种模式
- 通过 callback 机制向上层报告进度
- 通过 ResultManager 管理结果输出（不再写死 test_result.csv）

v5.0 变更：
- 完全独立于 GUI
- 支持 ResultManager 结果管理
- 支持 stop_flag 中断
- 进度回调带准确的总次数

核心概念：
- SimulationEngine: 仿真执行器，管理 Detector 阵列和仿真流程
- SingleSimulationResult: 单次仿真（单烟雾源位置）的结果
- GridScanCallbacks: 进度/中断回调接口
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Generator, Literal

# 核心子模块
sys.path.insert(0, str(Path(__file__).parent))
from Detector import Detector
from cargobay import CargoBay
from result_manager import ResultManager
from simulation_config import SimulationConfig, BayConfig


# ------------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------------
@dataclass
class SingleSimulationResult:
    """
    一次仿真（单个烟雾源位置）的结果。
    """
    test_no:     int
    src_x_mm:    float
    src_y_mm:    float
    src_z_mm:    float = 0.0
    alarm_times: dict = field(default_factory=dict)  # {sd_name: alarm_time_s}
    alarm:      bool = False
    failed_channel: str = ""   # 空字符串 = 双通道均报警

    def to_dict(self) -> dict:
        d = {
            "No.":         self.test_no,
            "Src Loc.":    f"({self.src_x_mm}, {self.src_y_mm}, {self.src_z_mm})",
            "Alarm":       self.alarm,
        }
        d.update(self.alarm_times)
        return d

    @property
    def fieldnames(self) -> list[str]:
        """导出时的 CSV 列顺序"""
        return ["No.", "Src Loc."] + sorted(self.alarm_times.keys()) + ["Alarm"]


# ------------------------------------------------------------------
# 回调接口
# ------------------------------------------------------------------
class GridScanCallbacks:
    """
    网格扫描时的回调集合。
    """
    def __init__(
        self,
        on_progress:   Optional[Callable[[int, int, str], None]] = None,
        on_stop:      Optional[Callable[[], bool]] = None,
    ):
        """
        Args:
            on_progress(current, total, msg): 每次迭代调用
            on_stop():                         返回 True 则中断仿真
        """
        self.on_progress = on_progress
        self.on_stop     = on_stop

    def progress(self, current: int, total: int, msg: str) -> None:
        if self.on_progress:
            self.on_progress(current, total, msg)

    def should_stop(self) -> bool:
        if self.on_stop:
            return self.on_stop()
        return False


# ------------------------------------------------------------------
# 仿真引擎
# ------------------------------------------------------------------
class SimulationEngine:
    """
    烟雾检测仿真执行器。

    负责：
    - 探测器阵列排布
    - 烟雾源网格遍历（movesrc generator）
    - 双通道 AND/OR 报警逻辑
    - 进度报告 & 中断支持
    - 结果输出（通过 ResultManager）

    Usage:
        cfg   = SimulationConfig.from_json("inputs.json")
        eng   = SimulationEngine(cfg, predictor, result_manager=rm)
        eng.run_grid(callbacks=cbs)

        # 或直接单点测试：
        eng.set_source(5000, 2000)
        result = eng.run_single()
    """

    # 固定步长 (mm)，每个网格点间距
    STEP_X_MM = 1000
    STEP_Y_MM = 1000

    def __init__(
        self,
        config: SimulationConfig,
        predictor,                      # ML predictor with .predict()
        result_manager: ResultManager | None = None,
    ):
        self.cfg       = config
        self.predictor = predictor
        self.rm        = result_manager

        # 构建货舱
        self.cargobay = CargoBay(
            width_mm  = config.bay.width_mm,
            length_mm = config.bay.length_mm,
            height_mm = config.bay.height_mm,
        )

        # 构建探测器阵列
        self.detectors = [
            Detector(predictor=predictor, name=f"SD{i+1}")
            for i in range(config.sd_num)
        ]

        # 通道分组
        self.CHA_SD: list[Detector] = []   # Channel-A (odd id)
        self.CHB_SD: list[Detector] = []   # Channel-B (even id)

        # 烟雾源
        self.smoke_src_pos = (0.0, 0.0, 0.0)

        # 排布
        self._apply_arrangement()

        # 初始化结果管理器
        if self.rm is not None:
            fieldnames = ["No.", "Src Loc."] + [d.name for d in self.detectors] + ["Alarm"]
            self.rm.start_run(metadata={
                "config_type":   config.type_,
                "sd_num":        config.sd_num,
                "bay":           f"{config.bay.length_mm}x{config.bay.width_mm}x{config.bay.height_mm}",
                "criteria_s":    config.criteria_s,
                "arrange_method": config.arrange.method,
            })
            self._fieldnames = fieldnames

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def run_grid(self, callbacks: GridScanCallbacks | None = None) -> list[SingleSimulationResult]:
        """
        执行全量网格扫描仿真。

        Returns:
            list[SingleSimulationResult]: 所有仿真结果列表
        """
        cbs = callbacks or GridScanCallbacks()
        results: list[SingleSimulationResult] = []
        test_no  = 0
        total    = self.cfg.grid_points   # 准确的网格总数

        for src_pos in self._movesrc():
            if cbs.should_stop():
                print("仿真已被用户中断")
                break

            test_no += 1
            self.smoke_src_pos = (src_pos[0], src_pos[1], 0.0)

            # 计算所有探测器报警时间
            alarm_times = {}
            for sd in self.detectors:
                sd.alarm(self.smoke_src_pos)
                alarm_times[sd.name] = sd.alarm_time[0]

            # 双通道逻辑
            alarm, failed_ch = self._det_logic()

            # 记录结果
            result = SingleSimulationResult(
                test_no     = test_no,
                src_x_mm    = src_pos[0],
                src_y_mm    = src_pos[1],
                alarm_times = alarm_times,
                alarm       = alarm,
                failed_channel = failed_ch,
            )
            results.append(result)

            # 写结果管理器
            if self.rm is not None:
                self.rm.append_row(result.to_dict())

            cbs.progress(test_no, total, f"测试 #{test_no}")

        if self.rm is not None:
            self.rm.finalize()

        return results

    def run_single(self) -> SingleSimulationResult:
        """
        执行单点仿真（当前烟雾源位置）。

        Returns:
            SingleSimulationResult: 本次仿真结果
        """
        alarm_times = {}
        for sd in self.detectors:
            sd.alarm(self.smoke_src_pos)
            alarm_times[sd.name] = sd.alarm_time[0]
        alarm, failed_ch = self._det_logic()

        return SingleSimulationResult(
            test_no     = 1,
            src_x_mm    = self.smoke_src_pos[0],
            src_y_mm    = self.smoke_src_pos[1],
            alarm_times = alarm_times,
            alarm       = alarm,
            failed_channel = failed_ch,
        )

    def set_source(self, x_mm: float, y_mm: float) -> bool:
        """
        设置烟雾源位置（如果超出货舱范围则返回 False）。

        Returns:
            True  — 成功设置
            False — 超出边界，未修改
        """
        if not self.cargobay.isinbay((x_mm, y_mm)):
            print("wrong source location: out of boundary")
            return False
        self.smoke_src_pos = (float(x_mm), float(y_mm), 0.0)
        return True

    def detector_info(self) -> list[tuple]:
        """
        返回探测器布局信息，用于 GUI 可视化。

        Returns:
            [(x_mm, y_mm, name, channel_id), ...]
        """
        return [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in self.detectors]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _apply_arrangement(self) -> None:
        """根据配置排布探测器"""
        cfg = self.cfg.arrange
        method  = cfg.method
        fwd     = cfg.fwd_mm
        aft     = cfg.aft_mm
        displace = cfg.displace_mm

        # 通道 & ID 初始化
        for sd in self.detectors:
            sd.set_SD_id(self.detectors.index(sd) + 1)
            if sd.SD_id % 2 == 1:
                sd.set_channel_id(0)
                self.CHA_SD.append(sd)
            else:
                sd.set_channel_id(1)
                self.CHB_SD.append(sd)

        if method == "center":
            x_group, y_group = self._center_arrange(
                self.cfg.sd_num, fwd, aft, displace)
        else:
            x_group, y_group = self._side_arrange(
                self.cfg.sd_num, fwd, aft, displace)

        # 设置 A 通道
        for i, sd in enumerate(self.CHA_SD):
            sd.set_pos(x_group[i], y_group[0], self.cargobay.height_mm)
        # 设置 B 通道
        for i, sd in enumerate(self.CHB_SD):
            sd.set_pos(x_group[i], y_group[1], self.cargobay.height_mm)

    def _center_arrange(self, SD_NUM, fwd, aft, displace=0):
        """中心排布：成对探测器共享 X，Channel-A/B 在 Y 方向偏移"""
        assert SD_NUM % 2 == 0, "sd_num must be even"
        group_NUM = SD_NUM // 2
        sd_dim = self.detectors[0].get_dimension()
        sd_len  = sd_dim[0]

        x_group = []
        total_space = SD_NUM * sd_len + (SD_NUM - 1) * (
            (self.cargobay.length_mm - fwd - aft - SD_NUM * sd_len) / (SD_NUM - 1)
        )
        gap = (self.cargobay.length_mm - fwd - aft - sd_len * group_NUM) / max(group_NUM - 1, 1)

        x0 = fwd + sd_len / 2
        x_group.append(x0)
        for _ in range(group_NUM - 1):
            x0 = x0 + gap + sd_len
            x_group.append(x0)
        x_group[-1] = self.cargobay.length_mm - aft - sd_len / 2

        y_group = [
            self.cargobay.width_mm / 2 + displace + sd_dim[1] / 2,
            self.cargobay.width_mm / 2 - displace - sd_dim[1] / 2,
        ]
        return x_group, y_group

    def _side_arrange(self, SD_NUM, fwd, aft, displace=50):
        """侧向排布：所有 A 通道在上侧，B 通道在下侧"""
        assert SD_NUM % 2 == 0, "sd_num must be even"
        sd_dim  = self.detectors[0].get_dimension()
        sd_len  = sd_dim[0]
        gap = (self.cargobay.length_mm - fwd - aft - sd_len * SD_NUM) / max(SD_NUM - 1, 1)

        x_group = []
        x0 = fwd + sd_len / 2
        x_group.append(x0)
        for _ in range(SD_NUM - 1):
            x0 = x0 + gap + sd_len
            x_group.append(x0)
        x_group[-1] = self.cargobay.length_mm - aft - sd_len / 2

        y_group = [
            self.cargobay.width_mm / 2 + displace + sd_dim[1] / 2,
            self.cargobay.width_mm / 2 - displace - sd_dim[1] / 2,
        ]
        return x_group, y_group

    def _det_logic(self) -> tuple[bool, str]:
        """
        双通道报警逻辑。

        Returns:
            (alarm, failed_channel_str):
            - alarm: True = 报警触发
            - failed_channel_str: ""=无失败，"A"=A通道未触发，"B"=B通道未触发
        """
        crit = self.cfg.criteria_s
        cha_ok = any(sd.alarm_time[0] <= crit for sd in self.CHA_SD)
        chb_ok = any(sd.alarm_time[0] <= crit for sd in self.CHB_SD)

        if cha_ok and chb_ok:
            return True, ""
        elif not cha_ok and not chb_ok:
            return False, "AB"
        elif not cha_ok:
            return False, "A"
        else:
            return False, "B"

    def _movesrc(self) -> Generator[tuple[float, float], None, None]:
        """
        烟雾源网格遍历 generator。

        X 方向外循环，Y 方向内循环。
        每个方向步长为 STEP_X_MM / STEP_Y_MM。
        """
        src_x = 0.0
        while src_x <= self.cargobay.length_mm:
            src_y = 0.0
            while src_y <= self.cargobay.width_mm:
                yield src_x, src_y
                src_y = min(src_y + self.STEP_Y_MM, self.cargobay.width_mm)
            src_x = min(src_x + self.STEP_X_MM, self.cargobay.length_mm)

    def __repr__(self):
        return (f"<SimulationEngine sd_num={self.cfg.sd_num} "
                f"bay={self.cargobay.length_mm}x{self.cargobay.width_mm}mm "
                f"method={self.cfg.arrange.method}>")
