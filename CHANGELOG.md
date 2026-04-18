# 更新日志 (Changelog)

## [v5.0] - 2026-04-18 (Major Refactor)

### 架构重构
- **新增 `sklearn_compat.py`**：sklearn 旧模型兼容层独立为独立模块，GUI 不再内联兼容代码
- **新增 `simulation_config.py`**：类型化配置对象，构造时即完成完整校验，消除 bay_dimension[0/1/2] 歧义
- **新增 `result_manager.py`**：仿真结果版本化管理，每次运行生成带时间戳的独立文件（`result_YYYYMMDD_HHMMSS.csv`），不再覆盖旧结果
- **新增 `simulation.py`**：仿真核心引擎 `SimulationEngine` 完全解耦，可不依赖 GUI 独立运行，支持单元测试
- **`Environment.py`**：已废弃，被 `simulation.py` 替代（文件保留但标记为废弃）

### 代码质量
- **进度计算 Bug 修复**：`total_tests = ceil(len/1000)*ceil(width/1000)` → `floor(len/1000)*floor(width/1000)`，精确的网格点数
- **增加 type hints**：Detector / CargoBay / SimulationConfig 全流程添加类型标注
- **Detector 增强**：`alarm_time` 标注为 `np.ndarray`，增加 `__repr__`
- **CargoBay 增强**：去除无用的 `detectorSeries` 属性，增加 `volume_mm3` 属性和 `__repr__`
- **配置校验**：增加 `SimulationConfig.validate()` 完整校验（sd_num 偶数、空间不越界等）

### 废弃文件清理
- **删除 `gui_pyside6_v3.py`**：1014行旧版 GUI，完全废弃
- **删除 `gui.py`**：6296行极早期版本，完全废弃

### 开发文档
- 更新 `development-documentation.md` 至 v5.0，同步新架构说明
- 更新 README.md 模块列表

---

## [v4.0] - 2026-04-06 (Native Windows UI)

### 全新界面风格
- Windows 传统 C++ 软件风格重设计
- 顶部工具栏（几何图标，无 emoji）
- Tab 页导航（Simulation / Results / Settings / Help）
- 底部状态栏
- Segoe UI 字体，深色主题

### 新增
- 新增 `gui_pyside6_winstyle.py`（独立文件，ui-redesign 分支）
- 新增正式开发文档 `docs/development-documentation.md`（SDSS-SW-001）

---

## [v3.1] - 2026-04-06

### 修复
- 图表中文显示：matplotlib 中文字体配置（SimHei / Microsoft YaHei）
- 进度条实时更新：预计算总测试次数，解决进度条长期停留在0%的问题
- 货舱布局可视化：缩小探测器图标、标签字号和图例，解决重叠看不清的问题
- 货舱可视化最小尺寸增加，改善小屏显示效果

### 依赖
- PySide6
- pandas
- numpy
- scikit-learn
- matplotlib

---

## [v3.0] - 2026-04-05

### 修复/新增
- 修复 CargoBay 高度参数传递错误（bay_dim[0] -> bay_dim[2]）
- 修复 Detector 距离计算缺少 Z 轴分量
- 修复 Environment side 排列模式循环嵌套 bug
- 修复 sklearn 旧模型在新版无法加载的问题
- 设置页面参数现在会应用到仿真中
- 进度条实时更新 + 停止按钮可用
- 高分屏 DPI 自适应
- 货舱布局可视化（显示探测器位置）
- 减少弹窗提示

## [v3.x] - 2026-04-06

### UI 修复
- **字体替换**：所有 `Microsoft YaHei` / `SimHei` 替换为系统内置 `Noto Sans CJK SC`，解决 WSL/Linux 环境下中文显示为方块的问题
- **matplotlib 中文**：图表字体同步替换为 `Noto Sans CJK SC`，解决坐标轴/标题中文乱码

### 高分屏适配
- 新增 `QT_SCALE_FACTOR=2` 强制 2x 缩放（WSLg 环境）
- 新增 `QT_SCALE_FACTOR_ROUNDING_POLICY=Passthrough` 避免缩放取整模糊
