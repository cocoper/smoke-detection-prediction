# Smoke Detection Simulation System — Development Documentation

**Document Number:** SDSS-SW-001
**Version:** 5.1
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

The Smoke Detection Simulation System (SDSS) is a desktop application that simulates smoke diffusion within aircraft cargo bays and predicts smoke detector response times using a pre-trained machine learning model. It supports aircraft fire-protection system design and certification activities.

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

- Simulate smoke diffusion across a configurable cargo bay grid (1000mm step resolution)
- Predict detector alarm times using a trained ML model
- AND-logic dual-channel detection (Channel-A and Channel-B must both alarm)
- Cargo bay layout visualization with detector positions
- **NEW v5.1:** Color-coded heatmap overlay showing alarm/miss per grid point
- **NEW v5.1:** Interactive drag-and-drop detector positioning with confirm workflow
- **NEW v5.1:** Detector size configuration dialog with live preview
- **NEW v5.1:** Config loading auto-syncs drag page探测器列表
- Versioned result management (timestamped CSV files, never overwritten)
- Simulation result comparison across multiple runs
- matplotlib charts:报警时间直方图, 报警率饼图, 多运行对比柱状图

### 1.4 Project Structure

```
smoke_project/
├── main.py                          # CLI entry point (legacy)
├── gui_pyside6_winstyle.py          # GUI application (main launcher)
├── Detector.py                       # Smoke detector model
├── cargobay.py                       # Cargo bay geometry model
├── Environment.py                    # Legacy environment model (deprecated)
├── simulation.py                     # Core simulation engine
├── simulation_config.py              # Typed configuration object
├── result_manager.py                 # Versioned result management
├── sklearn_compat.py                  # Legacy sklearn model compatibility
├── inputs.json                       # Configuration file
├── rf_model.model                    # Trained ML model (pickle)
├── rf_model_all.model                # Full-featured ML model
├── rf_model_all_verbose1.model       # Verbose variant model
├── icons/                            # GUI icon assets
│   ├── icon_open.png
│   ├── icon_save.png
│   ├── icon_run.png
│   ├── icon_stop.png
│   ├── icon_model.png
│   ├── icon_detector.png
│   ├── icon_drag.png
│   ├── icon_bay.png
│   ├── icon_chart.png
│   ├── icon_compare.png
│   ├── icon_export.png
│   ├── icon_history.png
│   ├── icon_heatmap.png
│   ├── icon_settings.png
│   ├── icon_help.png
│   ├── icon_delete.png
│   └── icon_alert.png
└── docs/
    └── development-documentation.md  # This document
```

---

## 2. System Architecture

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     GUI Layer (PySide6)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ MainWindow   │  │DetectorDrag  │  │ DetectorSizeDialog   │  │
│  │ (tabs + toolbar)│ │  Widget     │  │  (_SizePreviewWidget)│  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                    │
│  ┌──────▼─────────────────▼────────────────────────────────┐  │
│  │              CargoBayWidget (heatmap + detectors)         │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────┐
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────┐  ┌───────────────┐  ┌─────────────────────┐
│SimulationConfig │  │SimulationEngine│  │   ResultManager     │
│  (typed config) │  │  (core engine)  │  │ (versioned output)   │
└────────┬────────┘  └───────┬───────┘  └─────────────────────┘
         │                    │
         │         ┌──────────┴──────────┐
         │         │                     │
         ▼         ▼                     ▼
┌─────────────────┐  ┌────────────┐  ┌─────────────────────────┐
│  inputs.json    │  │  Detector   │  │   CargoBay              │
│  (JSON config) │  │  (SD model) │  │   (geometry)            │
└─────────────────┘  └─────┬──────┘  └─────────────────────────┘
                           │
                           ▼
                   ┌─────────────────┐
                   │  ML Predictor    │
                   │  (sklearn model) │
                   └─────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `MainWindow` | Tab-based GUI, toolbar, menu bar, simulation orchestration |
| `CargoBayWidget` | 2D cargo bay canvas with heatmap overlay and detector rendering |
| `DetectorDragWidget` | Drag-and-drop detector layout editor with table + canvas |
| `_DetectorCanvas` | Low-level mouse event handling for detector drag/add/delete |
| `DetectorSizeDialog` | Modal dialog for L×W×H detector dimension configuration |
| `_SizePreviewWidget` | Three-view schematic preview (top/side/isometric) of detector |
| `SimulationEngine` | Grid scan loop, alarm logic, smoke source iteration, result collection |
| `SimulationConfig` | Type-safe configuration from inputs.json, validates on construction |
| `ResultManager` | Timestamped CSV output, metadata, run history listing |
| `Detector` | 3D Euclidean distance calc, alarm time prediction via ML |
| `CargoBay` | Cargo bay geometry (width/length/height), boundary check |
| `sklearn_compat` | Legacy pickle loading, missing_go_to_left patch for old sklearn |

### 2.3 Data Flow

