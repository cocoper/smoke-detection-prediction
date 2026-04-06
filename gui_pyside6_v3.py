# -*- coding:utf-8 -*-
"""
飞机货舱烟雾检测仿真系统 - v3.1 (PySide6)

v3.1 修复/新增内容:
- 修复图表中文显示（matplotlib 中文字体配置）
- 修复仿真进度条实时更新（预计算总测试次数）
- 优化货舱布局可视化（缩小探测器图标和标签，解决重叠问题）
- 货舱可视化最小尺寸增加，改善小屏显示效果

v3.0 修复/新增内容:
- 修复 CargoBay 高度参数传递错误（bay_dim[0] -> bay_dim[2]）
- 修复 Detector 距离计算缺少 Z 轴分量
- 修复 Environment side 排列模式循环嵌套 bug
- 修复 sklearn 旧模型在新版无法加载的问题
- 设置页面参数现在会应用到仿真中
- 进度条实时更新 + 停止按钮可用
- 高分屏 DPI 自适应
- 货舱布局可视化（显示探测器位置）
- 减少弹窗提示

依赖安装: pip install PySide6 pandas numpy scikit-learn
运行方式: python gui_pyside6_v3.py
"""

import os
import sys
import json
import pickle
import io
import math
import warnings
import numpy as np
from time import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFrame, QSlider, QComboBox,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QStackedWidget, QListWidget,
    QListWidgetItem, QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush
import pandas as pd

warnings.filterwarnings('ignore')

# ========== sklearn 旧模型兼容 ==========
import importlib as _importlib
sys.modules['sklearn.ensemble.forest'] = _importlib.import_module('sklearn.ensemble._forest')
sys.modules['sklearn.tree.tree'] = _importlib.import_module('sklearn.tree')

from sklearn.tree._tree import Tree as _OrigTree

class _PatchedTree(_OrigTree):
    """修补旧版 Tree 的 dtype 兼容问题"""
    def __setstate__(self, state):
        if isinstance(state, dict) and 'nodes' in state:
            nodes = state['nodes']
            if hasattr(nodes, 'dtype') and hasattr(nodes.dtype, 'names'):
                names = nodes.dtype.names or ()
                if 'missing_go_to_left' not in names:
                    new_names = list(names) + ['missing_go_to_left']
                    new_formats = [nodes.dtype.fields[n][0].str for n in names] + ['u1']
                    new_dtype = np.dtype(list(zip(new_names, new_formats)))
                    new_arr = np.empty(nodes.shape, dtype=new_dtype)
                    for n in names:
                        new_arr[n] = nodes[n]
                    new_arr['missing_go_to_left'] = np.ones(len(new_arr), dtype='u1')
                    state = dict(state)
                    state['nodes'] = new_arr
        super().__setstate__(state)

class _CompatUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        new_mod = {'sklearn.ensemble.forest': 'sklearn.ensemble._forest'}.get(module, module)
        cls = super().find_class(new_mod, name)
        if cls is _OrigTree:
            return _PatchedTree
        return cls

class LegacyModelWrapper:
    """包装旧版 sklearn 模型，兼容新版接口"""
    def __init__(self, model):
        self._model = model
        self.n_outputs_ = getattr(model, 'n_outputs_', 1)
        self.n_features_in_ = getattr(model, 'n_features_in_', None)
        self.estimators_ = getattr(model, 'estimators_', [])
        self.classes_ = getattr(model, 'classes_', None)

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, dtype=float))
        if X.shape == (1,):  # 单特征标量 [[val]] -> [[val]]
            pass  # 已经是正确形状
        elif X.ndim == 1:
            X = X.reshape(1, -1)
        predictions = np.array([t.predict(X) for t in self.estimators_])
        if self.n_outputs_ == 1:
            return np.mean(predictions, axis=0)
        else:
            return np.array([np.mean(predictions[:, i]) for i in range(self.n_outputs_)])

def load_model(path):
    with open(path, 'rb') as f:
        raw = _CompatUnpickler(f).load()
    return LegacyModelWrapper(raw)

# ========== 业务逻辑层 ==========
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment


# ==================== 货舱可视化组件 ====================

