# Smoke Detection Simulation System — Development Documentation

**Document Number:** SDSS-SW-001
**Version:** 5.0
**Date:** 2026-04-18
**Classification:** Internal — Technical Reference

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Module Specification — `sklearn_compat.py`](#3-module-specification--sklearn_compatpy)
4. [Module Specification — `simulation_config.py`](#4-module-specification--simulation_configpy)
5. [Module Specification — `result_manager.py`](#5-module-specification--result_managerpy)
6. [Module Specification — `simulation.py`](#6-module-specification--simulationpy)
7. [Module Specification — `Detector.py`](#7-module-specification--detectorpy)
8. [Module Specification — `cargobay.py`](#8-module-specification--cargobaypy)
9. [Module Specification — `gui_pyside6_winstyle.py`](#9-module-specification--gui_pyside6_winstylepy)
10. [Data Dictionary — `inputs.json`](#10-data-dictionary--inputsjson)
11. [Configuration Guide](#11-configuration-guide)
12. [Build & Deployment](#12-build--deployment)
13. [Changelog](#13-changelog)

---

## 1. Overview

### 1.1 Purpose

The Smoke Detection Simulation System (SDSS) is a desktop application that simulates smoke diffusion within aircraft cargo bays and predicts smoke detector response times using a pre-trained machine learning model. It is designed to support aircraft fire-protection system design and certification activities.

### 1.2 Scope

| Item | Description |
|------|-------------|
| **Type** | Desktop simulation tool |
| **Language** | Python 3.10+ |
| **GUI Framework** | PySide6 (Qt for Python) |
| **ML Backend** | scikit-learn (RandomForestRegressor, DecisionTreeRegressor) |
| **Target Platform** | Windows (WSL2 with WSLg), Linux |
| **Output** | Timestamped CSV result log, matplotlib charts |

### 1.3 Key Capabilities

- Simulate smoke diffusion across a configurable cargo bay grid
- Predict detector alarm times using a trained ML model
- AND-logic dual-channel detection (Channel-A and Channel-B)
- Visualize cargo bay layout and detector placement
- Real-time progress tracking with stop/abort support
- Export simulation results to CSV (non-overwriting, timestamped files)

---

## 2. System Architecture

### 2.1 Component Diagram (v5.0)

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Application                         │
│            gui_pyside6_winstyle.py (v5.0)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Tool Bar    │  │  TabWidget   │  │   Status Bar     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ SimulationThread (QThread)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                    │
│                                                             │
│  ┌──────────────────┐  ┌────────────────┐  ┌────────────┐  │
│  │ SimulationEngine  │  │ SimulationConfig│ │ResultManager│  │
│  │  (simulation.py)  │  │(sim_config.py) │  │(res_mgr.py)│  │
│  └────────┬─────────┘  └────────────────┘  └────────────┘  │
│           │                                              │
│           ▼                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │  Detector     │  │  CargoBay    │  │  sklearn_compat │  │
│  │  (Detector.py)│  │ (cargobay.py)│  │(sklearn_compat)│   │
│  └──────────────┘  └──────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `sklearn_compat.py` | 旧版 sklearn pickle 模型兼容层，独立于 GUI |
| `simulation_config.py` | 类型化配置对象，构造时完整校验 |
| `result_manager.py` | 仿真结果输出抽象，时间戳文件，不覆盖旧结果 |
| `simulation.py` | 仿真核心引擎，与 GUI 完全解耦，支持单元测试 |
| `Detector.py` | 单个探测器模型 |
| `cargobay.py` | 货舱几何模型 |
| `gui_pyside6_winstyle.py` | 桌面 GUI（v5.0，使用新模块）|
| `Environment.py` | **已废弃**，被 `simulation.py` 替代（保留兼容）|

### 2.3 Data Flow

```
inputs.json ──► SimulationConfig ──► SimulationEngine
                                              │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
             Detector × N              CargoBay.isinbay()         ResultManager
                    │                          │                 (result_TIMESTAMP.csv)
                    ▼                          │
             predictor.predict()          smoke_grid
                    │                   (movesrc generator)
                    ▼
             det_logic() ─► Alarm (True/False)
```

---

## 3. Module Specification — `sklearn_compat.py`

### 3.1 Purpose

将旧版 sklearn (< 1.0) 的 pickle 模型兼容逻辑从 GUI 中分离出来，成为独立可测试模块。

### 3.2 API

#### `load_model(path: str) -> LegacyModelWrapper`

加载旧版 sklearn pickle 模型文件，自动处理兼容性问题。

#### `LegacyModelWrapper`

封装旧版 sklearn 模型，提供统一 `.predict()` 接口。

```python
from sklearn_compat import load_model

predictor = load_model('rf_model.model')
alarm_time = predictor.predict([[distance_cm, channel_id]])
# distance_cm: float, channel_id: 0 or 1
```

---

## 4. Module Specification — `simulation_config.py`

### 4.1 Purpose

将裸 `dict` + JSON 配置提升为强类型配置对象，构造时即完成完整校验，不再运行时才发现配置错误。

### 4.2 Class Hierarchy

```
SimulationConfig
├── BayConfig (frozen dataclass)
│   ├── width_mm:  float
│   ├── length_mm: float
│   └── height_mm: float
└── ArrangeConfig (frozen dataclass)
    ├── method:       Literal["center", "side"]
    ├── fwd_mm:       int
    ├── aft_mm:       int
    └── displace_mm:  int
```

### 4.3 Key Methods

| Method | Description |
|--------|-------------|
| `SimulationConfig.from_json(path)` | 从 `inputs.json` 加载 |
| `SimulationConfig.from_dict(d)` | 从 dict 加载（内部使用）|
| `cfg.validate() -> list[str]` | 完整校验，返回错误列表 |
| `cfg.grid_points -> int` | 估算网格总点数（准确的，用于进度）|
| `cfg.to_json(path)` | 导出到 JSON（保持格式兼容）|

### 4.4 Dimension Convention

| Axis | Name | Key | Unit |
|------|------|-----|------|
| X | length | `bay.length_mm` | mm |
| Y | width | `bay.width_mm` | mm |
| Z | height | `bay.height_mm` | mm |

> **注意**：`inputs.json` 的 `bay_dimension` 顺序是 `[width, length, height]`，即 Y, X, Z。`SimulationConfig` 将其映射为具名属性，不再用 `[0]/[1]/[2]` 索引。

---

## 5. Module Specification — `result_manager.py`

### 5.1 Purpose

原来 `Environment.run()` 直接 `open('test_result.csv', 'w')` 写死文件名，每次运行覆盖，无版本管理。`ResultManager` 解决这些问题。

### 5.2 Key Features

- 每次运行生成带时间戳的独立文件（`result_YYYYMMDD_HHMMSS.csv`）
- 可配置输出目录
- 结果在内存中按 `DataFrame` 管理
- 支持 CSV 导出
- 元信息文件（`.meta.json`）记录每次运行的配置参数

### 5.3 API

```python
from result_manager import ResultManager

rm = ResultManager(output_dir="results")

# 方式1：上下文管理器（自动 finalize）
with rm:
    rm.append_row({"No.": 1, "Alarm": True, "SD1": 42.5, ...})
    rm.append_row({"No.": 2, "Alarm": False, ...})

print(rm.latest_file)   # PosixPath("results/result_20260418_143022.csv")
df = rm.latest_dataframe

# 方式2：手动控制
rm.start_run(fieldnames=[...])
rm.append_row(row)
rm.finalize()
```

---

## 6. Module Specification — `simulation.py`

### 6.1 Purpose

将仿真核心逻辑从 GUI 完全解耦，成为独立可测试的 `SimulationEngine`。

### 6.2 Key Features

- 不依赖 GUI / PySide6
- 支持单点仿真 (`run_single()`) 和网格扫描 (`run_grid()`)
- 通过 `GridScanCallbacks` 向上层报告进度和中断
- 精确的网格点数计算（修复了 v4.0 用 `ceil` 导致进度条偏大的 bug）
- 支持 `ResultManager` 结果输出

### 6.3 `SimulationEngine`

```python
from simulation import SimulationEngine, GridScanCallbacks

cfg = SimulationConfig.from_json("inputs.json")
eng = SimulationEngine(cfg, predictor, result_manager=rm)

cbs = GridScanCallbacks(
    on_progress=lambda cur, tot, msg: print(f"{cur}/{tot} {msg}"),
    on_stop=lambda: False,
)

results = eng.run_grid(callbacks=cbs)
# results: list[SingleSimulationResult]
```

### 6.4 `SingleSimulationResult`

```python
result.to_dict()
# {'No.': 1, 'Src Loc.': '(0, 0, 0)', 'SD1': 42.53, 'SD2': 39.21, ..., 'Alarm': True}
```

---

## 7. Module Specification — `Detector.py`

### 7.1 Class: `Detector`

Represents a single smoke detector in the cargo bay.

#### Constructor

```python
class Detector(
    predictor  = 'None',   # ML model with .predict(), or string 'None'
    x_pos      = 0.0,      # mm, along cargo bay length (X)
    y_pos      = 0.0,      # mm, along cargo bay width (Y)
    z_pos      = 0.0,      # mm, along cargo bay height (Z)
    dimension  = (140, 145), # mm, (length, width)
    threshold  = None,      # optional alarm threshold override (seconds)
    SD_id      = 1,         # 1-based detector number
    name       = 'SD',       # display name
    channel_id = 1,         # 0=Channel-A, 1=Channel-B
)
```

#### Key Methods

| Method | Description |
|--------|-------------|
| `set_pos(x, y, z)` | 设置三维坐标 |
| `alarm(src_pos)` | 计算距离并调用 ML 预测器 |
| `alarm_time` | 最近一次预测结果（`np.ndarray`，取 `[0]`）|

---

## 8. Module Specification — `cargobay.py`

### 8.1 Class: `CargoBay`

Represents the physical cargo bay volume.

#### Constructor

```python
class CargoBay(width_mm=1000.0, length_mm=5000.0, height_mm=5000.0)
```

#### Dimension Convention

| Attribute | Axis | Direction |
|-----------|------|-----------|
| `width_mm` | Y | cargo bay width (lateral) |
| `length_mm` | X | cargo bay length (longitudinal) |
| `height_mm` | Z | cargo bay height (vertical) |

#### Key Methods

| Method | Description |
|--------|-------------|
| `isinbay((x, y))` | 判断 (x, y) 是否在货舱投影范围内 |

---

## 9. Module Specification — `gui_pyside6_winstyle.py`

### 9.1 Overview

Desktop GUI using PySide6 with Windows Classic UI style. **v5.0** refactored to use the new modular architecture.

### 9.2 v5.0 Changes from v4.0

| Change | v4.0 | v5.0 |
|--------|------|------|
| sklearn 兼容层 | 内联在 GUI 头部 (~50行) | 独立 `sklearn_compat.py` |
| 配置管理 | 裸 `dict` | `SimulationConfig`（类型化+校验）|
| 结果输出 | `test_result.csv` 覆盖 | `ResultManager` 时间戳文件 |
| 仿真引擎 | `Environment` 紧耦合 | `SimulationEngine` 解耦 |
| 进度计算 | `ceil(length/1000)*ceil(width/1000)` 偏大 | `floor(length/1000)*floor(width/1000)` 精确 |
| 废弃文件 | `gui_pyside6_v3.py`, `gui.py` 存在 | 已删除 |

### 9.3 UI Structure

```
QMainWindow
├── QToolBar
│   ├── [打开] [加载模型] [ | ] [运行] [停止] [ | ] [图表] [导出]
├── QTabWidget
│   ├── Tab 0: Simulation  (配置 | 可视化 | 进度)
│   ├── Tab 1: Results     (QTableWidget)
│   ├── Tab 2: Settings    (输出目录等)
│   └── Tab 3: Help        (使用说明)
├── QTextEdit (日志区)
└── QStatusBar
```

---

## 10. Data Dictionary — `inputs.json`

### 10.1 Schema

```json
{
  "Type":        "string",
  "SD_num":     "integer (even, 2-20)",
  "bay_dimension": [
    "float (width_mm,  Y-axis)",
    "float (length_mm, X-axis)",
    "float (height_mm, Z-axis)"
  ],
  "criteria":   "integer (seconds, > 0)",
  "arrange": {
    "method":    "string (center | side)",
    "fwd space": "integer (mm, >= 0)",
    "aft space":  "integer (mm, >= 0)",
    "displace":   "integer (mm, >= 0)"
  }
}
```

### 10.2 Example

```json
{
  "Type": "CR929-base",
  "SD_num": 10,
  "bay_dimension": [4166, 16184, 1727.6],
  "criteria": 60,
  "arrange": {
    "method": "center",
    "fwd space": 100,
    "aft space": 100,
    "displace": 100
  }
}
```

---

## 11. Configuration Guide

### 11.1 Runtime Environment Variables

| Variable | Values | Default | Effect |
|---------|--------|---------|--------|
| `QT_ENABLE_HIGHDPI_SCALING` | `1` / `0` | `1` | Enables Qt high-DPI scaling |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | `1` / `0` | `1` | Auto-detect display DPI |
| `QT_SCALE_FACTOR` | `1`, `2` | `2` | Fixed scale factor for WSLg |
| `QT_SCALE_FACTOR_ROUNDING_POLICY` | `Passthrough` | `Passthrough` | Rounding mode |

> **Note:** For standard Windows desktops (non-WSL), remove or set `QT_SCALE_FACTOR=1`.

### 11.2 Dependencies

```
PySide6>=6.5
pandas>=2.0
numpy>=1.24
scikit-learn>=1.3
matplotlib>=3.7  (optional, for charts)
```

### 11.3 Running the Application

```bash
cd ~/smoke_project
python gui_pyside6_winstyle.py
```

### 11.4 Programmatic Usage (No GUI)

```python
from sklearn_compat import load_model
from simulation_config import SimulationConfig
from simulation import SimulationEngine, GridScanCallbacks
from result_manager import ResultManager

cfg   = SimulationConfig.from_json("inputs.json")
pred  = load_model("rf_model.model")
rm    = ResultManager(output_dir="results")
eng   = SimulationEngine(cfg, pred, result_manager=rm)

results = eng.run_grid()   # returns list[SingleSimulationResult]
df = rm.latest_dataframe   # pandas DataFrame
```

---

## 12. Build & Deployment

### 12.1 Packaging

```bash
pip install pyinstaller
pyinstaller --one-window --noconsole \
  --add-data "Detector.py;." \
  --add-data "cargobay.py;." \
  --add-data "sklearn_compat.py;." \
  --add-data "simulation_config.py;." \
  --add-data "result_manager.py;." \
  --add-data "simulation.py;." \
  --add-data "inputs.json;." \
  --add-data "rf_model.model;." \
  gui_pyside6_winstyle.py
```

### 12.2 Known Compatibility Notes

| Issue | Cause | Solution |
|-------|-------|----------|
| Model fails to load | sklearn version mismatch | Use `sklearn_compat.load_model()` |
| Chinese font missing in chart | Font not installed in WSL | Install `fonts-noto-cjk` or use `Noto Sans CJK SC` |
| Progress bar stays at 0% | Grid size not pre-calculated | `SimulationEngine.cfg.grid_points` provides accurate count |
| WSLg GUI does not launch | Display not configured | Ensure `DISPLAY` env var is set |

---

## 13. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 5.0 | 2026-04-18 | **Major refactor**: New modular architecture. `sklearn_compat`, `simulation_config`, `result_manager`, `simulation` extracted as independent modules. `SimulationEngine` replaces `Environment`. Progress calculation bug fixed. Legacy GUI files removed. |
| 4.0 | 2026-04-06 | Windows Classic UI redesign. New `gui_pyside6_winstyle.py`. |
| 3.1 | 2026-04-06 | Font replacement (Noto Sans CJK SC); High-DPI scaling; matplotlib Chinese fix |
| 3.0 | 2026-04-05 | CargoBay height fix; Z-axis distance; sklearn compatibility; progress bar; cargo bay visualization |

---

*Document generated for v5.0 branch — SDSS project*