```
1. User loads inputs.json  →  SimulationConfig.from_json()
   └── SimulationConfig validates and stores bay/detector/arrange params

2. User loads .model file  →  load_model() from sklearn_compat
   └── Returns LegacyModelWrapper with .predict() interface

3. User customizes detectors (optional)
   a) Via DetectorDragWidget: drag/add/delete on canvas → list of (x,y,name,ch)
   b) Via DetectorSizeDialog: set L/W/H dimensions
   c) Clicks "确认布放" (Confirm) → locks layout → "应用到仿真" (Apply to Sim)

4. User clicks "运行" (Run)
   a) MainWindow._run() constructs SimulationConfig
   b) cfg._custom_detectors = drag_wid.get_detectors() (if any)
   c) SimulationThread starts, creates SimulationEngine
   d) Engine iterates smoke source grid via _movesrc() generator
   e) For each grid point: all detectors call alarm(src_pos)
   f) det_logic() evaluates AND of Channel-A and Channel-B
   g) ResultManager.append_row() writes to timestamped CSV

5. Simulation completes
   a) MainWindow._on_done() loads latest CSV via ResultManager
   b) parse_src_loc() parses "Src Loc." column strings → (x, y, z)
   c) heatmap dict {(x,y): alarm_bool} built and passed to CargoBayWidget
   d) CargoBayWidget renders color-coded dots over cargo bay schematic
   e) Results tab shows full DataFrame; chart/compare/export available
```

### 2.4 Coordinate System

The system uses a right-handed 3D Cartesian coordinate system aligned with aircraft axes:

| Axis | Direction | Units | Used For |
|------|-----------|-------|---------|
| **X** | Along cargo bay length (fore-aft / nose-to-tail) | mm | Smoke source X, detector X positions |
| **Y** | Along cargo bay width (spanwise / wing-to-wing) | mm | Smoke source Y, detector Y positions |
| **Z** | Along cargo bay height (vertical) | mm | Fixed at ceiling (detector Z = bay height); smoke source Z always 0 |

**Cargo Bay Layout (top view):**
```
←── length (X) ──→
┌─────────────────────┐  ↑
│   Forward Wall      │  │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  │  width (Y)
│                     │  │
│   AFT WALL           │  ↓
└─────────────────────┘
```

Channel-A detectors (odd IDs): displayed in green
Channel-B detectors (even IDs): displayed in blue

---

## 3. Module Specification — `sklearn_compat.py`

### 3.1 Purpose

Loads legacy sklearn pickle files (pre-1.0) that used `sklearn.ensemble.forest` and `sklearn.tree.tree` module paths that changed in sklearn ≥1.0. Also patches the `Tree` class to add the `missing_go_to_left` field introduced in sklearn 1.1+.

### 3.2 Public API

```python
from sklearn_compat import load_model

model = load_model(path: str) -> LegacyModelWrapper
```

### 3.3 Classes

#### `LegacyModelWrapper`

Wraps a raw sklearn estimator and exposes a unified `.predict()` interface.

**Attributes:**
| Attribute | Type | Description |
|-----------|------|-------------|
| `_model` | object | The underlying sklearn estimator |
| `n_outputs_` | int | Number of outputs (default 1) |
| `n_features_in_` | int | Number of input features |
| `estimators_` | list | List of base estimator trees |
| `classes_` | array | Class labels (if applicable) |

**Methods:**
| Method | Returns | Description |
|--------|---------|-------------|
| `predict(X)` | `np.ndarray` | Average prediction across all trees |
| `__repr__()` | str | Human-readable summary |

#### `_PatchedTree`

Subclass of `sklearn.tree._tree.Tree` that adds the `missing_go_to_left` field during unpickling via `__setstate__`.

#### `_CompatUnpickler`

Custom pickle Unpickler that redirects old module paths:
- `sklearn.ensemble.forest` → `sklearn.ensemble._forest`
- `sklearn.tree.tree` → `sklearn.tree`

Also intercepts `Tree` class lookups and returns `_PatchedTree` instead.

### 3.4 Usage Example

```python
from sklearn_compat import load_model

# Load legacy model
predictor = load_model('rf_model_all.model')

# Use like any sklearn model
alarm_time = predictor.predict(distance_mm / 10.0)
# distance is in mm, model expects meters (÷10)
```

---

## 4. Module Specification — `simulation_config.py`

### 4.1 Purpose

Provides type-safe, validated configuration objects. Eliminates the `bay_dimension[0/1/2]` positional ambiguity from the legacy dict-based approach. Full validation on construction.

### 4.2 Data Classes

#### `BayConfig` (frozen dataclass)

| Field | Type | Units | Validation |
|-------|------|-------|------------|
| `width_mm` | float | mm | must be > 0 |
| `length_mm` | float | mm | must be > 0 |
| `height_mm` | float | mm | must be > 0 |

#### `ArrangeConfig` (frozen dataclass)

| Field | Type | Units | Default | Validation |
|-------|------|-------|---------|------------|
| `method` | Literal["center", "side"] | — | — | must be "center" or "side" |
| `fwd_mm` | int | mm | 0 | must be >= 0 |
| `aft_mm` | int | mm | 0 | must be >= 0 |
| `displace_mm` | int | mm | 100 | must be >= 0 |

#### `SimulationConfig` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `type_` | str | Aircraft type name (display only) |
| `sd_num` | int | Total detector count (must be even) |
| `bay` | BayConfig | Cargo bay dimensions |
| `criteria_s` | int | Alarm time threshold in seconds |
| `arrange` | ArrangeConfig | Detector arrangement parameters |
| `_src_step_x_mm` | int | Smoke source grid step in X (default 1000) |
| `_src_step_y_mm` | int | Smoke source grid step in Y (default 1000) |
| `sd_length_mm` | float | Detector length (UI-only, default 140.0) |
| `sd_width_mm` | float | Detector width (UI-only, default 145.0) |
| `_custom_detectors` | list | GUI-injected list of (x,y,name,ch), not serialized |