class CargoBayWidget(QWidget):
    """货舱布局可视化"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)  # 增加最小尺寸
        self.setStyleSheet("background: #1e1e1e; border-radius: 5px;")
        self.detectors = []
        self.bay_width = 1000
        self.bay_length = 5000
        self.smoke_source = None

    def set_layout(self, detectors, bay_width, bay_length):
        self.detectors = detectors
        self.bay_width = bay_width
        self.bay_length = bay_length
        self.update()

    def set_smoke_source(self, x, y):
        self.smoke_source = (x, y)
        self.update()

    def paintEvent(self, event):
        if not self.detectors:
            p = QPainter(self)
            p.setPen(QPen(QColor(136, 136, 136)))
            p.setFont(QFont("Microsoft YaHei", 16))
            p.drawText(self.rect(), Qt.AlignCenter, "加载配置后\n显示货舱布局")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        mt, mb, ml = 50, 35, 60
        dw, dh = w - 2*ml, h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s = min(sx, sy)
        bw, bh = self.bay_length * s, self.bay_width * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2

        # 标题
        p.setPen(QPen(Qt.white))
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        p.drawText(int(w/2-120), 28, f"货舱 {self.bay_length} x {self.bay_width} mm | {len(self.detectors)} 个探测器")

        # 货舱背景
        p.setPen(QPen(QColor(0, 120, 212), 2))
        p.setBrush(QBrush(QColor(22, 38, 52)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        # 网格 (每2000mm)
        p.setPen(QPen(QColor(45, 55, 65), 1, Qt.DotLine))
        for g in range(2000, int(self.bay_length), 2000):
            gx = int(ox + g * s)
            p.drawLine(gx, int(oy), gx, int(oy + bh))
        p.setPen(QPen(QColor(90, 100, 110)))
        p.setFont(QFont("Microsoft YaHei", 8))
        for g in range(0, int(self.bay_length)+1, 2000):
            gx = int(ox + g * s)
            p.drawText(gx - 10, int(oy + bh + 16), str(g))

        # 中线
        cy = int(oy + bh / 2)
        p.setPen(QPen(QColor(70, 85, 100), 1, Qt.DashLine))
        p.drawLine(int(ox), cy, int(ox + bw), cy)

        # 探测器
        for x, y, name, ch in self.detectors:
            dx, dy = ox + x * s, oy + y * s
            if ch == 0:
                c = QColor(16, 185, 80); label = f"{name}(A)"
            else:
                c = QColor(59, 165, 255); label = f"{name}(B)"

            # 光晕（缩小）
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 50)))
            p.drawEllipse(int(dx-10), int(dy-10), 20, 20)
            # 圆点（缩小）
            p.setPen(QPen(c, 1))
            p.setBrush(QBrush(c))
            p.drawEllipse(int(dx-5), int(dy-5), 10, 10)
            # 标签（缩小字号，去掉背景框）
            p.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(label)
            th = fm.height()
            # 标签放在探测器右上方，避免重叠
            tx, ty_ = int(dx + 7), int(dy - th/2 - 1)
            p.setPen(QPen(c))
            p.drawText(tx, ty_ + fm.ascent(), label)

        # 图例（缩小）
        lx = int(ox + bw - 115)
        ly = int(oy + bh - 38)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 150)))
        p.drawRoundedRect(lx, ly, 110, 32, 4, 4)
        p.setBrush(QBrush(QColor(16, 185, 80)))
        p.drawEllipse(lx+8, ly+6, 8, 8)
        p.setPen(QPen(QColor(200,200,200)))
        p.setFont(QFont("Microsoft YaHei", 9))
        p.drawText(lx+20, ly+14, "A 通道")
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(59, 165, 255)))
        p.drawEllipse(lx+8, ly+20, 8, 8)
        p.setPen(QPen(QColor(200,200,200)))
        p.drawText(lx+20, ly+28, "B 通道")

        p.end()


# ==================== 仿真线程        painter.end()


# ==================== 仿真线程 ====================

class SimulationThread(QThread):
    progress = Signal(int, str)
    finished = Signal(float, int, int)
    error = Signal(str)
    detector_info = Signal(list)  # 传递探测器位置信息

    def __init__(self, inputs, predictor):
        super().__init__()
        self.inputs = inputs
        self.predictor = predictor
        self._stop_flag = False

    def run(self):
        try:
            bay_dim = self.inputs['bay_dimension']
            SD_NUM = self.inputs['SD_num']
            arrange = self.inputs['arrange']

            cargobay = CargoBay(width=bay_dim[0], length=bay_dim[1], height=bay_dim[2])
            dets = [Detector(self.predictor, name=f'SD{i+1}') for i in range(SD_NUM)]

            env = Environment(
                cargobay_obj=cargobay,
                detector_series=dets,
                detector_qty=SD_NUM,
                arrange=arrange,
                time_criteria=self.inputs['criteria']
            )

            # 预计算总测试次数，解决进度条一直为0的问题
            import math
            total_tests = math.ceil(bay_dim[1] / 1000) * math.ceil(bay_dim[0] / 1000)
            self._progress_total = total_tests
            env._progress_callback = self._on_progress
            env._stop_flag = lambda: self._stop_flag

            # 发送探测器位置给可视化
            det_info = [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in dets]
            self.detector_info.emit(det_info)

            start_t = time()
            env.run(mode='all')
            end_t = time()

            df = pd.read_csv('test_result.csv')
            failed = len(df[df['Alarm'] == False])

            self.progress.emit(100, "完成！")
            self.finished.emit(end_t - start_t, failed, len(df))

        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current, total, msg):
        # 使用预计算的总次数计算进度百分比
        pct = int(current / max(self._progress_total, 1) * 95) if self._progress_total > 0 else 0
        self.progress.emit(min(pct, 95), msg)

    def stop(self):
        self._stop_flag = True


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.predictor = None
        self.inputs = None
        self.sim_thread = None
        self.sim_results = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("飞机货舱烟雾检测仿真系统 v3.0")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 900)
        self._apply_dark_theme()

        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QHBoxLayout(central)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._create_content()
        self._create_sidebar()

        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        self.sidebar.setCurrentRow(0)
        self.statusBar().showMessage("就绪")

    def _apply_dark_theme(self):
        dark = QPalette()
        dark.setColor(QPalette.Window, QColor(30, 30, 30))
        dark.setColor(QPalette.WindowText, Qt.white)
        dark.setColor(QPalette.Base, QColor(45, 45, 45))
        dark.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark.setColor(QPalette.ToolTipBase, Qt.white)
        dark.setColor(QPalette.ToolTipText, Qt.white)
        dark.setColor(QPalette.Text, Qt.white)
        dark.setColor(QPalette.Button, QColor(53, 53, 53))
        dark.setColor(QPalette.ButtonText, Qt.white)
        dark.setColor(QPalette.BrightText, Qt.red)
        dark.setColor(QPalette.Highlight, QColor(0, 120, 212))
        dark.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(dark)

        # 全局字体 - 14pt 基础
        font = QFont()
        font.setPointSize(14)
        font.setFamily("Microsoft YaHei")
        QApplication.setFont(font)

        # 全局样式表 - 统一增大字体
        QApplication.instance().setStyleSheet("""
            QLabel { font-size: 14px; }
            QPushButton { font-size: 14px; min-height: 36px; padding: 6px 16px; }
            QGroupBox { font-size: 15px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QTextEdit { font-size: 13px; }
            QComboBox { font-size: 14px; min-height: 32px; padding: 4px 8px; }
            QSpinBox, QDoubleSpinBox { font-size: 14px; min-height: 32px; padding: 4px 8px; }
            QSlider::groove:horizontal { height: 8px; }
            QListWidget { font-size: 14px; }
            QProgressBar { font-size: 14px; min-height: 28px; }
            QTableWidget { font-size: 13px; }
            QHeaderView::section { font-size: 13px; padding: 8px; }
        """)

    def _create_sidebar(self):
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(200)
        self.sidebar.setFrameShape(QFrame.NoFrame)
        self.sidebar.setSpacing(8)

        for text, page_id in [("▶ 仿真", "sim"), ("📊 结果", "result"),
                               ("⚙️ 设置", "settings"), ("❓ 帮助", "help")]:
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, page_id)
            self.sidebar.addItem(item)

        status_frame = QFrame()
        status_frame.setStyleSheet("background: #252526; border-radius: 8px;")
        sl = QVBoxLayout(status_frame)
        sl.setContentsMargins(10, 10, 10, 10)
        self.status_label = QLabel("⚫ 未就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        sl.addWidget(self.status_label)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.addWidget(self.sidebar)
        sidebar_layout.addWidget(status_frame)

        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar_layout)
        sidebar_widget.setStyleSheet("background: #252526;")
        self._main_layout.addWidget(sidebar_widget)

    def _create_content(self):
        self.pages = QStackedWidget()
        self.pages.addWidget(self._create_sim_page())
        self.pages.addWidget(self._create_result_page())
        self.pages.addWidget(self._create_settings_page())
        self.pages.addWidget(self._create_help_page())
        self._main_layout.addWidget(self.pages)

    def _on_page_changed(self, index):
        self.pages.setCurrentIndex(index)

    # ==================== 仿真页面 ====================

    def _create_sim_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        layout.addWidget(self._create_config_panel(), 3)
        layout.addWidget(self._create_visual_panel(), 5)
        layout.addWidget(self._create_status_panel(), 3)
        return page

    def _create_config_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #252526; border-radius: 10px; border: 1px solid #3c3c3c; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("📋 仿真配置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding-bottom: 8px;")
        layout.addWidget(title)

        # 配置文件
        cg = QGroupBox("配置文件")
        cl = QVBoxLayout()
        self.config_path_label = QLabel("未加载")
        self.config_path_label.setStyleSheet("color: #cccccc;")
        cl.addWidget(self.config_path_label)
        btn = QPushButton("📂 打开配置")
        btn.clicked.connect(self._open_config)
        cl.addWidget(btn)
        cg.setLayout(cl)
        layout.addWidget(cg)

        # 模型文件
        mg = QGroupBox("预测模型")
        ml = QVBoxLayout()
        self.model_path_label = QLabel("未加载")
        self.model_path_label.setStyleSheet("color: #cccccc;")
        ml.addWidget(self.model_path_label)
        btn2 = QPushButton("📥 加载模型")
        btn2.clicked.connect(self._open_model)
        ml.addWidget(btn2)
        mg.setLayout(ml)
        layout.addWidget(mg)

        # 配置预览
        pg = QGroupBox("配置预览")
        pl = QVBoxLayout()
        self.config_preview = QTextEdit()
        self.config_preview.setReadOnly(True)
        self.config_preview.setPlainText("未加载配置文件\n\n请先加载 inputs.json")
        self.config_preview.setStyleSheet("background: #1e1e1e; color: #cccccc; border: none;")
        pl.addWidget(self.config_preview)
        pg.setLayout(pl)
        layout.addWidget(pg)

        layout.addStretch()
        return panel

    def _create_visual_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #252526; border-radius: 10px; border: 1px solid #3c3c3c; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("✈️ 货舱布局示意")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding-bottom: 8px;")
        layout.addWidget(title)

        self.cargo_widget = CargoBayWidget()
        self.cargo_widget.setMinimumHeight(450)  # 增加最小高度
        layout.addWidget(self.cargo_widget, 1)  # stretch=1 占满剩余空间

        return panel

    def _create_status_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #252526; border-radius: 10px; border: 1px solid #3c3c3c; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("📊 仿真状态")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white; padding-bottom: 8px;")
        layout.addWidget(title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3c3c3c; border-radius: 5px; text-align: center; background: #1e1e1e; color: white; }
            QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("等待开始仿真...")
        self.progress_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(self.progress_label)

        sg = QGroupBox("统计信息")
        sl = QVBoxLayout()
        self.total_label = QLabel("总测试数: 0")
        self.total_label.setStyleSheet("color: white; font-size: 14px;")
        sl.addWidget(self.total_label)
        self.success_label = QLabel("成功: 0")
        self.success_label.setStyleSheet("color: #107c10; font-size: 14px;")
        sl.addWidget(self.success_label)
        self.fail_label = QLabel("失败: 0")
        self.fail_label.setStyleSheet("color: #e81123; font-size: 14px;")
        sl.addWidget(self.fail_label)
        sg.setLayout(sl)
        layout.addWidget(sg)

        self.run_btn = QPushButton("▶ 开始仿真")
        self.run_btn.setMinimumHeight(50)
        self.run_btn.setStyleSheet("""
            QPushButton { background: #107c10; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; }
            QPushButton:hover { background: #0b5a0b; }
            QPushButton:disabled { background: #3c3c3c; color: #888888; }
        """)
        self.run_btn.clicked.connect(self._run_simulation)
        layout.addWidget(self.run_btn)

        self.stop_btn = QPushButton("⏹ 停止仿真")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton { background: #3c3c3c; color: white; border: none; border-radius: 8px; }
            QPushButton:hover { background: #e81123; }
            QPushButton:disabled { background: #2c2c2c; color: #555555; }
        """)
        self.stop_btn.clicked.connect(self._stop_simulation)
        layout.addWidget(self.stop_btn)

        clear_btn = QPushButton("🗑 清除结果")
        clear_btn.setStyleSheet("""
            QPushButton { background: #3c3c3c; color: white; border: none; border-radius: 8px; }
            QPushButton:hover { background: #555555; }
        """)
        clear_btn.clicked.connect(self._clear_results)
        layout.addWidget(clear_btn)

        layout.addStretch()
        return panel

    # ==================== 结果页面 ====================

    def _create_result_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        toolbar = QHBoxLayout()
        title = QLabel("📊 仿真结果")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        chart_btn = QPushButton("📈 查看图表")
        chart_btn.clicked.connect(self._show_chart)
        toolbar.addWidget(chart_btn)

        export_btn = QPushButton("💾 导出CSV")
        export_btn.clicked.connect(self._export_results)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(["序号", "烟雾位置X", "烟雾位置Y", "SD1", "SD2", "SD3", "SD4", "报警"])
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setStyleSheet("""
            QTableWidget { background: #252526; alternate-background-color: #2c2c2c; color: white; gridline-color: #3c3c3c; border: 1px solid #3c3c3c; border-radius: 5px; }
            QTableWidget::item { padding: 5px; }
            QTableWidget::item:selected { background: #0078d4; }
            QHeaderView::section { background: #1e1e1e; color: white; padding: 8px; border: none; border-bottom: 2px solid #0078d4; }
        """)
        layout.addWidget(self.result_table)

        self.empty_label = QLabel("暂无仿真结果\n\n请先运行仿真")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; font-size: 14px;")
        self.empty_label.setMinimumHeight(200)
        self.empty_label.setVisible(True)
        layout.addWidget(self.empty_label)
        return page

    # ==================== 设置页面 ====================

    def _create_settings_page(self):
        page = QWidget()
        scroll = QVBoxLayout(page)
        scroll.setContentsMargins(20, 20, 20, 20)

        title = QLabel("⚙️ 参数设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        scroll.addWidget(title)

        desc = QLabel("💡 修改参数后点击【应用到配置】，或直接开始仿真时自动应用。")
        desc.setStyleSheet("color: #cccccc; font-size: 13px;")
        desc.setWordWrap(True)
        scroll.addWidget(desc)

        # 探测器参数
        sg = QGroupBox("🔍 烟雾探测器参数")
        sgl = QGridLayout()
        sgl.addWidget(QLabel("探测器数量:"), 0, 0)
        self.sd_quantity = QSpinBox()
        self.sd_quantity.setRange(2, 20)
        self.sd_quantity.setValue(6)
        self.sd_quantity.setSingleStep(2)
        sgl.addWidget(self.sd_quantity, 0, 1)

        sgl.addWidget(QLabel("误报率:"), 1, 0)
        self.sd_far = QDoubleSpinBox()
        self.sd_far.setRange(0, 1); self.sd_far.setValue(0.01); self.sd_far.setDecimals(4)
        sgl.addWidget(self.sd_far, 1, 1)

        sgl.addWidget(QLabel("灵敏度:"), 2, 0)
        self.sd_sen = QDoubleSpinBox()
        self.sd_sen.setRange(0, 1); self.sd_sen.setValue(0.98); self.sd_sen.setDecimals(4)
        sgl.addWidget(self.sd_sen, 2, 1)
        sg.setLayout(sgl)
        scroll.addWidget(sg)

        # 仿真参数
        simg = QGroupBox("🎯 仿真参数")
        siml = QGridLayout()
        siml.addWidget(QLabel("排列方式:"), 0, 0)
        self.sim_method = QComboBox()
        self.sim_method.addItems(["center", "side"])
        siml.addWidget(self.sim_method, 0, 1)

        siml.addWidget(QLabel("报警时间阈值(秒):"), 1, 0)
        self.sim_criteria = QSpinBox()
        self.sim_criteria.setRange(1, 600); self.sim_criteria.setValue(60)
        siml.addWidget(self.sim_criteria, 1, 1)

        siml.addWidget(QLabel("前壁板间距:"), 2, 0)
        self.sim_fwd = QSpinBox()
        self.sim_fwd.setRange(0, 5000); self.sim_fwd.setValue(100)
        siml.addWidget(self.sim_fwd, 2, 1)

        siml.addWidget(QLabel("后壁板间距:"), 3, 0)
        self.sim_aft = QSpinBox()
        self.sim_aft.setRange(0, 5000); self.sim_aft.setValue(100)
        siml.addWidget(self.sim_aft, 3, 1)

        siml.addWidget(QLabel("中线偏移:"), 4, 0)
        self.sim_disp = QSpinBox()
        self.sim_disp.setRange(0, 5000); self.sim_disp.setValue(100)
        siml.addWidget(self.sim_disp, 4, 1)

        simg.setLayout(siml)
        scroll.addWidget(simg)

        apply_btn = QPushButton("✅ 应用到配置")
        apply_btn.setMinimumHeight(45)
        apply_btn.setStyleSheet("""
            QPushButton { background: #0078d4; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: bold; }
            QPushButton:hover { background: #005a9e; }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        scroll.addWidget(apply_btn)
        scroll.addStretch()
        return page

    def _apply_settings(self):
        if self.inputs is None:
            QMessageBox.warning(self, "提示", "请先加载配置文件！")
            return
        sd_num = self.sd_quantity.value()
        if sd_num % 2 != 0:
            sd_num -= 1
            self.sd_quantity.setValue(sd_num)

        self.inputs['SD_num'] = sd_num
        self.inputs['criteria'] = self.sim_criteria.value()
        self.inputs['arrange']['method'] = self.sim_method.currentText()
        self.inputs['arrange']['fwd space'] = self.sim_fwd.value()
        self.inputs['arrange']['aft space'] = self.sim_aft.value()
        self.inputs['arrange']['displace'] = self.sim_disp.value()

        info = f"飞机型号: {self.inputs.get('Type', 'N/A')}\n探测器数量: {sd_num}\n货舱尺寸: {self.inputs.get('bay_dimension', 'N/A')}\n仿真判据: {self.inputs['criteria']}秒\n排列方式: {self.inputs['arrange']['method']}\n\n✅ 设置已应用！"
        self.config_preview.setPlainText(info)
        self._update_status("🟡 参数已更新", "#ff8c00")

    # ==================== 帮助页面 ====================

    def _create_help_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("❓ 使用帮助")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: white;")
        layout.addWidget(title)

        help_text = """╔══════════════════════════════════════════════════════════╗
║    飞机货舱烟雾检测仿真系统 - 使用说明 v3.0       ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  【使用步骤】                                           ║
║  ① 点击"打开配置"加载 inputs.json                     ║
║  ② 点击"加载模型"加载 .model 文件                    ║
║  ③ (可选) 设置页面调整参数后点击"应用到配置"        ║
║  ④ 点击"开始仿真"运行烟雾扩散仿真                    ║
║  ⑤ 切换到"结果"查看详细数据                          ║
║                                                          ║
║  【货舱可视化】                                         ║
║  绿色圆点 = A通道探测器                                ║
║  蓝色圆点 = B通道探测器                                ║
║  橙色圆点 = 烟雾源位置                                ║
║                                                          ║
║  【v3.0 修复】                                          ║
║  • CargoBay 高度参数修复                               ║
║  • 距离计算增加 Z 轴分量                               ║
║  • 旧版 sklearn 模型兼容加载                           ║
║  • side 排列模式 bug 修复                              ║
║  • 高分屏字体适配                                      ║
║  • 货舱可视化显示                                      ║
║  • 进度条实时更新 + 停止可用                           ║
╚══════════════════════════════════════════════════════════╝"""
        help_box = QTextEdit()
        help_box.setReadOnly(True)
        help_box.setPlainText(help_text)
        help_box.setFont(QFont("Courier", 10))
        help_box.setStyleSheet("QTextEdit { background: #1e1e1e; color: #cccccc; border: none; padding: 10px; }")
        layout.addWidget(help_box)

        ag = QGroupBox("ℹ️ 关于")
        al = QVBoxLayout()
        al.addWidget(QLabel("飞机货舱烟雾检测仿真系统 v3.0"))
        al.addWidget(QLabel("基于机器学习的烟雾探测器响应时间预测"))
        al.addWidget(QLabel("© 2026 Xuan Yang"))
        ag.setLayout(al)
        layout.addWidget(ag)
        return page

    # ==================== 事件处理 ====================

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择配置文件", "", "JSON文件 (*.json);;所有文件 (*.*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.inputs = json.load(f)

            self.config_path_label.setText(os.path.basename(path))
            self.config_path_label.setStyleSheet("color: #107c10;")

            # 同步设置页
            self.sd_quantity.setValue(self.inputs.get('SD_num', 6))
            self.sim_criteria.setValue(self.inputs.get('criteria', 60))
            method = self.inputs.get('arrange', {}).get('method', 'center')
            idx = self.sim_method.findText(method)
            if idx >= 0: self.sim_method.setCurrentIndex(idx)
            self.sim_fwd.setValue(self.inputs.get('arrange', {}).get('fwd space', 100))
            self.sim_aft.setValue(self.inputs.get('arrange', {}).get('aft space', 100))
            self.sim_disp.setValue(self.inputs.get('arrange', {}).get('displace', 100))

            info = f"飞机型号: {self.inputs.get('Type', 'N/A')}\n探测器数量: {self.inputs.get('SD_num', 'N/A')}\n货舱尺寸: {self.inputs.get('bay_dimension', 'N/A')}\n仿真判据: {self.inputs.get('criteria', 'N/A')}秒\n排列方式: {self.inputs.get('arrange', {}).get('method', 'N/A')}"
            self.config_preview.setPlainText(info)

            # 更新可视化
            self._update_visualization()

            if self.predictor is not None:
                self._update_status("🟢 就绪", "#107c10")
            else:
                self._update_status("🟡 配置已加载，请加载模型", "#ff8c00")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载配置失败:\n{str(e)}")

    def _update_visualization(self):
        """根据当前 inputs 更新货舱可视化"""
        if self.inputs is None:
            return
        bay_dim = self.inputs['bay_dimension']
        SD_NUM = self.inputs['SD_num']
        arrange = self.inputs['arrange']

        cargobay = CargoBay(width=bay_dim[0], length=bay_dim[1], height=bay_dim[2])
        # 用空的 predictor 作为占位
        try:
            from sklearn.tree import DecisionTreeRegressor
            dummy = DecisionTreeRegressor()
        except:
            dummy = None
        dets = [Detector(dummy or 'None', name=f'SD{i+1}') for i in range(SD_NUM)]
        env = Environment(
            cargobay_obj=cargobay,
            detector_series=dets,
            detector_qty=SD_NUM,
            arrange=arrange,
            time_criteria=self.inputs['criteria']
        )
        det_info = [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in dets]
        self.cargo_widget.set_layout(det_info, bay_dim[0], bay_dim[1])

    def _open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "模型文件 (*.model);;所有文件 (*.*)")
        if not path:
            return
        try:
            self.predictor = load_model(path)
            self.model_path_label.setText(os.path.basename(path))
            self.model_path_label.setStyleSheet("color: #107c10;")
            if self.inputs is not None:
                self._update_status("🟢 就绪", "#107c10")
            else:
                self._update_status("🟡 模型已加载，请加载配置", "#ff8c00")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载模型失败:\n{str(e)}")

    def _run_simulation(self):
        if self.predictor is None:
            QMessageBox.warning(self, "提示", "请先加载预测模型！")
            return
        if self.inputs is None:
            QMessageBox.warning(self, "提示", "请先打开配置文件！")
            return

        self._clear_results_table()
        self._update_status("🟡 仿真中...", "#ff8c00")
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在仿真...")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.sim_thread = SimulationThread(self.inputs, self.predictor)
        self.sim_thread.progress.connect(self._on_progress)
        self.sim_thread.finished.connect(self._on_finished)
        self.sim_thread.error.connect(self._on_error)
        self.sim_thread.detector_info.connect(self._on_detector_info)
        self.sim_thread.start()

    def _on_detector_info(self, det_info):
        """接收探测器位置并更新可视化"""
        if self.inputs:
            bay_dim = self.inputs['bay_dimension']
            self.cargo_widget.set_layout(det_info, bay_dim[0], bay_dim[1])

    def _on_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.progress_label.setText(msg)
        # 强制刷新GUI，让进度条实时更新
        QApplication.processEvents()

    def _on_finished(self, elapsed, failed, total):
        try:
            self.sim_results = pd.read_csv('test_result.csv')
        except:
            self.sim_results = None
        self._update_status("🟢 仿真完成", "#107c10")
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"完成！耗时: {elapsed:.1f}秒")
        self.total_label.setText(f"总测试数: {total}")
        self.success_label.setText(f"成功: {total - failed}")
        self.fail_label.setText(f"失败: {failed}")
        self._update_result_table()
        self.empty_label.setVisible(False)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.sidebar.setCurrentRow(1)

    def _on_error(self, msg):
        self._update_status("🔴 出错", "#e81123")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", f"仿真出错:\n{msg}")

    def _stop_simulation(self):
        if self.sim_thread and self.sim_thread.isRunning():
            self.sim_thread.stop()
        self._update_status("⚠️ 正在停止...", "#ff8c00")

    def _clear_results(self):
        self._clear_results_table()
        self._clear_stats()
        self.progress_bar.setValue(0)
        self.progress_label.setText("等待开始仿真...")
        self.sim_results = None
        self.empty_label.setVisible(True)
        self._update_status("⚫ 已清除", "#888888")

    def _clear_results_table(self):
        self.result_table.setRowCount(0)

    def _clear_stats(self):
        self.total_label.setText("总测试数: 0")
        self.success_label.setText("成功: 0")
        self.fail_label.setText("失败: 0")

    def _update_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_result_table(self):
        if self.sim_results is None:
            return
        sd_cols = [c for c in self.sim_results.columns if c.startswith('SD')]
        total_cols = 3 + len(sd_cols) + 1
        self.result_table.setColumnCount(total_cols)
        self.result_table.setHorizontalHeaderLabels(["序号", "烟雾位置X", "烟雾位置Y"] + sd_cols + ["报警"])
        self.result_table.setRowCount(len(self.sim_results))

        for idx, row in self.sim_results.iterrows():
            alarm = "✓" if row.get('Alarm', False) else "✗"
            src_loc = row.get('Src Loc.', (0, 0))
            if isinstance(src_loc, str):
                try:
                    src_loc = eval(src_loc)
                except:
                    src_loc = (0, 0)
            items = [str(idx + 1)]
            if isinstance(src_loc, (tuple, list)) and len(src_loc) >= 2:
                items += [f"{src_loc[0]:.1f}", f"{src_loc[1]:.1f}"]
            else:
                items += ["-", "-"]
            for sd_name in sd_cols:
                val = row.get(sd_name, 0)
                items.append(f"{val:.2f}" if pd.notna(val) else "-")
            items.append(alarm)

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if col == total_cols - 1:
                    item.setForeground(QColor("#107c10" if alarm == "✓" else "#e81123"))
                self.result_table.setItem(idx, col, item)
        self.result_table.resizeColumnsToContents()

    def _show_chart(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "提示", "请先运行仿真！")
            return
        try:
            import matplotlib
            matplotlib.use('QtAgg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from PySide6.QtWidgets import QDialog, QVBoxLayout as DQVBoxLayout
            
            # 配置中文字体
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

            alarm_data = self.sim_results[self.sim_results['Alarm'] == True]
            fig, axes = plt.subplots(1, 2, figsize=(12, 4))

            sd_cols = [c for c in self.sim_results.columns if c.startswith('SD')]
            if len(alarm_data) > 0 and len(sd_cols) > 0:
                vals = alarm_data[sd_cols[0]].dropna()
                if len(vals) > 0:
                    axes[0].hist(vals, bins=30, color='steelblue', alpha=0.7)
                    axes[0].set_xlabel('报警时间 (s)')
                    axes[0].set_ylabel('频次')
                    axes[0].set_title(f'{sd_cols[0]} 报警时间分布')

            total = len(self.sim_results)
            failed = len(self.sim_results[self.sim_results['Alarm'] == False])
            axes[1].bar(['成功', '失败'], [total - failed, failed], color=['green', 'red'], alpha=0.7)
            axes[1].set_ylabel('测试数')
            axes[1].set_title(f'仿真结果统计 (总计: {total})')
            plt.tight_layout()

            dialog = QDialog(self)
            dialog.setWindowTitle("仿真结果图表")
            dialog.resize(900, 500)
            dl = DQVBoxLayout(dialog)
            dl.addWidget(FigureCanvasQTAgg(fig))
            dialog.exec()
        except ImportError:
            QMessageBox.information(self, "提示", "请安装 matplotlib:\npip install matplotlib")

    def _export_results(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "提示", "没有可导出的结果！")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存结果", "simulation_result.csv", "CSV文件 (*.csv);;所有文件 (*.*)")
        if path:
            try:
                self.sim_results.to_csv(path, index=False)
                QMessageBox.information(self, "成功", f"结果已保存到:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")


# ==================== 主程序入口 ====================

def main():
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
