# 飞机货舱烟雾检测仿真系统 — 开发技术文档

**文档编号：** SDSS-SW-001  
**版本：** 5.1  
**日期：** 2026-04-18  
**分类：** 内部 — 技术参考资料

---

## 目录

1. [系统概述](#1-系统概述)
2. [系统架构](#2-系统架构)
3. [模块说明—sklearn_compatpy](#3-模块说明sklearn_compatpy)
4. [模块说明—simulation_configpy](#4-模块说明simulation_configpy)
5. [模块说明—result_managerpy](#5-模块说明result_managerpy)
6. [模块说明—simulationpy](#6-模块说明simulationpy)
7. [模块说明—detectorpy](#7-模块说明detectorpy)
8. [模块说明—cargobaypy](#8-模块说明cargobaypy)
9. [模块说明—gui_pyside6_winstylepy](#9-模块说明gui_pyside6_winstylepy)
10. [数据字典—inputsjson](#10-数据字典inputsjson)
11. [配置指南](#11-配置指南)
12. [构建与部署](#12-构建与部署)
13. [更新日志](#13-更新日志)

---

## 1. 系统概述

### 1.1 目的

飞机货舱烟雾检测仿真系统（Smoke Detection Simulation System，简称 SDSS）是一款桌面应用程序，用于模拟飞机货舱内烟雾扩散过程，并基于预训练的机器学习模型预测烟雾探测器的报警响应时间。系统服务于飞机防火保护系统的设计与适航认证工作。

### 1.2 适用范围

| 项目 | 说明 |
|------|------|
| **类型** | 桌面仿真工具 |
| **语言** | Python 3.10+ |
| **GUI 框架** | PySide6（Qt for Python） |
| **ML 后端** | scikit-learn（RandomForestRegressor、DecisionTreeRegressor） |
| **目标平台** | Windows（WSL2 + WSLg）、Linux |
| **输出** | 带时间戳的 CSV 结果文件、matplotlib 图表 |

### 1.3 核心功能

- 仿真烟雾在可配置货舱网格上的扩散行为（步长 1000mm）
- 使用已训练的 ML 模型预测探测器报警时间
- 双通道 AND 逻辑检测（Channel-A 与 Channel-B 必须同时报警）
- 货舱布局可视化（探测器位置实时显示）
- **v5.1 新增：** 热力图叠加显示每个网格点的报警/漏检状态
- **v5.1 新增：** 交互式拖拽探测器定位功能（含确认工作流）
- **v5.1 新增：** 探测器尺寸配置对话框（含实时三视图预览）
- **v5.1 新增：** 配置文件加载时自动同步拖拽页面探测器列表
- 版本化管理仿真结果（时间戳 CSV，不覆盖旧结果）
- 多轮仿真结果对比分析
- matplotlib 图表：报警时间直方图、报警率饼图、多轮对比柱状图

### 1.4 项目结构

```
smoke_project/
├── main.py                          # 命令行入口（旧版）
├── gui_pyside6_winstyle.py          # GUI 主程序（主启动器）
├── Detector.py                       # 烟雾探测器模型
├── cargobay.py                      # 货舱几何模型
├── Environment.py                   # 旧版环境模型（已废弃）
├── simulation.py                    # 仿真核心引擎
├── simulation_config.py             # 类型化配置对象
├── result_manager.py                # 版本化结果管理
├── sklearn_compat.py                 # 旧版 sklearn 模型兼容层
├── inputs.json                      # 配置文件
├── rf_model.model                   # 已训练的 ML 模型（pickle 格式）
├── rf_model_all.model               # 完整功能 ML 模型
├── rf_model_all_verbose1.model      # verbose 变体模型
├── icons/                           # GUI 图标资源
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
    ├── development-documentation.zh.md  # 本文档（中文版）
    └── development-documentation.md     # 英文原版
```

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     GUI 层（PySide6）                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  MainWindow  │  │DetectorDrag  │  │ DetectorSizeDialog   │   │
│  │ (Tab页+工具栏) │  │   Widget     │  │  (_SizePreviewWidget)│   │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘   │
│         │                 │                                     │
│  ┌──────▼─────────────────▼────────────────────────────────┐    │
│  │              CargoBayWidget（热力图+探测器渲染）          │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────┐
         │                 │                  │
         ▼                 ▼                  ▼
┌─────────────────┐  ┌───────────────┐  ┌─────────────────────┐
│ SimulationConfig │  │SimulationEngine│  │    ResultManager    │
│   （类型化配置）  │  │   （核心引擎）  │  │   （版本化输出）     │
└────────┬────────┘  └───────┬───────┘  └─────────────────────┘
         │                    │
         │         ┌──────────┴──────────┐
         │         │                      │
         ▼         ▼                      ▼
┌─────────────────┐  ┌────────────┐  ┌─────────────────────────┐
│   inputs.json   │  │  Detector   │  │      CargoBay           │
│   （JSON 配置）  │  │  （SD 模型） │  │      （几何模型）        │
└─────────────────┘  └─────┬──────┘  └─────────────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │   ML 预测器      │
                    │ （sklearn 模型） │
                    └─────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 |
|------|------|
| `MainWindow` | 基于 Tab 页的 GUI、工具栏、菜单栏、仿真流程编排 |
| `CargoBayWidget` | 货舱 2D 画布，含热力图叠加与探测器渲染 |
| `DetectorDragWidget` | 拖拽式探测器布局编辑器，含列表与画布联动 |
| `_DetectorCanvas` | 底层鼠标事件处理（探测器拖拽/添加/删除） |
| `DetectorSizeDialog` | 探测器尺寸配置模态对话框 |
| `_SizePreviewWidget` | 探测器三视图预览（俯视图/侧视图/等轴测） |
| `SimulationEngine` | 网格扫描循环、报警逻辑、烟雾源迭代、结果收集 |
| `SimulationConfig` | 类型安全的 inputs.json 配置，构造时即校验 |
| `ResultManager` | 时间戳 CSV 输出、元信息记录、运行历史列表 |
| `Detector` | 3D 欧几里得距离计算、调用 ML 预测报警时间 |
| `CargoBay` | 货舱几何尺寸（宽/长/高）、边界校验 |
| `sklearn_compat` | 旧版 pickle 模型加载、`missing_go_to_left` 字段补丁 |

### 2.3 数据流

```
1. 用户加载 inputs.json  →  SimulationConfig.from_json()
   └── SimulationConfig 校验并存储 bay/detector/arrange 参数

2. 用户加载 .model 文件  →  load_model() 来自 sklearn_compat
   └── 返回带有 .predict() 接口的 LegacyModelWrapper

3. 用户自定义探测器（可选）
   a) 通过 DetectorDragWidget：拖拽/添加/删除画布上的探测器 → (x,y,name,ch) 列表
   b) 通过 DetectorSizeDialog：设置 L/W/H 尺寸
   c) 点击「确认布放」→「应用到仿真」（锁定布局并同步参数）

4. 用户点击「运行」
   a) MainWindow._run() 构造 SimulationConfig
   b) cfg._custom_detectors = drag_wid.get_detectors()（如有自定义）
   c) SimulationThread 启动，创建 SimulationEngine
   d) Engine 通过 _movesrc() 生成器遍历烟雾源网格
   e) 每个网格点：所有探测器调用 alarm(src_pos)
   f) det_logic() 评估 Channel-A 与 Channel-B 的 AND 关系
   g) ResultManager.append_row() 写入时间戳 CSV

5. 仿真完成
   a) MainWindow._on_done() 通过 ResultManager 加载最新 CSV
   b) parse_src_loc() 解析 "Src Loc." 列字符串 → (x, y, z)
   c) 构建 heatmap 字典 {(x,y): alarm_bool} 并传给 CargoBayWidget
   d) CargoBayWidget 在货舱示意图上渲染彩色点
   e) 结果 Tab 显示完整 DataFrame；支持图表/对比/导出
```

### 2.4 坐标系

系统采用右手 3D 笛卡尔坐标系，与飞机坐标轴对齐：

| 坐标轴 | 方向 | 单位 | 用途 |
|--------|------|------|------|
| **X** | 沿货舱长度（航向：机头→机尾） | mm | 烟雾源 X、探测器 X 坐标 |
| **Y** | 沿货舱宽度（展向：左→右） | mm | 烟雾源 Y、探测器 Y 坐标 |
| **Z** | 沿货舱高度（垂向） | mm | 固定为顶棚高度（探测器 Z = 货舱高度）；烟雾源 Z 始终为 0 |

**货舱布局（俯视图）：**

```
←── 长度 (X) ──→
┌─────────────────────┐  ↑
│    前壁（Forward）   │  │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  │  宽度 (Y)
│                      │  │
│    后壁（Aft）        │  ↓
└─────────────────────┘
```

Channel-A 探测器（奇数 ID）：绿色圆点显示  
Channel-B 探测器（偶数 ID）：蓝色圆点显示

---

## 3. 模块说明—sklearn_compat.py

### 3.1 目的

加载使用旧版 sklearn（<1.0）序列化的 pickle 文件，这些文件内部引用了 `sklearn.ensemble.forest` 和 `sklearn.tree.tree` 等在 sklearn ≥1.0 中已变更的模块路径。同时为 `Tree` 类打补丁，添加 sklearn 1.1+ 引入的 `missing_go_to_left` 字段。

### 3.2 公开 API

```python
from sklearn_compat import load_model

model = load_model(path: str) -> LegacyModelWrapper
```

### 3.3 类说明

#### LegacyModelWrapper

封装原始 sklearn 估计器，提供统一的 `.predict()` 接口。

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `_model` | object | 底层 sklearn 估计器 |
| `n_outputs_` | int | 输出数量（默认 1） |
| `n_features_in_` | int | 输入特征数量 |
| `estimators_` | list | 基础决策树列表 |
| `classes_` | array | 类别标签（如适用） |

**方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `predict(X)` | `np.ndarray` | 对所有树取平均预测 |
| `__repr__()` | str | 人类可读摘要 |

#### _PatchedTree

`sklearn.tree._tree.Tree` 的子类，在反序列化时通过 `__setstate__` 添加 `missing_go_to_left` 字段。

#### _CompatUnpickler

自定义 pickle Unpickler，将旧模块路径重定向：

- `sklearn.ensemble.forest` → `sklearn.ensemble._forest`
- `sklearn.tree.tree` → `sklearn.tree`

同时拦截 `Tree` 类查找，返回 `_PatchedTree` 而非原始类。

### 3.4 使用示例

```python
from sklearn_compat import load_model

# 加载旧版模型
predictor = load_model('rf_model_all.model')

# 使用方式与任何 sklearn 模型相同
alarm_time = predictor.predict(distance_mm / 10.0)
# distance 单位为 mm，模型需要米（÷10）
```

---

## 4. 模块说明—simulation_config.py

### 4.1 目的

提供类型安全、经过校验的配置对象。消除了旧版基于裸字典方案中 `bay_dimension[0/1/2]` 谁是谁的歧义。在构造时即完成全部校验，运行时通过属性访问。

### 4.2 数据类

#### BayConfig（冻结数据类）

| 字段 | 类型 | 单位 | 校验 |
|------|------|------|------|
| `width_mm` | float | mm | 必须 > 0 |
| `length_mm` | float | mm | 必须 > 0 |
| `height_mm` | float | mm | 必须 > 0 |

#### ArrangeConfig（冻结数据类）

| 字段 | 类型 | 单位 | 默认值 | 校验 |
|------|------|------|--------|------|
| `method` | Literal["center", "side"] | — | — | 必须为 "center" 或 "side" |
| `fwd_mm` | int | mm | 0 | 必须 >= 0 |
| `aft_mm` | int | mm | 0 | 必须 >= 0 |
| `displace_mm` | int | mm | 100 | 必须 >= 0 |

#### SimulationConfig（数据类）

| 字段 | 类型 | 说明 |
|------|------|------|
| `type_` | str | 机型名称（仅展示用） |
| `sd_num` | int | 探测器总数（必须为偶数） |
| `bay` | BayConfig | 货舱尺寸 |
| `criteria_s` | int | 报警时间阈值（秒） |
| `arrange` | ArrangeConfig | 探测器排布参数 |
| `_src_step_x_mm` | int | 烟雾源网格 X 方向步长（默认 1000） |
| `_src_step_y_mm` | int | 烟雾源网格 Y 方向步长（默认 1000） |
| `sd_length_mm` | float | 探测器长度（仅 UI 用，默认 140.0） |
| `sd_width_mm` | float | 探测器宽度（仅 UI 用，默认 145.0） |
| `_custom_detectors` | list | GUI 注入的探测器列表 (x,y,name,ch)，不参与序列化 |

### 4.3 工厂方法

```python
# 从 JSON 文件构造
cfg = SimulationConfig.from_json('inputs.json')

# 从字典构造（解析后的 JSON）
cfg = SimulationConfig.from_dict({'Type': 'CR929-base', 'SD_num': 10, ...})
```

### 4.4 派生属性

```python
cfg.sd_num_per_channel  # = sd_num // 2
cfg.grid_points         # = floor(length/1000+1) * floor(width/1000+1)
cfg.steps              # = (1000, 1000) 步长元组
```

### 4.5 序列化

```python
# 导出为字典（兼容 inputs.json 格式）
d = cfg.to_dict()

# 导出为 JSON 文件
cfg.to_json('output.json')
```

### 4.6 校验

```python
errors = cfg.validate()  # 返回错误字符串列表，空列表 = 全部通过
```

校验项：

- `sd_num` 必须为偶数
- `sd_num >= 2`
- `fwd_space + aft_space < bay length`（探测器必须能放入）

---

## 5. 模块说明—result_manager.py

### 5.1 目的

用版本化输出替代旧版写死 `test_result.csv` 的方案。每次仿真运行生成带时间戳的独立 CSV 文件（如 `result_20260418_143022.csv`）及配套的 `.meta.json` 元信息文件。旧结果永不覆盖。

### 5.2 公开 API

```python
from result_manager import ResultManager

rm = ResultManager(output_dir=".", filename_fmt=None)
rm.start_run(fieldnames=["No.", "Src Loc.", "SD1", "SD2", ...], metadata={...})
rm.append_row({"No.": 1, "Src Loc.": "(0, 0, 0)", "SD1": 12.5, "Alarm": True})
rm.append_row(row_dict)  # 重复 N 次（每个网格点一次）
rm.finalize()            # 关闭文件，写入 .meta.json

df = rm.latest_dataframe  # 读取为 DataFrame
runs = rm.list_runs()     # 列出所有历史运行
```

### 5.3 输出文件命名

格式：`result_{YYYYMMDD}_{HHMMSS}.csv`  
示例：`result_20260418_163946.csv`

配套元信息：`result_20260418_163946.meta.json`

### 5.4 元信息 Schema（.meta.json）

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

### 5.5 ResultManager 生命周期

```
start_run()  →  打开新 CSV 文件，写入 header
     ↓
append_row()  →  调用 N 次（每个网格点一次）
     ↓
finalize()    →  关闭 CSV，写入 .meta.json
```

支持连续多次 `start_run()` 调用；每次自动关闭前一次运行。

---

## 6. 模块说明—simulation.py

### 6.1 目的

与 GUI 解耦的核心仿真引擎。可无 GUI 运行（支持单元测试）。管理完整网格扫描循环、双通道报警逻辑、进度回调及结果收集。

### 6.2 类说明

#### SingleSimulationResult（数据类）

| 字段 | 类型 | 说明 |
|------|------|------|
| `test_no` | int | 测试序号 |
| `src_x_mm` | float | 烟雾源 X（mm） |
| `src_y_mm` | float | 烟雾源 Y（mm） |
| `src_z_mm` | float | 烟雾源 Z（mm，始终为 0.0） |
| `alarm_times` | dict | 每个探测器的 `{sd_name: alarm_time_s}` |
| `alarm` | bool | 总体报警决策（双通道 AND 结果） |
| `failed_channel` | str | ""=双通道均报警，"A"=A 未触发，"B"=B 未触发，"AB"=双通道均未触发 |

方法：`to_dict()`、`fieldnames` 属性

#### GridScanCallbacks

网格扫描事件的回调容器。

```python
cbs = GridScanCallbacks(
    on_progress=lambda current, total, msg: update_progress_bar(),
    on_stop=lambda: user_requested_stop,
)
```

#### SimulationEngine

**构造函数：**

```python
SimulationEngine(
    config: SimulationConfig,
    predictor,           # 来自 sklearn_compat 的 ML 预测器
    result_manager: ResultManager | None = None,
)
```

**关键方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `run_grid(callbacks)` | `list[SingleSimulationResult]` | 完整网格扫描 |
| `run_single()` | `SingleSimulationResult` | 当前烟雾源位置的单点测试 |
| `set_source(x_mm, y_mm)` | bool | 设置烟雾源位置；超出货舱边界返回 False |
| `detector_info()` | `list[tuple]` | 返回 `[(x,y,name,ch), ...]` 用于 GUI 可视化 |

**内部方法：**

| 方法 | 说明 |
|------|------|
| `_apply_arrangement()` | 根据 ArrangeConfig 方法放置探测器 |
| `_center_arrange()` | 中心排布：成对探测器共享 X，Channel-A/B 在 Y 方向偏移 |
| `_side_arrange()` | 侧向排布：所有 A 在上排，所有 B 在下排 |
| `_det_logic()` | AND 报警：双通道均须至少有一个探测器在 criteria 内报警 |
| `_movesrc()` | 生成器：按货舱网格遍历烟雾源（Y 内循环，X 外循环） |

**固定常量：**

- `STEP_X_MM = 1000` — 沿货舱长度方向的网格步长
- `STEP_Y_MM = 1000` — 沿货舱宽度方向的网格步长

### 6.3 报警逻辑

双通道 AND 逻辑要求至少一个 Channel-A 探测器 **且** 至少一个 Channel-B 探测器在 `criteria_s` 秒内报警：

```python
cha_ok = any(sd.alarm_time[0] <= crit for sd in CHA_SD)
chb_ok = any(sd.alarm_time[0] <= crit for sd in CHB_SD)
alarm = cha_ok and chb_ok
```

### 6.4 烟雾源网格遍历

`_movesrc()` 生成器扫描货舱：

- **外循环：** X 方向（长度），步长 1000mm
- **内循环：** Y 方向（宽度），步长 1000mm
- 端点（length, width）包含在网格中

以 CR929 货舱（16184×4166mm）为例：

- X 方向：0, 1000, 2000, ..., 16000, 16184 → 18 个点
- Y 方向：0, 1000, 2000, 3000, 4000, 4166 → 5 个点
- 总网格点：18 × 5 = 90

---

## 7. 模块说明—detector.py

### 7.1 目的

模拟单个烟雾探测器（SD）的行为：计算探测器到烟雾源的三维欧几里得距离，然后调用 ML 预测器获取报警时间。

### 7.2 类：Detector

**构造函数参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `predictor` | Any | "None" | 具有 `.predict()` 方法的 ML 模型 |
| `x_pos` | float | 0.0 | X 坐标（mm） |
| `y_pos` | float | 0.0 | Y 坐标（mm） |
| `z_pos` | float | 0.0 | Z 坐标（mm） |
| `dimension` | tuple[float,float] | (140.0, 145.0) | （长, 宽）单位 mm |
| `threshold` | float\|None | None | 单探测器报警阈值（秒），None=使用全局阈值 |
| `SD_id` | int | 1 | 探测器 ID（从 1 开始） |
| `name` | str | "SD" | 探测器名称（如 "SD1"） |
| `channel_id` | int | 1 | 0=Channel-A，1=Channel-B |

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `x_pos`, `y_pos`, `z_pos` | float | 当前 3D 位置（mm） |
| `dimension` | tuple | 探测器尺寸（长, 宽）mm |
| `threshold` | float\|None | 单探测器阈值 |
| `SD_id` | int | 从 1 开始的 ID |
| `name` | str | 显示名称 |
| `channel_id` | int | 0=Channel-A，1=Channel-B |
| `alarm_time` | `np.ndarray` | 最新预测结果，shape (1,) |
| `dis` | float | 到当前烟雾源的距离（mm） |

**关键方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `set_pos(x, y, z)` | None | 一次性设置三个坐标 |
| `get_pos()` | tuple[float,float,float] | 获取当前位置 |
| `get_dimension()` | tuple[float,float] | 获取探测器（长, 宽） |
| `set_threshold(t)` | None | 设置单探测器阈值 |
| `get_threshold()` | float\|None | 获取阈值 |
| `set_channel_id(ch)` | None | 设置通道（0=A, 1=B） |
| `set_SD_id(id)` | None | 设置从 1 开始的 ID |
| `alarm(src_pos)` | None | 计算距离并预测报警时间 |

**距离计算：**

```
dis = sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)   [mm]
alarm_time = predictor.predict(dis / 10.0)    [模型需要米]
```

**`__repr__`：**

```
<Detector SD1 id=1 ch=0 pos=(1000.0,2083.0,1727.6)>
```

---

## 8. 模块说明—cargobay.py

### 8.1 目的

模拟货舱物理几何结构。提供尺寸访问、边界判断和容积计算。

### 8.2 类：CargoBay

**坐标系（右手系）：**

- X：沿长度方向（航向）
- Y：沿宽度方向（展向）
- Z：沿高度方向（垂向）

**构造函数：**

```python
CargoBay(width_mm=1000.0, length_mm=5000.0, height_mm=5000.0)
```

**方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get_dimension()` | tuple[float,float,float] | 返回（宽, 长, 高）单位 mm |
| `set_dimension(w, l, h)` | None | 一次性设置三个尺寸 |
| `set_prop(cargo_prop)` | None | 从包含 'width'/'length'/'height' 的字典设置 |
| `isinbay(pos)` | bool | (x,y) 是否在长度×宽度范围内 |

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `volume_mm3` | float | 宽×长×高 mm³ |
| `width_mm` | float | 只读宽度 |
| `length_mm` | float | 只读长度 |
| `height_mm` | float | 只读高度 |

**`__repr__`：**

```
<CargoBay 16184x4166x1727.6mm vol=1.17m³>
```

---

## 9. 模块说明—gui_pyside6_winstylepy

### 9.1 目的

主 GUI 应用程序。经典 Windows 原生风格界面，含 Tab 页、工具栏和状态栏。处理所有用户交互：配置加载、模型加载、仿真执行、结果显示及历史管理。

### 9.2 窗口布局

```
┌──────────────────────────────────────────────────────────────┐
│ 菜单栏：文件(F)  帮助(H)                                      │
├──────────────────────────────────────────────────────────────┤
│ 工具栏：[打开] [加载模型] [运行] [停止] | [图表] [对比] [导出] │
├──────────────────────────────────────────────────────────────┤
│ TabWidget                                                     │
│  ┌──────┬────────────┬──────┬────────┬──────┐              │
│  │ 仿真  │ 探测器定位  │ 结果  │  设置  │ 帮助  │              │
│  └──────┴────────────┴──────┴────────┴──────┘              │
│  [各 Tab 内容不同]                                            │
├──────────────────────────────────────────────────────────────┤
│ 日志：[仿真输出文本]                                          │
├──────────────────────────────────────────────────────────────┤
│ 状态栏：[状态消息]                                            │
└──────────────────────────────────────────────────────────────┘
```

### 9.3 Tab 页说明

#### Tab 0：仿真

```
┌─────────────────────────────────────────────────────┐
│ 基本参数                    布局参数                  │
│ 机型: [____CR929-base__]   排布: [center ▼]         │
│ 探测器数量: [10]           前端间距: [100]           │
│ 货舱宽度: [4166] mm         后端间距: [100]           │
│ 货舱长度: [16184] mm        偏移: [100]              │
│ 货舱高度: [1727.6] mm                               │
│ 报警阈值: [60] s                                   │
├─────────────────────────────────────────────────────┤
│         CargoBayWidget（货舱可视化 + 热力图）          │
│                                                     │
│  [绿色圆点 = Channel-A，蓝色圆点 = Channel-B]         │
│  [热力图：绿色点 = 报警，红色点 = 漏检]               │
│                                                     │
├─────────────────────────────────────────────────────┤
│ 运行状态: [====进度条====] [测试 #42]               │
└─────────────────────────────────────────────────────┘
```

#### Tab 1：探测器定位

```
┌────────────────────────┬──────────────────────────┐
│                        │ 探测器列表（双击编辑坐标）   │
│  _DetectorCanvas       │  名称    X(mm)  Y(mm) 通道  │
│  (拖拽画布)            │  SD1    1000   2083   A     │
│                        │  SD2    1000   2083   B     │
│  单击空白处：添加 SD   │  SD3    3000   2083   A     │
│  右键：弹出菜单        │  ...                        │
│  拖拽：移动位置        ├────────────────────────────-┤
│                        │ [自动均匀布局] [确认布放]    │
│                        │ [应用到仿真]   [取消确认]    │
│                        ├────────────────────────────-┤
│                        │ 货舱尺寸: 宽度[4166] 长度[16184]│
│                        │ 显示通道: [全部 ▼]           │
└────────────────────────┴────────────────────────────┘
```

#### Tab 2：结果

显示最新仿真运行的完整 DataFrame 表格（可排序列）：No.、Src Loc.、SD1、SD2、...、Alarm。

#### Tab 3：设置

- 输出目录 QLineEdit
- 仿真历史表格（双击重新加载）
- 刷新历史按钮

#### Tab 4：帮助

只读 HTML 帮助，包含使用说明。

### 9.4 关键 GUI 类

#### CargoBayWidget

在货舱示意图上渲染的自定义 QWidget。

**功能：**

- 渲染货舱矩形（含网格线（2000mm 间隔））
- 绘制 X/Y 轴标签和刻度
- 渲染探测器位置（彩色圆点：绿色=A，蓝色=B）
- **v5.1 新增：** 渲染热力图叠加：绿色点=报警，红色点=漏检
- 中心线虚线标记
- 图例框

**关键方法：**

| 方法 | 说明 |
|------|------|
| `set_layout(detectors, bay_width, bay_length)` | 更新探测器位置 |
| `set_heatmap(data)` | 设置热力图数据 `{(x,y): alarm_bool}`，触发重绘 |
| `clear_heatmap()` | 清除热力图叠加 |

#### DetectorDragWidget

组合 `_DetectorCanvas` + 探测器列表 + 控制按钮的复合组件，管理确认工作流。

**确认工作流（v5.1）：**

1. 用户在画布上拖拽/添加/删除探测器
2. 用户点击 **「确认布放」** → `_confirmed = True`
   - 画布边框变为绿色（3px 实线 #27AE60）
   - 「确认布放」按钮禁用
   - 「取消确认」按钮启用
   - 「应用到仿真」按钮启用
3. 用户点击 **「应用到仿真」**
   - 确认对话框列出所有探测器
   - 调用 `sync_from_drag_widget()` 更新仿真参数
4. 用户可点击 **「取消确认」** 解锁布局以便进一步编辑

**信号：**

| 信号 | 载荷 | 说明 |
|------|------|------|
| `detectors_changed` | `list[(x,y,name,ch),...]` | 画布探测器变化时发出 |

#### _DetectorCanvas

处理底层鼠标交互的内部 QWidget。

**鼠标交互：**

| 操作 | 结果 |
|------|------|
| 左键单击探测器 | 开始拖拽 |
| 左键单击空白货舱区域 | 添加新探测器（A/B 通道交替） |
| 左键拖拽 | 移动探测器（限制在货舱边界内） |
| 左键释放 | 结束拖拽，发出 `detectors_changed` |
| 右键单击探测器 | 上下文菜单：编辑、删除、改为 A/B 通道 |
| 鼠标移动 | 悬停高亮 + 坐标提示 |

**上下文菜单选项：**

- 编辑 [SDn]：打开 QInputDialog 输入 X 和 Y 坐标
- 删除 [SDn]：从列表中移除探测器
- 改为 A通道：设置通道为 0
- 改为 B通道：设置通道为 1

#### DetectorSizeDialog（v5.1）

探测器物理尺寸配置模态对话框。

**UI 布局：**

```
┌─────────────────────────────────────┐
│ 探测器尺寸设置                    [X]│
├──────────────────┬──────────────────┤
│ 长度 L (mm): [140.0] │                  │
│ 宽度  W (mm): [145.0] │  [_SizePreview] │
│ 高度  H (mm): [58.0]  │   （三视图）     │
│                  │                  │
│ 预置尺寸         │                  │
│ [标准型 140×145×58]│                  │
│ [小型  100×100×45] │                  │
│ [大型  180×160×70] │                  │
├──────────────────┴──────────────────┤
│              [OK]  [Cancel]          │
└─────────────────────────────────────┘
```

**预置尺寸：**

| 预置 | L×W×H（mm） |
|------|-------------|
| 标准型 | 140×145×58 |
| 小型 | 100×100×45 |
| 大型 | 180×160×70 |

#### _SizePreviewWidget

绘制探测器三视图示意图（俯视图 + 侧视图）的自定义 QWidget，含尺寸标注。

#### ConfigLoadThread

异步加载 `SimulationConfig.from_json()` 的 QThread 子类。成功时发出 `loaded` (cfg, path)，失败时发出 `error` (msg)。

#### SimulationThread

运行 `SimulationEngine.run_grid()` 的 QThread 子类。

**信号：**

| 信号 | 载荷 | 说明 |
|------|------|------|
| `progress` | `int, str` | 百分比（0-100）和状态消息 |
| `finished` | `float, int, int` | 耗时（秒）、失败次数、总次数 |
| `error` | `str` | 错误消息 |
| `detector_inf` | `list[tuple]` | 最终探测器位置 |
| `log_msg` | `str` | 显示用的日志消息 |

#### parse_src_loc(s)（v5.1）

解析结果 CSV 中 "Src Loc." 列字符串的工具函数。

```python
def parse_src_loc(s: str):
    """解析 'Src Loc.' 列如 '(0.0, 1000.0, 0.0)' → (x, y, z)"""
    m = re.findall(r"[-+]?\d+\.?\d*", s)
    if len(m) >= 3:
        return float(m[0]), float(m[1]), float(m[2])
    return None, None, None
```

支持格式：`(0.0, 1000.0, 0.0)`、`(0, 1000, 0)`、`0.0, 1000.0, 0.0`

### 9.5 图标系统（v5.1）

图标从 `icons/` 子目录加载（使用 `_get_icon()`）：

```python
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def _get_icon(name: str) -> QIcon:
    path = os.path.join(_ICON_DIR, f"icon_{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()   # 空图标兜底
```

**可用图标（共 17 个）：**

open、save、model、run、stop、chart、compare、export、detector、drag、bay、settings、help、history、heatmap、delete、alert

### 9.6 matplotlib 中文字体配置（v5.1）

在 `_show_chart()` 和 `_show_compare()` 中应用：

```python
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
```

回退链确保中文在 Windows（SimHei、Microsoft YaHei）和跨平台（Arial Unicode MS）环境下均能正常显示。

### 9.7 配置文件加载同步拖拽页面（v5.1）

通过 `_on_config_loaded()` 加载配置文件时：

```python
def _on_config_loaded(self, cfg, path):
    self.inputs = cfg
    self._sync_ui_from_cfg()       # ① 同步 UI 参数控件
    self._refresh_vis_from_ui()    # ② 刷新可视化 + 同步拖拽页面
    self.log.append(f"已加载配置: {path}")
    self.btn_open.setEnabled(True)
    self.btn_run.setEnabled(self.predictor is not None)
    # 自动切换到拖拽 Tab 提示用户确认
    self.tabs.setCurrentWidget(self.drag_wid)
    self.log.append("[提示] 请检查探测器定位 Tab，确认布放后再运行仿真")
```

`_refresh_vis_from_ui()` 根据加载配置的 `arrange` 方法（center/side）计算探测器位置，然后调用：

```python
self.drag_wid.init_detectors(dets, w, l)
```

这会用自动计算的位置填充拖拽页面，供用户审查并在运行前选择修改。

---

## 10. 数据字典—inputsjson

### 10.1 文件位置

`/mnt/c/smoke_project/inputs.json`

### 10.2 Schema

```json
{
    "Type": "string",
    "SD_num": "integer (偶数, ≥2)",
    "bay_dimension": ["float (width_mm)", "float (length_mm)", "float (height_mm)"],
    "criteria": "integer (秒, >0)",
    "arrange": {
        "method": "string (center|side)",
        "fwd space": "integer (mm, ≥0)",
        "aft space": "integer (mm, ≥0)",
        "displace": "integer (mm, ≥0)"
    }
}
```

### 10.3 字段定义

| 字段 | JSON 路径 | 类型 | 单位 | 有效范围 | 说明 |
|------|----------|------|------|----------|------|
| Type | `Type` | string | — | 任意 | 机型名称（仅展示用） |
| SD_num | `SD_num` | integer | — | 偶数, ≥2 | 烟雾探测器总数（双通道须为偶数） |
| bay_dimension[0] | `bay_dimension[0]` | float | mm | >0 | 货舱宽度（Y 轴，展向） |
| bay_dimension[1] | `bay_dimension[1]` | float | mm | >0 | 货舱长度（X 轴，航向） |
| bay_dimension[2] | `bay_dimension[2]` | float | mm | >0 | 货舱高度（Z 轴，垂向） |
| criteria | `criteria` | integer | 秒 | >0 | 报警时间阈值；任一通道探测器在此时间内报警则该通道满足 |
| arrange.method | `arrange.method` | string | — | "center" 或 "side" | 排布算法 |
| arrange.fwd space | `arrange.fwd space` | integer | mm | ≥0 | 前壁到首个探测器的距离 |
| arrange.aft space | `arrange.aft space` | integer | mm | ≥0 | 后壁到最末探测器的距离 |
| arrange.displace | `arrange.displace` | integer | mm | ≥0 | 每对通道相对于中线的偏移 |

### 10.4 排布方法说明

#### "center" 中心排布

- 探测器成对排列（SD1+SD2、SD3+SD4、...）
- 每对探测器共享相同的 X 坐标
- Channel-A（奇数 ID）偏移 +displace 在中线上方
- Channel-B（偶数 ID）偏移 -displace 在中线下方

#### "side" 侧向排布

- 所有 Channel-A 探测器排列在 Y = width/2 + displace 处
- 所有 Channel-B 探测器排列在 Y = width/2 - displace 处
- X 方向等间距排列所有 N 个探测器

### 10.5 示例 inputs.json（CR929 配置）

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

**派生值：**

- 10 个探测器 → 5 对，5 个 Channel-A + 5 个 Channel-B
- 网格：X: 0 到 16184，步长 1000mm = 18 个点；Y: 0 到 4166，步长 1000mm = 5 个点
- 总仿真点数：18 × 5 = 90

---

## 11. 配置指南

### 11.1 典型工作流程

```
1. 启动应用程序
   python gui_pyside6_winstyle.py

2. 加载配置文件
   文件 → 打开配置... (Ctrl+O)
   选择 inputs.json

   应用程序自动：
   - 解析 JSON 为 SimulationConfig
   - 填充所有参数控件
   - 计算自动探测器位置
   - 同步探测器拖拽 Tab
   - 切换到探测器定位 Tab 供用户审查

3. 审查探测器布局（探测器定位 Tab）
   - 目视检查探测器位置
   - 拖拽调整单个位置
   - 或点击「自动均匀布局」生成均匀分布布局
   - 点击「确认布放」锁定
   - 点击「应用到仿真」应用到仿真

4. 加载 ML 模型
   文件 → 加载模型...
   选择 rf_model_all.model

5. 运行仿真
   点击工具栏「运行」

   进度条实时更新
   日志显示每个探测器位置和测试编号

6. 查看结果
   - 热力图叠加出现在货舱可视化上
   - 结果 Tab 中填充结果表格
   - 点击「图表」查看 matplotlib 报警分析

7. 对比运行（可选）
   点击「对比」对比任意两个历史运行
```

### 11.2 探测器尺寸配置

```
文件 → 探测器尺寸...
```

打开 `DetectorSizeDialog`。配置 L/W/H 后点击确定。值保存在 `SimulationConfig.sd_length_mm` 和 `sd_width_mm` 中，影响排布计算。

### 11.3 输出目录

在「设置」Tab 中配置。默认为 `.`（应用程序目录）。所有结果 CSV 文件以时间戳命名写入此处。

---

## 12. 构建与部署

### 12.1 依赖项

| 包 | 版本 | 用途 |
|----|------|------|
| Python | 3.10+ | 运行时 |
| PySide6 | ≥6.5 | GUI 框架 |
| scikit-learn | ≥1.0 | ML 模型加载（带兼容层） |
| pandas | ≥2.0 | DataFrame 结果 |
| numpy | ≥1.24 | 数组运算 |
| matplotlib | ≥3.7 | 图表 |
| pickle |（内置）| 模型序列化 |

### 12.2 安装依赖

```bash
pip install PySide6 pandas numpy scikit-learn matplotlib
```

### 12.3 运行应用程序

```bash
cd /mnt/c/smoke_project
python gui_pyside6_winstyle.py
```

### 12.4 WSLg 注意事项（Windows + WSL2）

对于高分屏，启动前设置：

```bash
export QT_SCALE_FACTOR=2
export QT_SCALE_FACTOR_ROUNDING_POLICY=Passthrough
python gui_pyside6_winstyle.py
```

### 12.5 无 GUI 运行（单元测试）

```python
from simulation_config import SimulationConfig
from simulation import SimulationEngine
from sklearn_compat import load_model
from result_manager import ResultManager

cfg = SimulationConfig.from_json('inputs.json')
predictor = load_model('rf_model_all.model')
rm = ResultManager(output_dir='.')

eng = SimulationEngine(cfg, predictor, result_manager=rm)
results = eng.run_grid()  # 无需 GUI
```

---

## 13. 更新日志

### v5.1 — 2026-04-18

#### 新增功能

**热力图可视化（CargoBayWidget）**

- 仿真完成后，货舱组件叠加彩色编码热力图，每个网格点显示报警（绿色）与漏检（红色）
- 使用 `parse_src_loc()` 从 CSV "Src Loc." 列提取 X/Y 坐标（格式：`(x, y, z)`）
- 热力图圆点（直径 10px）绘制在各网格点 (x, y) 位置
- 右下角图例更新显示报警/漏检颜色含义
- `CargoBayWidget` 上新增 `set_heatmap(data)` 和 `clear_heatmap()` 方法
- 通过历史表格双击加载历史结果时也会渲染热力图

**探测器拖拽定位及确认工作流（DetectorDragWidget）**

- 新增「探测器定位」Tab，含交互式拖放画布
- 左键单击空白货舱区域添加新探测器（A/B 通道交替）
- 左键拖拽移动现有探测器（限制在货舱边界内）
- 右键弹出上下文菜单：编辑坐标、删除、改为 A/B 通道
- 双击表格行打开坐标输入对话框
- **确认工作流：** 点击「确认布放」→「绿色边框表示布局已锁定」→「应用到仿真」同步到仿真参数
- 「取消确认」解锁布局以便进一步编辑
- 通道过滤下拉菜单（全部/仅A通道/仅B通道）
- 「自动均匀布局」按钮生成均匀分布布局

**探测器尺寸对话框（DetectorSizeDialog，v5.1）**

- 新增模态对话框：文件 → 探测器尺寸...
- 配置探测器长/宽/高（mm）
- 三个预置按钮：标准型（140×145×58）、小型（100×100×45）、大型（180×160×70）
- 实时三视图预览组件，显示俯视图+侧视图及尺寸标注
- 保存到 `SimulationConfig.sd_length_mm`、`sd_width_mm` 字段

**matplotlib 中文字体修复（`_show_chart`、`_show_compare`）**

- 在字体回退链末尾添加 `Arial Unicode MS`
- 完整链：`['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']`
- 在所有 `plt.rcParams` 用法之前应用

**图标系统（`_get_icon`）**

- 从 `icons/` 目录统一加载图标
- 所有工具栏按钮、菜单项和上下文菜单操作均使用主题图标
- 共 17 个图标：open、save、model、run、stop、chart、compare、export、detector、drag、bay、settings、help、history、heatmap、delete、alert
- 文件不存在时回退到空 QIcon()

**配置文件加载同步拖拽页面（`_on_config_loaded` → `_refresh_vis_from_ui`）**

- 加载 inputs.json 现自动填充探测器定位 Tab 的计算探测器位置
- 用户点击「应用到仿真」时设置 `SimulationConfig._custom_detectors`
- `sync_from_drag_widget()` 更新 sp_sdnum、sp_width、sp_len、bay_wid 布局

#### Bug 修复

- `parse_src_loc()` 正确处理浮点数和整数：`(0.0, 1000.0, 0.0)` 和 `(0, 1000, 0)`
- `BayConfig` 校验在 width_mm/length_mm/height_mm ≤ 0 时抛出异常
- `SimulationConfig.validate()` 正确检查 `fwd + aft < bay length`

---

### v5.0 — 2026-04-18（重大重构）

#### 架构重构

- **新增 `sklearn_compat.py`**：sklearn 旧模型兼容层独立为模块，GUI 不再内联兼容代码
- **新增 `simulation_config.py`**：类型化配置对象，构造时即完成完整校验，消除 bay_dimension[0/1/2] 歧义
- **新增 `result_manager.py`**：仿真结果版本化管理，每次运行生成带时间戳的独立文件，不再覆盖旧结果
- **新增 `simulation.py`**：仿真核心引擎 `SimulationEngine` 完全解耦，可不依赖 GUI 独立运行，支持单元测试

#### 代码质量

- 全流程添加 type hints（Detector / CargoBay / SimulationConfig）
- `alarm_time` 标注为 `np.ndarray`
- 新增 `Detector.__repr__`
- `CargoBay` 新增 `volume_mm3` 属性和 `__repr__`
- `SimulationConfig.validate()` 完整校验
- 修复进度计算 Bug：`floor(len/1000)*floor(width/1000)` 替代 ceil，精确网格点数

#### 废弃文件清理

- 删除 `gui_pyside6_v3.py`（1014 行旧版 GUI）
- 删除 `gui.py`（6296 行极早期版本）
- `Environment.py` — 文件保留但标记为废弃（被 `simulation.py` 替代）

---

*文档撰写日期：2026-04-18 | smoke_project v5.1*