### 4.3 Factory Methods

```python
# From JSON file
cfg = SimulationConfig.from_json('inputs.json')

# From dict (parsed JSON)
cfg = SimulationConfig.from_dict({'Type': 'CR929-base', 'SD_num': 10, ...})
```

### 4.4 Derived Properties

```python
cfg.sd_num_per_channel  # = sd_num // 2
cfg.grid_points          # = floor(length/1000+1) * floor(width/1000+1)
cfg.steps               # = (1000, 1000) tuple of step sizes
```

### 4.5 Serialization

```python
# Export to dict (inputs.json compatible format)
d = cfg.to_dict()

# Export to JSON file
cfg.to_json('output.json')
```

### 4.6 Validation

```python
errors = cfg.validate()  # Returns list of error strings, empty = pass
```

Validation checks:
- `sd_num` is even
- `sd_num >= 2`
- `fwd_space + aft_space < bay length` (detectors must fit)

---

## 5. Module Specification — `result_manager.py`

### 5.1 Purpose

Replaces the legacy hardcoded `test_result.csv` approach with versioned output. Each simulation run generates a timestamped CSV file (e.g., `result_20260418_143022.csv`) plus a companion `.meta.json` metadata file. Old results are never overwritten.

### 5.2 Public API

```python
from result_manager import ResultManager

rm = ResultManager(output_dir=".", filename_fmt=None)
rm.start_run(fieldnames=["No.", "Src Loc.", "SD1", "SD2", ...], metadata={...})
rm.append_row({"No.": 1, "Src Loc.": "(0, 0, 0)", "SD1": 12.5, "Alarm": True})
rm.append_row(row_dict)  # repeat for each test
rm.finalize()            # closes files, writes .meta.json

df = rm.latest_dataframe  # read back as DataFrame
runs = rm.list_runs()    # list all historical runs
```

### 5.3 Output File Naming

Format: `result_{YYYYMMDD}_{HHMMSS}.csv`
Example: `result_20260418_163946.csv`

Companion metadata: `result_20260418_163946.meta.json`

### 5.4 Metadata Schema (`.meta.json`)

```json
{
  "timestamp": "20260418_163946",
  "sd_num": 10,
  "bay": "16184x4166x1727.6",
  "criteria_s": 60,
  "arrange_method": "center",
  "n_rows": 68
}
```

### 5.5 ResultManager Lifecycle

```
start_run()  →  opens new CSV file, writes header
     ↓
append_row()  →  called N times (once per grid point)
     ↓
finalize()    →  closes CSV, writes .meta.json
```

Multiple consecutive `start_run()` calls are supported; each closes the previous run automatically.

---

## 6. Module Specification — `simulation.py`

### 6.1 Purpose

Core simulation engine decoupled from GUI. Can run headless (no GUI) for unit testing. Manages the full grid scan loop, dual-channel alarm logic, progress callbacks, and result collection.

### 6.2 Classes

#### `SingleSimulationResult` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `test_no` | int | Test sequence number |
| `src_x_mm` | float | Smoke source X (mm) |
| `src_y_mm` | float | Smoke source Y (mm) |
| `src_z_mm` | float | Smoke source Z (mm, always 0.0) |
| `alarm_times` | dict | `{sd_name: alarm_time_s}` for each detector |
| `alarm` | bool | Overall alarm decision (AND of both channels) |
| `failed_channel` | str | ""=both alarmed, "A"=A failed, "B"=B failed, "AB"=both failed |

Methods: `to_dict()`, `fieldnames` property

#### `GridScanCallbacks`

Callback container for grid scan events.

```python
cbs = GridScanCallbacks(
    on_progress=lambda current, total, msg: update_progress_bar(),
    on_stop=lambda: user_requested_stop,
)
```

#### `SimulationEngine`

**Constructor:**
```python
SimulationEngine(
    config: SimulationConfig,
    predictor,           # ML predictor from sklearn_compat
    result_manager: ResultManager | None = None,
)
```

**Key Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `run_grid(callbacks)` | `list[SingleSimulationResult]` | Full grid scan |
| `run_single()` | `SingleSimulationResult` | Single-point test at current smoke source |
| `set_source(x_mm, y_mm)` | bool | Set smoke source position; returns False if out of bay bounds |
| `detector_info()` | `list[tuple]` | Returns `[(x,y,name,ch), ...]` for GUI visualization |

**Internal Methods:**

| Method | Description |
|--------|-------------|
| `_apply_arrangement()` | Places detectors per `ArrangeConfig` method |
| `_center_arrange()` | Center排布: pairs share X, Channel-A/B offset in Y |
| `_side_arrange()` | 侧向排布: all A on top row, all B on bottom row |
| `_det_logic()` | AND alarm: both channels must have ≥1 detector alarm within criteria |
| `_movesrc()` | Generator: iterates smoke source over cargo bay grid (Y inner, X outer) |

**Fixed Constants:**
- `STEP_X_MM = 1000` — grid step along cargo bay length
- `STEP_Y_MM = 1000` — grid step along cargo bay width

