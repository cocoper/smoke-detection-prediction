# Smoke Detection Simulation System — Development Documentation

**Document Number:** SDSS-SW-001  
**Version:** 3.1  
**Date:** 2026-04-06  
**Classification:** Internal — Technical Reference

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Module Specification — `Detector.py`](#3-module-specification--detectorpy)
4. [Module Specification — `cargobay.py`](#4-module-specification--cargobaypy)
5. [Module Specification — `Environment.py`](#5-module-specification--environmentpy)
6. [Module Specification — `gui_pyside6_winstyle.py`](#6-module-specification--gui_pyside6_winstylepy)
7. [Data Dictionary — `inputs.json`](#7-data-dictionary--inputsjson)
8. [Configuration Guide](#8-configuration-guide)
9. [Build & Deployment](#9-build--deployment)
10. [Changelog](#10-changelog)

---

## 1. Overview

### 1.1 Purpose

The Smoke Detection Simulation System (SDSS) is a desktop application that simulates smoke diffusion within aircraft cargo bays and predicts smoke detector response times using a pre-trained machine learning model. It is designed to support aircraft fire-protection system design and certification activities.

### 1.2 Scope

| Item | Description |
|------|-----------|
| **Type** | Desktop simulation tool |
| **Language** | Python 3.10+ |
| **GUI Framework** | PySide6 (Qt for Python) |
| **ML Backend** | scikit-learn (RandomForestRegressor, DecisionTreeRegressor) |
| **Target Platform** | Windows (WSL2 with WSLg), Linux |
| **Output** | CSV result log, matplotlib charts |

### 1.3 Key Capabilities

- Simulate smoke diffusion across a configurable cargo bay grid
- Predict detector alarm times using a trained ML model
- AND-logic dual-channel detection (Channel-A and Channel-B)
- Visualize cargo bay layout and detector placement
- Real-time progress tracking with stop/abort support
- Export simulation results to CSV

---

## 2. System Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Application                         │
│              gui_pyside6_winstyle.py                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Tool Bar    │  │  TabWidget   │  │   Status Bar     │  │
│  │  (Controls)  │  │  (Pages)     │  │  (Run Status)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                   │                               │
│         └──────────┬────────┘                               │
│                    ▼                                        │
│         ┌─────────────────────┐                            │
│         │  SimulationThread   │  (QThread, async)          │
│         └──────────┬──────────┘                            │
│                    │                                        │
└───────────────│───────────────────────────────│─────────────┘
                ▼
┌───────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Environment │  │  CargoBay   │  │    Detector       │  │
│  │  (Simulator) │  │  (Bay Model)│  │   (Sensor Model) │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│                 ┌─────────────────┐                         │
│                 │  ML Predictor   │  (LegacyModelWrapper)  │
│                 │  (sklearn)      │                         │
│                 └─────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
inputs.json ──► Environment ──► Detector × N
                              │
                              ├──► CargoBay.isinbay()
                              │         │
                              │         ▼
                              │    smoke_grid (movesrc iterator)
                              │
                              ├──► Detector.alarm(src_pos)
                              │         │
                              │         ▼
                              │    predictor.predict(distance)
                              │
                              ▼
                         det_logic() ──► Alarm (True/False)
                              │
                              ▼
                    test_result.csv
```

---

## 3. Module Specification — `Detector.py`

### 3.1 Class: `Detector`

Represents a single smoke detector in the cargo bay.

#### Constructor

```python
class Detector(object):
    def __init__(self,
                 predictor='None',
                 x_pos=0, y_pos=0, z_pos=0,
                 dimension=(140, 145),
                 threshold=None,
                 SD_id=1,
                 name='SD',
                 channel_id=1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `predictor` | object | `'None'` | ML model instance with `.predict()` method. Pass `'None'` (string) to disable prediction. |
| `x_pos` | float | `0` | Detector position along cargo bay length axis (mm). |
| `y_pos` | float | `0` | Detector position along cargo bay width axis (mm). |
| `z_pos` | float | `0` | Detector position along cargo bay height axis (mm). |
| `dimension` | tuple | `(140, 145)` | Detector physical dimensions (length, width) in mm. |
| `threshold` | float | `None` | Optional alarm threshold override. |
| `SD_id` | int | `1` | Sequential detector identifier (1-based). |
| `name` | str | `'SD'` | Display name prefix (e.g., `'SD1'`). |
| `channel_id` | int | `1` | Channel assignment: `0` = Channel-A, `1` = Channel-B. |

#### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `x_pos` | float | Current X position in mm. |
| `y_pos` | float | Current Y position in mm. |
| `z_pos` | float | Current Z position in mm. |
| `dimension` | tuple | Detector dimensions (length, width) in mm. |
| `threshold` | float | Alarm threshold value. |
| `SD_id` | int | Detector ID. |
| `name` | str | Detector name string. |
| `channel_id` | int | Channel: `0` (A) or `1` (B). |
| `alarm_time` | ndarray | Last predicted alarm time from ML model. |
| `dis` | float | Last computed Euclidean distance from smoke source. |

#### Methods

##### `set_pos(x_pos, y_pos, z_pos)`

Sets the detector's 3D position.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x_pos` | float | X coordinate (mm). |
| `y_pos` | float | Y coordinate (mm). |
| `z_pos` | float | Z coordinate (mm). |

##### `get_pos() → tuple`

Returns the current 3D position as `(x_pos, y_pos, z_pos)`.

##### `get_dimension() → tuple`

Returns detector physical dimensions `(length, width)` in mm.

##### `set_threshold(threshold)`

Sets the alarm threshold. Does not return a value.

##### `get_threshold() → float`

Returns the current alarm threshold.

##### `set_channel_id(channel_id)`

Sets the channel assignment.

| Parameter | Type | Description |
|-----------|------|-------------|
| `channel_id` | int | `0` for Channel-A, `1` for Channel-B. |

##### `alarm(src_pos)`

Computes the Euclidean distance from `src_pos` to the detector position and invokes the ML predictor to obtain an alarm time.

| Parameter | Type | Description |
|-----------|------|-------------|
| `src_pos` | tuple/list | Smoke source position as `(x, y, z)`. |

> **Distance calculation:** `sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)`  
> **Prediction input:** `dis / 10` (distance in cm passed to model)

##### `__cal_distance(pos1, pos2) → float` *(private)*

Euclidean distance between two 3D points. Returns distance in mm.

---

## 4. Module Specification — `cargobay.py`

### 4.1 Class: `CargoBay`

Represents the physical cargo bay volume.

#### Constructor

```python
class CargoBay(object):
    def __init__(self, width=1000, length=5000, height=5000)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `width` | float | `1000` | Cargo bay width (Y-axis) in mm. Must be > 0. |
| `length` | float | `5000` | Cargo bay length (X-axis) in mm. Must be > 0. |
| `height` | float | `5000` | Cargo bay height (Z-axis) in mm. Must be > 0. |

> **Raises:** `AssertionError` if any dimension is not positive.

#### Methods

##### `get_dimension() → tuple`

Returns bay dimensions as `(width, length, height)` in mm.

##### `set_dimension(width=0, length=0, height=0)`

Sets bay dimensions without validation.

##### `set_prop(cargo_prop)`

Sets all dimensions from a dictionary.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cargo_prop` | dict | Dict with keys: `'width'`, `'length'`, `'height'`. |

##### `isinbay(pos) → bool`

Tests whether a 2D point is within the cargo bay floor plan.

| Parameter | Type | Description |
|-----------|------|-------------|
| `pos` | list/tuple | Position as `(x, y)`. |

| Return | Description |
|--------|-------------|
| `True` | Point is within length and width bounds. |
| `False` | Point is outside bounds. |

> **Logic:** `pos[0] < length AND pos[1] < width`

---

## 5. Module Specification — `Environment.py`

### 5.1 Class: `Environment`

Manages the simulation lifecycle: detector arrangement, smoke source traversal, alarm logic, and result logging.

#### Constructor

```python
class Environment(cargobay_obj, detector_series,
                   detector_qty, arrange, time_criteria=60)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `cargobay_obj` | `CargoBay` | Cargo bay model instance. |
| `detector_series` | list[Detector] | List of `Detector` instances. |
| `detector_qty` | int | Number of detectors. Must be even. |
| `arrange` | dict | Arrangement parameters (see below). |
| `time_criteria` | int | Alarm time threshold in seconds. Default: `60`. |

**`arrange` dict schema:**

| Key | Type | Description |
|-----|------|-------------|
| `method` | str | Arrangement method: `"center"` or `"side"`. |
| `fwd space` | int | Distance from front wall to first detector (mm). |
| `aft space` | int | Distance from rear wall to last detector (mm). |
| `displace` | int | Centerline offset for side-by-side channels (mm). |

#### Instance Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `detectors` | list[Detector] | All detector instances. |
| `CHA_SD` | list[Detector] | Channel-A detectors (odd SD_id). |
| `CHB_SD` | list[Detector] | Channel-B detectors (even SD_id). |
| `bay_dim` | dict | Bay dimensions: `{'width', 'length', 'height'}`. |
| `crit` | int | Alarm time threshold in seconds. |
| `sys_arrange` | dict | Active arrangement parameters. |
| `log` | dict | Current test record (updated each iteration). |
| `_progress_callback` | callable | Called each iteration with `(current, total, msg)`. |
| `_stop_flag` | callable | Must return `True` to abort simulation. |

#### Methods

##### `arrange(arrange_method='center', fwd_space=0, aft_space=0, displace=100)`

Places detectors in the cargo bay according to the specified layout algorithm.

| Parameter | Type | Description |
|-----------|------|-------------|
| `arrange_method` | str | `"center"` or `"side"`. |
| `fwd_space` | int | Forward wall spacing (mm). |
| `aft_space` | int | Aft wall spacing (mm). |
| `displace` | int | Centerline offset (mm). |

**Center Arrangement (`"center"`):**
- Detectors are grouped in pairs (Channel-A, Channel-B share the same X position).
- Channel-A is offset above the centerline by `displace + SD_dim[1]/2`.
- Channel-B is offset below the centerline by `displace + SD_dim[1]/2`.
- Evenly distributed along the X-axis.

**Side Arrangement (`"side"`):**
- All Channel-A detectors are on the upper side; all Channel-B on the lower side.
- Both channels share the same X positions.
- Each channel has its own Y offset from centerline.

##### `set_source(x_pos, y_pos)`

Sets the smoke source position if within bay bounds.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x_pos` | float | X coordinate (mm). |
| `y_pos` | float | Y coordinate (mm). |

##### `run(mode='singal')`

Executes the simulation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | str | `"singal"` — single position test. `"all"` — full grid scan. |

**Mode `"all"` algorithm:**

1. Creates a grid iterator via `movesrc(1000, 1000)` (10mm step in X and Y).
2. For each grid point:
   - Sets smoke source position.
   - Calls `detector.alarm(src_pos)` for each detector.
   - Evaluates `det_logic(CHA_SD, CHB_SD, mode='AND')`.
   - Writes result to `test_result.csv`.
   - Calls `_progress_callback(current, total, msg)`.
   - Checks `_stop_flag()` — aborts if `True`.
3. On `StopIteration`: closes CSV, reports final count.

**Output file:** `test_result.csv` (written to current working directory).

##### `det_logic(signal_CHA, signal_CHB, mode='AND') → bool`

Applies dual-channel alarm logic.

| Parameter | Type | Description |
|-----------|------|-------------|
| `signal_CHA` | list[Detector] | Channel-A detectors. |
| `signal_CHB` | list[Detector] | Channel-B detectors. |
| `mode` | str | `"AND"` (default): both channels must alarm. `"OR"`: either channel alarms. |

**Return:** `True` if alarm condition is met.

##### `movesrc(step_x, step_y, initial_pos=(0, 0, 0)) → Generator`

Generator that yields smoke source positions on a rectangular grid.

| Parameter | Type | Description |
|-----------|------|-------------|
| `step_x` | int | Grid step along X-axis (mm). |
| `step_y` | int | Grid step along Y-axis (mm). |
| `initial_pos` | tuple | Starting position. |

> **Traversal order:** Scans along Y first (inner loop), then X (outer loop).  
> Yields `(x, y)` tuples. Raises `StopIteration` with `e.value = 'Smoke Source moving finished'` when complete.

##### `alarm2binary(crit, det_series) → list[bool]`

Converts detector alarm times to a boolean alarm status list.

| Parameter | Type | Description |
|-----------|------|-------------|
| `crit` | int/float | Alarm threshold in seconds. |
| `det_series` | list[Detector] | List of detectors. |

**Return:** `[True if detector.alarm_time[0] <= crit else False for detector in det_series]`

##### `output()`

Prints the last detector states to stdout (for debugging).

---

## 6. Module Specification — `gui_pyside6_winstyle.py`

### 6.1 Overview

The GUI module implements the desktop user interface using PySide6. It follows a Model-View-Controller pattern with a separate `SimulationThread` for background computation.

### 6.2 Class: `LegacyModelWrapper`

Wraps legacy sklearn models for compatibility with newer scikit-learn versions.

#### Constructor

```python
class LegacyModelWrapper(model)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | object | Raw unpickled sklearn model. |

#### Methods

##### `predict(X) → ndarray`

Wrapper around the underlying model's predict method. Handles input reshaping and aggregation for ensemble models.

### 6.3 Class: `_CompatUnpickler`

Custom pickle unpickler that redirects old module paths to new ones.

| Old Module | New Module |
|-----------|-----------|
| `sklearn.ensemble.forest` | `sklearn.ensemble._forest` |
| `sklearn.tree.tree` | `sklearn.tree` |

### 6.4 Class: `SimulationThread`

Asynchronous simulation runner (inherits `QThread`).

#### Signals

| Signal | Signature | Description |
|--------|-----------|-------------|
| `progress` | `Signal(int, str)` | Emits `(percentage, message)` during simulation. |
| `finished` | `Signal(float, int, int)` | Emits `(elapsed_seconds, failed_count, total_count)` on completion. |
| `error` | `Signal(str)` | Emits error message string on failure. |
| `detector_info` | `Signal(list)` | Emits list of `(x, y, name, channel_id)` tuples for visualization. |

#### Methods

##### `run()`

Thread entry point. Instantiates `Environment`, executes `env.run(mode='all')`, reads result CSV, and emits signals.

##### `stop()`

Sets the internal stop flag. The simulation checks `_stop_flag()` each iteration and exits cleanly when `True`.

### 6.5 Class: `CargoBayWidget`

Custom Qt widget that renders the cargo bay layout using `QPainter`.

#### Methods

##### `set_layout(detectors, bay_width, bay_length)`

Updates the visualization data and triggers a repaint.

| Parameter | Type | Description |
|-----------|------|-------------|
| `detectors` | list | List of `(x, y, name, channel_id)` tuples. |
| `bay_width` | float | Bay width in mm. |
| `bay_length` | float | Bay length in mm. |

##### `paintEvent(event)` *(override)*

Renders:
- Cargo bay outline (blue border, dark fill)
- Grid lines every 2000mm
- Centerline (dashed)
- Detector dots (green = Channel-A, blue = Channel-B)
- Labels and legend

### 6.6 Class: `MainWindow`

Main application window.

#### UI Structure

```
QMainWindow
├── QToolBar ("Main")
│   ├── [Open Config] [ | ] [Run] [Stop] [ | ] [Chart] [Export]
├── QTabWidget
│   ├── Tab 0: Simulation  (QHBoxLayout: Config | Visualization | Status)
│   ├── Tab 1: Results     (QTableWidget)
│   ├── Tab 2: Settings    (QScrollArea with QGroupBox panels)
│   └── Tab 3: Help        (QTextEdit + About group)
└── QStatusBar
    └── [Status Label]
```

#### Key Methods

| Method | Description |
|--------|-------------|
| `_open_config()` | Opens file dialog for `inputs.json`. Parses and syncs Settings tab. |
| `_open_model()` | Opens file dialog for `.model` file. Calls `load_model()`. |
| `_update_vis()` | Re-renders cargo bay layout from current config. |
| `_apply_settings()` | Writes Settings tab values back to the active `inputs` dict. |
| `_run_simulation()` | Launches `SimulationThread`. Disables Run, enables Stop. |
| `_stop_simulation()` | Calls `sim_thread.stop()`. Sets status to "Stopping...". |
| `_on_finished(...)` | Reads CSV, populates result table, switches to Results tab. |
| `_show_chart()` | Opens matplotlib dialog with alarm time histogram and summary bar chart. |
| `_export_results()` | Saves `sim_results` DataFrame to user-selected CSV path. |

### 6.7 Icon Factory Functions

All icons are generated programmatically using `QPainter` on a 24×24 `QPixmap`.

| Function | Visual | Color |
|---------|--------|-------|
| `_icon_open` | Open folder | `#ffcc80` |
| `_icon_play` | Triangle | `#10b010` |
| `_icon_stop` | Square | `#e01010` |
| `_icon_chart` | Bar chart | `#a0d0ff` |
| `_icon_export` | Download box | `#a0d0ff` |
| `_icon_config` | Gear | `#80bfff` |
| `_icon_clear` | X mark | `#888888` |

---

## 7. Data Dictionary — `inputs.json`

### 7.1 Schema

```json
{
  "Type": "string",
  "SD_num": "integer (even)",
  "bay_dimension": ["float (width)", "float (length)", "float (height)"],
  "criteria": "integer (seconds)",
  "arrange": {
    "method": "string (center | side)",
    "fwd space": "integer (mm)",
    "aft space": "integer (mm)",
    "displace": "integer (mm)"
  }
}
```

### 7.2 Field Specifications

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `Type` | string | — | Aircraft type/model designation. Display only. |
| `SD_num` | integer | Even, 2–20 | Total number of smoke detectors. |
| `bay_dimension[0]` | float | > 0, mm | Cargo bay width (Y-axis). |
| `bay_dimension[1]` | float | > 0, mm | Cargo bay length (X-axis). |
| `bay_dimension[2]` | float | > 0, mm | Cargo bay height (Z-axis). |
| `criteria` | integer | > 0, seconds | Alarm time threshold for detection logic. |
| `arrange.method` | string | `"center"` or `"side"` | Detector arrangement algorithm. |
| `arrange.fwd space` | integer | ≥ 0, mm | Distance from front bulkhead to first detector. |
| `arrange.aft space` | integer | ≥ 0, mm | Distance from rear bulkhead to last detector. |
| `arrange.displace` | integer | ≥ 0, mm | Offset of Channel-B from cargo bay centerline. |

### 7.3 Example

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

## 8. Configuration Guide

### 8.1 Runtime Environment Variables

| Variable | Values | Default | Effect |
|---------|--------|---------|--------|
| `QT_ENABLE_HIGHDPI_SCALING` | `1` / `0` | `1` | Enables Qt high-DPI scaling. |
| `QT_AUTO_SCREEN_SCALE_FACTOR` | `1` / `0` | `1` | Auto-detect display DPI. |
| `QT_SCALE_FACTOR` | `1`, `2` | `2` | Fixed scale factor for WSLg. |
| `QT_SCALE_FACTOR_ROUNDING_POLICY` | `Passthrough` | `Passthrough` | Rounding mode for fractional scales. |

> **Note:** For standard Windows desktops (non-WSL), remove or set `QT_SCALE_FACTOR=1`.

### 8.2 Dependencies

```
PySide6>=6.5
pandas>=2.0
numpy>=1.24
scikit-learn>=1.3
matplotlib>=3.7  (optional, for charts)
```

Install all at once:
```bash
pip install PySide6 pandas numpy scikit-learn matplotlib
```

### 8.3 Running the Application

```bash
cd ~/smoke_project
python gui_pyside6_winstyle.py
```

### 8.4 Preparing the ML Model

The `.model` file must contain a pickled scikit-learn regressor trained on two features:
- Feature 0: Euclidean distance from smoke source to detector (cm)
- Feature 1: Detector channel ID (`0` or `1`)

Target: Alarm time in seconds.

---

## 9. Build & Deployment

### 9.1 Packaging

To create a standalone executable:

```bash
pip install pyinstaller
pyinstaller --one-window --noconsole \
  --add-data "Detector.py;." \
  --add-data "cargobay.py;." \
  --add-data "Environment.py;." \
  gui_pyside6_winstyle.py
```

### 9.2 Known Compatibility Notes

| Issue | Cause | Solution |
|-------|-------|----------|
| Model fails to load | sklearn version mismatch | Use `LegacyModelWrapper` with `_CompatUnpickler` |
| Chinese font missing in chart | Font not installed in WSL | Install `fonts-noto-cjk` or use `Noto Sans CJK SC` |
| Progress bar stays at 0% | Grid size not pre-calculated | Pass pre-computed `total_tests` to callback |
| WSLg GUI does not launch | Display not configured | Ensure `DISPLAY` env var is set; use WSLg |

---

## 10. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 3.1 | 2026-04-06 | Font replacement (Noto Sans CJK SC); High-DPI scaling; matplotlib Chinese fix |
| 3.0 | 2026-04-05 | CargoBay height fix; Z-axis distance; sklearn compatibility; progress bar; cargo bay visualization |
| 2.x | 2026-04-xx | Earlier releases (see git history) |

---

*End of Document — SDSS-SW-001*