### 6.3 Alarm Logic

The dual-channel AND logic requires at least one Channel-A detector AND at least one Channel-B detector to report alarm time ≤ `criteria_s`:

```python
cha_ok = any(sd.alarm_time[0] <= crit for sd in CHA_SD)
chb_ok = any(sd.alarm_time[0] <= crit for sd in CHB_SD)
alarm = cha_ok and chb_ok
```

### 6.4 Smoke Source Grid Traversal

The `_movesrc()` generator scans the cargo bay:
- **Outer loop:** X direction (length), step 1000mm
- **Inner loop:** Y direction (width), step 1000mm
- Endpoints (length, width) are included in the grid

Example for CR929 bay (16184×4166mm):
- X points: 0, 1000, 2000, ..., 16000, 16184 → 18 points
- Y points: 0, 1000, 2000, 3000, 4000, 4166 → 5 points
- Total grid points: 18 × 5 = 90

---

## 7. Module Specification — `Detector.py`

### 7.1 Purpose

Models a single smoke detector (SD). Computes 3D Euclidean distance from detector to smoke source, then calls the ML predictor to get alarm time.

### 7.2 Class: `Detector`

**Constructor Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `predictor` | Any | "None" | ML model with `.predict()` method |
| `x_pos` | float | 0.0 | X coordinate (mm) |
| `y_pos` | float | 0.0 | Y coordinate (mm) |
| `z_pos` | float | 0.0 | Z coordinate (mm) |
| `dimension` | tuple[float,float] | (140.0, 145.0) | (length, width) in mm |
| `threshold` | float\|None | None | Per-detector alarm threshold (s), None = use global |
| `SD_id` | int | 1 | Detector ID (1-based) |
| `name` | str | "SD" | Detector name (e.g., "SD1") |
| `channel_id` | int | 1 | 0=Channel-A, 1=Channel-B |

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `x_pos`, `y_pos`, `z_pos` | float | Current 3D position (mm) |
| `dimension` | tuple | Detector size (length, width) mm |
| `threshold` | float\|None | Per-detector threshold |
| `SD_id` | int | 1-based ID |
| `name` | str | Display name |
| `channel_id` | int | 0=Channel-A, 1=Channel-B |
| `alarm_time` | `np.ndarray` | Latest prediction, shape (1,) |
| `dis` | float | Distance to current smoke source (mm) |

**Key Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `set_pos(x, y, z)` | None | Set all three coordinates at once |
| `get_pos()` | tuple[float,float,float] | Get current position |
| `get_dimension()` | tuple[float,float] | Get detector (L, W) |
| `set_threshold(t)` | None | Set per-detector threshold |
| `get_threshold()` | float\|None | Get threshold |
| `set_channel_id(ch)` | None | Set channel (0=A, 1=B) |
| `set_SD_id(id)` | None | Set 1-based ID |
| `alarm(src_pos)` | None | Compute distance + predict alarm time |

**Distance Calculation:**
```
dis = sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)   [mm]
alarm_time = predictor.predict(dis / 10.0)    [model expects meters]
```

**`__repr__`:**
```
<Detector SD1 id=1 ch=0 pos=(1000.0,2083.0,1727.6)>
```

---

## 8. Module Specification — `cargobay.py`

### 8.1 Purpose

Models the cargo bay physical geometry. Provides dimension access, boundary checking, and volume calculation.

### 8.2 Class: `CargoBay`

**Constructor:**
```python
CargoBay(width_mm=1000.0, length_mm=5000.0, height_mm=5000.0)
```

**Coordinate System (right-handed):**
- X: along length (fore-aft)
- Y: along width (spanwise)
- Z: along height (vertical)

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `get_dimension()` | tuple[float,float,float] | Returns (width, length, height) in mm |
| `set_dimension(w, l, h)` | None | Set all three at once |
| `set_prop(cargo_prop)` | None | Set from dict with keys 'width','length','height' |
| `isinbay(pos)` | bool | True if (x,y) is within length×width bounds |

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `volume_mm3` | float | Width×Length×Height mm³ |
| `width_mm` | float | Read-only width |
| `length_mm` | float | Read-only length |
| `height_mm` | float | Read-only height |

**`__repr__`:**
```
<CargoBay 16184x4166x1727.6mm vol=1.17m³>
```

---

## 9. Module Specification — `gui_pyside6_winstyle.py`

### 9.1 Purpose

Main GUI application. Classic Windows native style with tabbed interface, toolbar, and status bar. Handles all user interaction: config loading, model loading, simulation execution, results display, and history management.

### 9.2 Window Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Menu Bar: 文件(F)  帮助(H)                                    │
├──────────────────────────────────────────────────────────────┤
│ Toolbar: [打开] [加载模型] [运行] [停止] | [图表] [对比] [导出] │
├──────────────────────────────────────────────────────────────┤
│ TabWidget                                                     │
│  ┌──────┬────────────┬──────┬────────┬──────┐                 │
│  │ 仿真  │ 探测器定位 │ 结果  │  设置  │ 帮助  │                │
│  └──────┴────────────┴──────┴────────┴──────┘                 │
│  [Content varies by selected tab]                             │
├──────────────────────────────────────────────────────────────┤
│ Log: [simulation output text]                                 │
├──────────────────────────────────────────────────────────────┤
│ Status Bar: [status message]                                  │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 Tab Descriptions

#### Tab 0: 仿真 (Simulation)

```
┌─────────────────────────────────────────────────────┐
│ 基本参数                    布局参数                │
│ 机型: [____CR929-base__]    排布: [center ▼]       │
│ 探测器数量: [10]            前端间距: [100]        │
│ 货舱宽度: [4166] mm         后端间距: [100]        │
│ 货舱长度: [16184] mm        偏移: [100]           │
│ 货舱高度: [1727.6] mm                              │
│ 报警阈值: [60] s                                   │
├─────────────────────────────────────────────────────┤
│         CargoBayWidget (货舱可视化 + 热力图)        │
│                                                     │
│  [Green dots = Channel-A, Blue dots = Channel-B]    │
│  [Heatmap: green dot = alarm, red dot = miss]      │
│                                                     │
├─────────────────────────────────────────────────────┤
│ 运行状态: [====progress bar====] [测试 #42]        │
└─────────────────────────────────────────────────────┘
```

#### Tab 1: 探测器定位 (Detector Positioning)

```
┌────────────────────────┬──────────────────────────┐
│                        │ 探测器列表（双击编辑坐标）  │
│  _DetectorCanvas       │  名称    X(mm)  Y(mm) 通道 │
│  (drag/drop canvas)    │  SD1    1000   2083   A    │
│                        │  SD2    1000   2083   B    │
│  Left-click: add SD    │  SD3    3000   2083   A    │
│  Right-click: menu     │  ...                        │
│  Drag: move position   ├───────────────────────────-┤
│                        │ [自动均匀布局] [确认布放]    │
│                        │ [应用到仿真]   [取消确认]    │
│                        ├───────────────────────────-┤
│                        │ 货舱尺寸: 宽度[4166] 长度[16184]│
│                        │ 显示通道: [全部 ▼]          │
└────────────────────────┴──────────────────────────┘
```

#### Tab 2: 结果 (Results)

Full DataFrame table of latest simulation run with sortable columns: No., Src Loc., SD1, SD2, ..., Alarm.

#### Tab 3: 设置 (Settings)

- Output directory QLineEdit
- Simulation history table (double-click to reload)
- Refresh history button

#### Tab 4: 帮助 (Help)

Read-only HTML help with usage instructions.

### 9.4 Key GUI Classes

#### `CargoBayWidget`

Custom QWidget that paints the cargo bay schematic.

**Features:**
- Renders cargo bay rectangle with grid lines (2000mm intervals)
- Draws X/Y axis labels and tick marks
- Renders detector positions as colored circles (green=A, blue=B)
- **NEW v5.1:** Renders heatmap overlay: green dots for alarm, red dots for miss
- Centerline dashed marker
- Legend box

**Key Methods:**

| Method | Description |
|--------|-------------|
| `set_layout(detectors, bay_width, bay_length)` | Update detector positions |
| `set_heatmap(data)` | Set heatmap data `{(x,y): alarm_bool}`, triggers repaint |
| `clear_heatmap()` | Remove heatmap overlay |

**Heatmap Rendering (v5.1):**
```python
# After simulation completes:
heatmap = {}
for _, row in df.iterrows():
    loc_str = str(row.get("Src Loc.", ""))
    alarm   = bool(row.get("Alarm", False))
    x, y, _ = parse_src_loc(loc_str)
    if x is not None and (x > 0 or y > 0):
        heatmap[(x, y)] = alarm
bay_wid.set_heatmap(heatmap)
```

#### `DetectorDragWidget`

Composite widget combining `_DetectorCanvas` + detector table + control buttons. Manages the confirm workflow.

**Confirm Workflow (v5.1):**
1. User drags/adds/deletes detectors on canvas
2. User clicks **「确认布放」** (Confirm Layout) → `_confirmed = True`
   - Canvas border turns green (3px solid #27AE60)
   - "确认布放" button disabled
   - "取消确认" button enabled
   - "应用到仿真" button enabled
3. User clicks **「应用到仿真」** (Apply to Simulation)
   - Confirmation dialog lists all detectors
   - Calls `sync_from_drag_widget()` to update simulation parameters
4. User can click **「取消确认」** (Cancel Confirm) to unlock for further edits

**Signals:**
| Signal | Payload | Description |
|--------|---------|-------------|
| `detectors_changed` | `list[(x,y,name,ch),...]` | Emitted when canvas detectors change |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `init_detectors(detectors, w, l)` | Initialize/replace detector list from config |
| `_auto_layout()` | Generate evenly spaced layout across bay center |
| `_confirm_layout()` | Lock current layout (green border) |
| `_cancel_confirm()` | Unlock layout |
| `_apply_to_simulation()` | Sync to main simulation config |
| `get_detectors()` | Returns current detector list |

#### `_DetectorCanvas`

Internal QWidget handling low-level mouse interactions.

**Mouse Interactions:**
| Action | Result |
|--------|--------|
| Left-click on detector | Start drag |
| Left-click on empty bay area | Add new detector (alternates A/B channel) |
| Left-click + drag | Move detector, constrained to bay bounds |
| Left-release | End drag, emit `detectors_changed` |
| Right-click on detector | Context menu: Edit, Delete, Change to A/B channel |
| Mouse move | Hover highlight + coordinate tooltip |

**Context Menu Options:**
- Edit [SDn]: Opens QInputDialog for X and Y coordinates
- Delete [SDn]: Removes detector from list
- 改为 A通道: Sets channel to 0
- 改为 B通道: Sets channel to 1

**Coordinate Tooltip:**
While dragging or hovering, a small yellow box at top-left shows:
```
X=5000.0  Y=2083.0  (mm)
```

#### `DetectorSizeDialog` (v5.1)

Modal dialog for configuring detector physical dimensions.

**UI Layout:**
```
┌─────────────────────────────────────┐
│ 探测器尺寸设置                    [X]│
├──────────────────┬──────────────────┤
│ 长度 L (mm): [140.0] │                  │
│ 宽度  W (mm): [145.0] │  [_SizePreview] │
│ 高度  H (mm): [58.0]  │   (三视图)       │
│                  │                  │
│ 预置尺寸         │                  │
│ [标准型 140×145×58]│                  │
│ [小型  100×100×45] │                  │
│ [大型  180×160×70] │                  │
├──────────────────┴──────────────────┤
│              [OK]  [Cancel]         │
└─────────────────────────────────────┘
```

**Preset Sizes:**
| Preset | L×W×H (mm) |
|--------|------------|
| 标准型 | 140×145×58 |
| 小型 | 100×100×45 |
| 大型 | 180×160×70 |

#### `_SizePreviewWidget`

Custom QWidget painting a three-view schematic of the detector (top view + side view) with dimension annotations.

#### `ConfigLoadThread`

QThread subclass that loads `SimulationConfig.from_json()` asynchronously. Emits `loaded` (cfg, path) on success or `error` (msg) on failure.

#### `SimulationThread`

QThread subclass running `SimulationEngine.run_grid()`. 

**Signals:**
| Signal | Payload | Description |
|--------|---------|-------------|
| `progress` | `int, str` | Percentage (0-100) and status message |
| `finished` | `float, int, int` | Elapsed time (s), failed count, total count |
| `error` | `str` | Error message |
| `detector_inf` | `list[tuple]` | Final detector positions |
| `log_msg` | `str` | Log message for display |

#### `parse_src_loc(s)` (v5.1)

Utility function that parses the "Src Loc." column string from result CSV files.

```python
def parse_src_loc(s: str):
    """Parse 'Src Loc.' column like '(0.0, 1000.0, 0.0)' → (x, y, z)"""
    m = re.findall(r"[-+]?\d+\.?\d*", s)
    if len(m) >= 3:
        return float(m[0]), float(m[1]), float(m[2])
    return None, None, None
```

Handles formats: `(0.0, 1000.0, 0.0)`, `(0, 1000, 0)`, `0.0, 1000.0, 0.0`

### 9.5 Icon System (v5.1)

Icons are loaded from the `icons/` subdirectory using `_get_icon()`:

```python
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def _get_icon(name: str) -> QIcon:
    path = os.path.join(_ICON_DIR, f"icon_{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()   # empty fallback
```

**Available Icons:**

| Icon Name | File | Used For |
|-----------|------|----------|
| `open` | `icon_open.png` | Open config file action + toolbar |
| `save` | `icon_save.png` | Save config action |
| `model` | `icon_model.png` | Load model action |
| `run` | `icon_run.png` | Run simulation button |
| `stop` | `icon_stop.png` | Stop simulation button |
| `chart` | `icon_chart.png` | Show chart button |
| `compare` | `icon_compare.png` | Compare runs button |
| `export` | `icon_export.png` | Export results button |
| `detector` | `icon_detector.png` | Detector size dialog |
| `drag` | `icon_drag.png` | Drag page tab |
| `bay` | `icon_bay.png` | Bay visualization + auto-layout |
| `settings` | `icon_settings.png` | Settings tab + edit context menu |
| `help` | `icon_help.png` | Help menu + about |
| `history` | `icon_history.png` | Reload history button |
| `heatmap` | `icon_heatmap.png` | Heatmap toggle |
| `delete` | `icon_delete.png` | Delete detector button + context menu |
| `alert` | `icon_alert.png` | Alert icon |

### 9.6 matplotlib Chinese Font Configuration (v5.1)

Applied in `_show_chart()` and `_show_compare()`:

```python
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
```

Fallback chain ensures Chinese characters display on both Windows (SimHei, Microsoft YaHei) and cross-platform (Arial Unicode MS) environments.

### 9.7 Config Loading Syncs Drag Page (v5.1)

When a config file is loaded via `_on_config_loaded()`:

```python
def _on_config_loaded(self, cfg, path):
    self.inputs = cfg
    self._sync_ui_from_cfg()       # ① Sync UI parameter controls
    self._refresh_vis_from_ui()    # ② Refresh vis + sync drag page
    self.log.append(f"已加载配置: {path}")
    self.btn_open.setEnabled(True)
    self.btn_run.setEnabled(self.predictor is not None)
    # Auto-switch to drag tab to prompt user confirmation
    self.tabs.setCurrentWidget(self.drag_wid)
    self.log.append("[提示] 请检查探测器定位 Tab，确认布放后再运行仿真")
```

`_refresh_vis_from_ui()` computes detector positions from arrange parameters and calls:
```python
self.drag_wid.init_detectors(dets, w, l)
```

This populates the drag page with auto-computed positions derived from the loaded config's `arrange` method (center/side), so the user can review and optionally modify before running.

---

## 10. Data Dictionary — `inputs.json`

### 10.1 File Location

`/mnt/c/smoke_project/inputs.json`

### 10.2 Schema

```json
{
    "Type": "string",
    "SD_num": "integer (even, ≥2)",
    "bay_dimension": ["float (width_mm)", "float (length_mm)", "float (height_mm)"],
    "criteria": "integer (seconds, >0)",
    "arrange": {
        "method": "string (center|side)",
        "fwd space": "integer (mm, ≥0)",
        "aft space": "integer (mm, ≥0)",
        "displace": "integer (mm, ≥0)"
    }
}
```

### 10.3 Field Definitions

| Field | JSON Path | Type | Units | Valid Range | Default | Description |
|-------|-----------|------|-------|-------------|---------|-------------|
| Type | `Type` | string | — | Any | — | Aircraft type name (display only) |
| SD_num | `SD_num` | integer | — | even, ≥2 | — | Total smoke detector count (must be even for dual-channel) |
| bay_dimension[0] | `bay_dimension[0]` | float | mm | >0 | — | Cargo bay width (Y axis, spanwise) |
| bay_dimension[1] | `bay_dimension[1]` | float | mm | >0 | — | Cargo bay length (X axis, fore-aft) |
| bay_dimension[2] | `bay_dimension[2]` | float | mm | >0 | — | Cargo bay height (Z axis, vertical) |
| criteria | `criteria` | integer | seconds | >0 | — | Alarm time threshold; if any channel detector alarms within this time, channel is satisfied |
| arrange.method | `arrange.method` | string | — | "center" or "side" | "center" | Arrangement algorithm |
| arrange.fwd space | `arrange.fwd space` | integer | mm | ≥0 | 0 | Distance from forward wall to first detector |
| arrange.aft space | `arrange.aft space` | integer | mm | ≥0 | 0 | Distance from aft wall to last detector |
| arrange.displace | `arrange.displace` | integer | mm | ≥0 | 100 | Offset of each channel pair from bay centerline |

### 10.4 Arrangement Methods

#### "center" Arrangement

- Detectors are grouped in pairs (SD1+SD2, SD3+SD4, ...)
- Each pair shares the same X coordinate
- Channel-A (odd IDs) is offset +displace above centerline
- Channel-B (even IDs) is offset -displace below centerline

#### "side" Arrangement

- All Channel-A detectors are in a row at Y = width/2 + displace
- All Channel-B detectors are in a row at Y = width/2 - displace
- X spacing is uniform across all N detectors

### 10.5 Example `inputs.json` (CR929 Configuration)

```json
{
    "Type": "CR929-base",
    "SD_num": 10,
    "bay_dimension": [
        4166,
        16184,
        1727.6
    ],
    "criteria": 60,
    "arrange": {
        "method": "center",
        "fwd space": 100,
        "aft space": 100,
        "displace": 100
    }
}
```

**Derived Values:**
- 10 detectors → 5 pairs, 5 Channel-A + 5 Channel-B
- Grid: X: 0 to 16184 in 1000mm steps = 18 points; Y: 0 to 4166 in 1000mm steps = 5 points
- Total simulation points: 18 × 5 = 90

---

## 11. Configuration Guide

### 11.1 Typical Workflow

```
1. Launch application
   python gui_pyside6_winstyle.py

2. Load configuration
   File → 打开配置... (Ctrl+O)
   Select inputs.json

   Application automatically:
   - Parses JSON into SimulationConfig
   - Populates all parameter controls
   - Computes auto-detector positions
   - Syncs Detector Drag tab with computed positions
   - Switches to 探测器定位 tab for user review

3. Review detector layout (探测器定位 tab)
   - Verify detector positions visually
   - Drag to adjust individual positions
   - Or click 自动均匀布局 for auto-computed evenly-spaced layout
   - Click 确认布放 to lock
   - Click 应用到仿真 to apply to simulation

4. Load ML model
   File → 加载模型...
   Select rf_model_all.model

5. Run simulation
   Click 运行 (Run) on toolbar

   Progress bar updates in real-time
   Log shows per-detector positions and test count

6. Review results
   - Heatmap overlay appears on cargo bay visualization
   - Results table populated in 结果 tab
   - Click 图表 for matplotlib alarm analysis

7. Compare runs (optional)
   Click 对比 to compare any two historical runs
```

### 11.2 Detector Size Configuration

```
File → 探测器尺寸...
```

Opens `DetectorSizeDialog`. Configure L/W/H and click OK. The values are stored in `SimulationConfig.sd_length_mm` and `sd_width_mm` and affect arrangement calculations.

### 11.3 Output Directory

Configure in 设置 tab. Default is `.` (application directory). All result CSV files are written here with timestamp names.

---

## 12. Build & Deployment

### 12.1 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.10+ | Runtime |
| PySide6 | ≥6.5 | GUI framework |
| scikit-learn | ≥1.0 | ML model loading (with compat layer) |
| pandas | ≥2.0 | DataFrame results |
| numpy | ≥1.24 | Array operations |
| matplotlib | ≥3.7 | Charts |
| pickle | (built-in) | Model serialization |

### 12.2 Running the Application

```bash
cd /mnt/c/smoke_project
python gui_pyside6_winstyle.py
```

### 12.3 WSLg Notes (Windows + WSL2)

For HiDPI displays, set before launch:
```bash
export QT_SCALE_FACTOR=2
export QT_SCALE_FACTOR_ROUNDING_POLICY=Passthrough
python gui_pyside6_winstyle.py
```

### 12.4 Running Headless (No GUI)

```python
from simulation_config import SimulationConfig
from simulation import SimulationEngine
from sklearn_compat import load_model
from result_manager import ResultManager

cfg = SimulationConfig.from_json('inputs.json')
predictor = load_model('rf_model_all.model')
rm = ResultManager(output_dir='.')

eng = SimulationEngine(cfg, predictor, result_manager=rm)
results = eng.run_grid()  # No GUI needed
```

---

## 13. Changelog

### v5.1 — 2026-04-18

#### New Features

**Heatmap Visualization (`CargoBayWidget`)**
- After simulation completes, the cargo bay widget overlays a color-coded heatmap showing alarm (green) vs. miss (red) for each grid point
- Uses `parse_src_loc()` to extract X/Y coordinates from the "Src Loc." CSV column string (format: `(x, y, z)`)
- Heatmap dots (10px diameter) are drawn at each grid point's (x, y) position
- Legend in the bottom-right corner updates to show alarm/miss color key
- `set_heatmap(data)` and `clear_heatmap()` methods on `CargoBayWidget`
- Also rendered when loading historical results via double-click in history table

**Detector Drag-Positioning with Confirm Workflow (`DetectorDragWidget`)**
- New "探测器定位" tab with interactive drag-and-drop canvas
- Left-click on empty bay area adds a new detector (alternates A/B channel)
- Left-click + drag moves existing detectors (constrained to bay bounds)
- Right-click opens context menu: Edit coordinates, Delete, Change to A/B channel
- Double-click table row opens coordinate input dialog
- **Confirm workflow:** Click "确认布放" → green border indicates locked layout → "应用到仿真" syncs to simulation parameters
- "取消确认" unlocks layout for further editing
- Channel filter dropdown (全部/仅A通道/仅B通道)
- "自动均匀布局" button generates evenly-spaced layout

**Detector Size Dialog (`DetectorSizeDialog`, v5.1)**
- New modal dialog: File → 探测器尺寸...
- Configure detector Length/Width/Height in mm
- Three preset buttons: 标准型 (140×145×58), 小型 (100×100×45), 大型 (180×160×70)
- Live three-view preview widget showing top view + side view with dimension annotations
- Saved to `SimulationConfig.sd_length_mm`, `sd_width_mm` fields

**matplotlib Chinese Font Fix (`_show_chart`, `_show_compare`)**
- Added `Arial Unicode MS` as final fallback in font fallback chain
- Full chain: `['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']`
- Applied before all `plt.rcParams` usages

**Icon System (`_get_icon`)**
- Consolidated icon loading from `icons/` directory
- All toolbar buttons, menu items, and context menu actions use themed icons
- 17 icons total: open, save, model, run, stop, chart, compare, export, detector, drag, bay, settings, help, history, heatmap, delete, alert
- Falls back to QIcon() if file not found

**Config Loading Syncs Drag Page (`_on_config_loaded` → `_refresh_vis_from_ui`)**
- Loading an inputs.json now automatically populates the 探测器定位 tab with computed detector positions
- `SimulationConfig._custom_detectors` is set when user clicks "应用到仿真"
- `sync_from_drag_widget()` updates sp_sdnum, sp_width, sp_len, bay_wid layout

#### Bug Fixes
- `parse_src_loc()` correctly handles floats and integers: `(0.0, 1000.0, 0.0)` and `(0, 1000, 0)`
- `BayConfig` validation raises on width_mm/length_mm/height_mm ≤ 0
- `SimulationConfig.validate()` correctly checks `fwd + aft < bay length`

---

### v5.0 — 2026-04-18 (Major Refactor)

#### Architecture Refactoring
- **New `sklearn_compat.py`**: sklearn legacy model compatibility layer, GUI no longer has inline compat code
- **New `simulation_config.py`**: Typed configuration objects with full validation, eliminates bay_dimension[0/1/2] positional ambiguity
- **New `result_manager.py`**: Versioned result management; each run generates a timestamped CSV (`result_YYYYMMDD_HHMMSS.csv`), never overwrites old results
- **New `simulation.py`**: Core `SimulationEngine` completely decoupled from GUI, supports headless unit testing

#### Code Quality
- Type hints added throughout Detector / CargoBay / SimulationConfig
- `alarm_time` annotated as `np.ndarray`
- `Detector.__repr__` added
- `CargoBay` now has `volume_mm3` property and `__repr__`
- Configuration validation in `SimulationConfig.validate()`
- Fixed progress calculation bug: `floor(len/1000)*floor(width/1000)` instead of ceil

#### Deprecated Files
- `gui_pyside6_v3.py` (1014 lines) — deleted
- `gui.py` (6296 lines) — deleted
- `Environment.py` — file retained but marked deprecated (replaced by `simulation.py`)

---

*Document prepared: 2026-04-18 | smoke_project v5.1*
