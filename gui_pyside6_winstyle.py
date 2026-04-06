# -*- coding:utf-8 -*-
"""
飞机货舱烟雾检测仿真系统 - Windows 传统风格界面 (PySide6)
风格参考：传统 C++ Windows 软件风格
  - 顶部工具栏（几何图标）
  - Tab 页导航
  - 底部状态栏
  - 无 emoji，纯文字 + 几何图标
依赖安装: pip install PySide6 pandas numpy scikit-learn
运行方式: python gui_pyside6_winstyle.py
"""

import os, sys, json, pickle, io, math, warnings
import numpy as np
from time import time
import pandas as pd

warnings.filterwarnings('ignore')

# sklearn 旧模型兼容
import importlib as _importlib
sys.modules['sklearn.ensemble.forest'] = _importlib.import_module('sklearn.ensemble._forest')
sys.modules['sklearn.tree.tree'] = _importlib.import_module('sklearn.tree')
from sklearn.tree._tree import Tree as _OrigTree

class _PatchedTree(_OrigTree):
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
    def __init__(self, model):
        self._model = model
        self.n_outputs_ = getattr(model, 'n_outputs_', 1)
        self.n_features_in_ = getattr(model, 'n_features_in_', None)
        self.estimators_ = getattr(model, 'estimators_', [])
        self.classes_ = getattr(model, 'classes_', None)

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, dtype=float))
        if X.ndim == 1:
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFrame, QSlider, QComboBox,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QStackedWidget, QGroupBox, QGridLayout,
    QSpinBox, QDoubleSpinBox, QTabWidget, QToolBar, QToolButton,
    QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QIcon, QPixmap, QPainterPath


# ==================== 图标工厂 ====================

def _make_icon(color, draw_fn):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_fn(painter, QColor(color))
    painter.end()
    return QIcon(pixmap)

def _icon_open(p, c):
    p.setPen(QPen(c, 1.5))
    p.setBrush(QBrush(QColor(255, 195, 77)))
    p.drawRect(3, 9, 18, 12)
    p.setPen(QPen(QColor(200, 150, 50), 1.5))
    p.drawRect(3, 6, 10, 5)

def _icon_play(p, c):
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(c))
    path = QPainterPath()
    path.moveTo(6, 4); path.lineTo(20, 12); path.lineTo(6, 20); path.closeSubpath()
    p.drawPath(path)

def _icon_stop(p, c):
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(c))
    p.drawRect(5, 5, 14, 14)

def _icon_chart(p, c):
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(c))
    p.drawRect(3, 14, 5, 7)
    p.drawRect(9, 9, 5, 12)
    p.drawRect(15, 4, 5, 17)

def _icon_export(p, c):
    p.setPen(QPen(c, 2)); p.setBrush(Qt.NoBrush)
    p.drawRect(4, 3, 14, 16)
    p.drawLine(11, 7, 11, 17)
    p.drawLine(7, 13, 11, 17)
    p.drawLine(15, 13, 11, 17)

def _icon_config(p, c):
    p.setPen(QPen(c, 1.5)); p.setBrush(QBrush(QColor(100, 100, 100)))
    for i in range(8):
        r = 7
        ax = 12 + int(r * math.cos(math.radians(i * 45)))
        ay = 12 + int(r * math.sin(math.radians(i * 45)))
        p.drawLine(12, 12, ax, ay)
    p.setBrush(QBrush(QColor(60, 60, 60)))
    p.drawEllipse(8, 8, 8, 8)

def _icon_clear(p, c):
    p.setPen(QPen(c, 2.5))
    p.drawLine(5, 5, 19, 19)
    p.drawLine(19, 5, 5, 19)


# ==================== 货舱可视化 ====================

class CargoBayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background: #1e1e1e; border: 1px solid #3c3c3c;")
        self.detectors = []
        self.bay_width = 1000
        self.bay_length = 5000

    def set_layout(self, detectors, bay_width, bay_length):
        self.detectors = detectors
        self.bay_width = bay_width
        self.bay_length = bay_length
        self.update()

    def paintEvent(self, event):
        if not self.detectors:
            p = QPainter(self)
            p.setPen(QPen(QColor(136, 136, 136)))
            p.setFont(QFont("Segoe UI", 14))
            p.drawText(self.rect(), Qt.AlignCenter, "Load configuration to display cargo bay layout")
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

        p.setPen(QPen(Qt.white))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(int(w/2-150), 28, f"Cargo Bay  {self.bay_length} x {self.bay_width} mm  |  {len(self.detectors)} Detectors")

        p.setPen(QPen(QColor(0, 120, 212), 2))
        p.setBrush(QBrush(QColor(22, 38, 52)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        p.setPen(QPen(QColor(45, 55, 65), 1, Qt.DotLine))
        for g in range(2000, int(self.bay_length), 2000):
            p.drawLine(int(ox + g * s), int(oy), int(ox + g * s), int(oy + bh))
        p.setPen(QPen(QColor(90, 100, 110)))
        p.setFont(QFont("Segoe UI", 8))
        for g in range(0, int(self.bay_length)+1, 2000):
            p.drawText(int(ox + g * s - 10), int(oy + bh + 16), str(g))

        cy = int(oy + bh / 2)
        p.setPen(QPen(QColor(70, 85, 100), 1, Qt.DashLine))
        p.drawLine(int(ox), cy, int(ox + bw), cy)

        for x, y, name, ch in self.detectors:
            dx, dy = ox + x * s, oy + y * s
            c = QColor(16, 185, 80) if ch == 0 else QColor(59, 165, 255)
            label = f"{name}(A)" if ch == 0 else f"{name}(B)"
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 50)))
            p.drawEllipse(int(dx-10), int(dy-10), 20, 20)
            p.setPen(QPen(c, 1)); p.setBrush(QBrush(c))
            p.drawEllipse(int(dx-5), int(dy-5), 10, 10)
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            fm = p.fontMetrics()
            p.setPen(QPen(c))
            p.drawText(int(dx + 7), int(dy - fm.height()/2 - 1) + fm.ascent(), label)

        lx = int(ox + bw - 115); ly = int(oy + bh - 38)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(0, 0, 0, 150)))
        p.drawRect(lx, ly, 110, 32)
        p.setBrush(QBrush(QColor(16, 185, 80)))
        p.drawEllipse(lx+8, ly+6, 8, 8)
        p.setPen(QPen(QColor(200,200,200))); p.setFont(QFont("Segoe UI", 9))
        p.drawText(lx+20, ly+14, "Ch-A")
        p.setPen(Qt.NoPen); p.setBrush(QBrush(QColor(59, 165, 255)))
        p.drawEllipse(lx+8, ly+20, 8, 8)
        p.setPen(QPen(QColor(200,200,200)))
        p.drawText(lx+20, ly+28, "Ch-B")
        p.end()


# ==================== 仿真线程 ====================

class SimulationThread(QThread):
    progress = Signal(int, str)
    finished = Signal(float, int, int)
    error = Signal(str)
    detector_info = Signal(list)

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
            env = Environment(cargobay_obj=cargobay, detector_series=dets,
                              detector_qty=SD_NUM, arrange=arrange,
                              time_criteria=self.inputs['criteria'])
            total_tests = math.ceil(bay_dim[1] / 1000) * math.ceil(bay_dim[0] / 1000)
            self._progress_total = total_tests
            env._progress_callback = self._on_progress
            env._stop_flag = lambda: self._stop_flag
            det_info = [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in dets]
            self.detector_info.emit(det_info)
            start_t = time()
            env.run(mode='all')
            end_t = time()
            df = pd.read_csv('test_result.csv')
            failed = len(df[df['Alarm'] == False])
            self.progress.emit(100, "Done!")
            self.finished.emit(end_t - start_t, failed, len(df))
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current, total, msg):
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
        self.setWindowTitle("Smoke Detection Simulation System  v3.1")
        self.setMinimumSize(1100, 700)
        self.resize(1380, 880)
        self._apply_theme()

        central = QWidget()
        self.setCentralWidget(central)
        main_v = QVBoxLayout(central)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        self._create_toolbar()
        self._create_tabs(main_v)
        self.statusBar().showMessage("Ready")
        self._status_label = QLabel("Not Ready")
        self.statusBar().addPermanentWidget(self._status_label)
        self._build_pages()

    def _apply_theme(self):
        dark = QPalette()
        dark.setColor(QPalette.Window, QColor(45, 45, 45))
        dark.setColor(QPalette.WindowText, Qt.white)
        dark.setColor(QPalette.Base, QColor(30, 30, 30))
        dark.setColor(QPalette.AlternateBase, QColor(38, 38, 38))
        dark.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
        dark.setColor(QPalette.ToolTipText, Qt.white)
        dark.setColor(QPalette.Text, Qt.white)
        dark.setColor(QPalette.Button, QColor(60, 60, 60))
        dark.setColor(QPalette.ButtonText, Qt.white)
        dark.setColor(QPalette.BrightText, Qt.red)
        dark.setColor(QPalette.Highlight, QColor(0, 120, 212))
        dark.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(dark)
        font = QFont(); font.setPointSize(9); font.setFamily("Segoe UI")
        QApplication.setFont(font)
        QApplication.instance().setStyleSheet("""
            QLabel { font-size: 9pt; }
            QPushButton { font-size: 9pt; min-height: 30px; padding: 4px 12px; }
            QGroupBox { font-size: 9pt; font-weight: bold; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QTextEdit { font-size: 9pt; }
            QComboBox { font-size: 9pt; min-height: 26px; }
            QSpinBox, QDoubleSpinBox { font-size: 9pt; min-height: 26px; }
            QSlider::groove:horizontal { height: 6px; }
            QProgressBar { font-size: 9pt; min-height: 22px; text-align: center; }
            QTableWidget { font-size: 9pt; }
            QHeaderView::section { font-size: 9pt; padding: 6px; }
            QTabBar::tab { font-size: 9pt; padding: 8px 20px; }
            QToolBar { background: #383838; border: none; padding: 4px; spacing: 6px; }
            QToolButton { background: transparent; border: none; font-size: 9pt; padding: 4px 8px; }
            QToolButton:hover { background: #505050; border-radius: 3px; }
        """)

    def _create_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))

        b_open = QToolButton()
        b_open.setIcon(_make_icon("#ffcc80", _icon_open))
        b_open.setText("Open Config")
        b_open.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b_open.clicked.connect(self._open_config)

        b_model = QToolButton()
        b_model.setIcon(_make_icon("#80bfff", _icon_config))
        b_model.setText("Load Model")
        b_model.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b_model.clicked.connect(self._open_model)

        b_run = QToolButton()
        b_run.setIcon(_make_icon("#10b010", _icon_play))
        b_run.setText("Run")
        b_run.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b_run.clicked.connect(self._run_simulation)

        self.b_stop = QToolButton()
        self.b_stop.setIcon(_make_icon("#e01010", _icon_stop))
        self.b_stop.setText("Stop")
        self.b_stop.setEnabled(False)
        self.b_stop.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.b_stop.clicked.connect(self._stop_simulation)

        b_chart = QToolButton()
        b_chart.setIcon(_make_icon("#a0d0ff", _icon_chart))
        b_chart.setText("Chart")
        b_chart.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b_chart.clicked.connect(self._show_chart)

        b_export = QToolButton()
        b_export.setIcon(_make_icon("#a0d0ff", _icon_export))
        b_export.setText("Export")
        b_export.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b_export.clicked.connect(self._export_results)

        tb.addWidget(b_open)
        tb.addSeparator()
        tb.addWidget(b_run)
        tb.addWidget(self.b_stop)
        tb.addSeparator()
        tb.addWidget(b_chart)
        tb.addWidget(b_export)

    def _create_tabs(self, parent_layout):
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3c3c3c; background: #2d2d2d; }
            QTabBar::tab { background: #383838; color: #cccccc; border: 1px solid #3c3c3c; padding: 8px 24px; margin-right: 2px; }
            QTabBar::tab:selected { background: #2d2d2d; color: white; border-bottom: 2px solid #0078d4; font-weight: bold; }
            QTabBar::tab:hover { background: #404040; }
        """)
        parent_layout.addWidget(self.tab_widget)

    def _build_pages(self):
        self.tab_widget.addTab(self._make_sim_page(), "Simulation")
        self.tab_widget.addTab(self._make_result_page(), "Results")
        self.tab_widget.addTab(self._make_settings_page(), "Settings")
        self.tab_widget.addTab(self._make_help_page(), "Help")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    # ==================== 仿真页面 ====================

    def _make_sim_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 左：配置
        left = QWidget()
        left.setStyleSheet("background: #2d2d2d; border: 1px solid #3c3c3c; border-radius: 3px;")
        ll = QVBoxLayout(left); ll.setContentsMargins(12, 12, 12, 12)
        ll.addWidget(QLabel("[ Simulation Configuration ]"))
        ll.children()

        cfg_g = QGroupBox("Configuration File")
        cgl = QVBoxLayout()
        self.path_label = QLabel("No file loaded")
        self.path_label.setStyleSheet("color: #888;")
        cgl.addWidget(self.path_label)
        btn = QPushButton("Open..."); btn.clicked.connect(self._open_config)
        cgl.addWidget(btn)
        cfg_g.setLayout(cgl); ll.addWidget(cfg_g)

        model_g = QGroupBox("Prediction Model")
        mgl = QVBoxLayout()
        self.model_label = QLabel("No model loaded")
        self.model_label.setStyleSheet("color: #888;")
        mgl.addWidget(self.model_label)
        btn2 = QPushButton("Load Model..."); btn2.clicked.connect(self._open_model)
        mgl.addWidget(btn2)
        model_g.setLayout(mgl); ll.addWidget(model_g)

        preview_g = QGroupBox("Config Preview")
        pgl = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText("No configuration loaded.\n\nPlease load inputs.json first.")
        self.preview_text.setStyleSheet("background: #1e1e1e; color: #aaa; border: none;")
        pgl.addWidget(self.preview_text)
        preview_g.setLayout(pgl); ll.addWidget(preview_g)
        ll.addStretch()
        layout.addWidget(left, 3)

        # 中：可视化
        center = QWidget()
        center.setStyleSheet("background: #2d2d2d; border: 1px solid #3c3c3c; border-radius: 3px;")
        cl = QVBoxLayout(center); cl.setContentsMargins(12, 12, 12, 12)
        cl.addWidget(QLabel("[ Cargo Bay Layout ]"))
        self.cargo_widget = CargoBayWidget()
        cl.addWidget(self.cargo_widget, 1)
        layout.addWidget(center, 5)

        # 右：状态
        right = QWidget()
        right.setStyleSheet("background: #2d2d2d; border: 1px solid #3c3c3c; border-radius: 3px;")
        rl = QVBoxLayout(right); rl.setContentsMargins(12, 12, 12, 12)
        rl.addWidget(QLabel("[ Status & Control ]"))

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #555; border-radius: 3px; background: #1e1e1e; color: white; }
            QProgressBar::chunk { background: #0078d4; border-radius: 2px; }
        """)
        rl.addWidget(self.progress_bar)

        self.progress_label = QLabel("Waiting for simulation...")
        self.progress_label.setStyleSheet("color: #aaa;")
        rl.addWidget(self.progress_label)

        stats_g = QGroupBox("Statistics")
        sl = QVBoxLayout()
        self.total_label = QLabel("Total: 0"); self.total_label.setStyleSheet("color: white;")
        self.success_label = QLabel("Success: 0"); self.success_label.setStyleSheet("color: #10b010;")
        self.fail_label = QLabel("Failed: 0"); self.fail_label.setStyleSheet("color: #e01010;")
        for l in [self.total_label, self.success_label, self.fail_label]:
            sl.addWidget(l)
        stats_g.setLayout(sl); rl.addWidget(stats_g)

        self.run_btn = QPushButton("  Run Simulation")
        self.run_btn.setIcon(_make_icon("#10b010", _icon_play))
        self.run_btn.setStyleSheet("""
            QPushButton { background: #0f5c0f; color: white; border: 1px solid #10b010; border-radius: 3px; font-weight: bold; }
            QPushButton:hover { background: #0a450a; }
            QPushButton:disabled { background: #2a2a2a; color: #666; border-color: #444; }
        """)
        self.run_btn.clicked.connect(self._run_simulation)
        rl.addWidget(self.run_btn)

        self.stop_btn = QPushButton("  Stop Simulation")
        self.stop_btn.setIcon(_make_icon("#e01010", _icon_stop))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton { background: #2a2a2a; color: #aaa; border: 1px solid #555; border-radius: 3px; }
            QPushButton:hover { background: #7a1010; color: white; }
        """)
        self.stop_btn.clicked.connect(self._stop_simulation)
        rl.addWidget(self.stop_btn)

        clear_btn = QPushButton("  Clear Results")
        clear_btn.setIcon(_make_icon("#888888", _icon_clear))
        clear_btn.setStyleSheet("""
            QPushButton { background: #2a2a2a; color: #ccc; border: 1px solid #555; border-radius: 3px; }
            QPushButton:hover { background: #444; }
        """)
        clear_btn.clicked.connect(self._clear_results)
        rl.addWidget(clear_btn)
        rl.addStretch()
        layout.addWidget(right, 3)
        return page

    # ==================== 结果页面 ====================

    def _make_result_page(self):
        page = QWidget()
        layout = QVBoxLayout(page); layout.setContentsMargins(16, 16, 16, 16)

        toolbar = QHBoxLayout()
        lbl = QLabel("[ Simulation Results ]")
        lbl.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 10pt;")
        toolbar.addWidget(lbl); toolbar.addStretch()

        chart_btn = QPushButton("View Chart")
        chart_btn.setIcon(_make_icon("#80bfff", _icon_chart))
        chart_btn.clicked.connect(self._show_chart)
        toolbar.addWidget(chart_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.setIcon(_make_icon("#80bfff", _icon_export))
        export_btn.clicked.connect(self._export_results)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(["No.", "Smoke X", "Smoke Y", "SD1", "SD2", "SD3", "SD4", "Alarm"])
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setStyleSheet("""
            QTableWidget { background: #252525; alternate-background-color: #2a2a2a; color: white; gridline-color: #3c3c3c; border: 1px solid #3c3c3c; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #0078d4; }
            QHeaderView::section { background: #1e1e1e; color: white; padding: 6px; border: none; border-right: 1px solid #3c3c3c; border-bottom: 2px solid #0078d4; }
        """)
        layout.addWidget(self.result_table)

        self.empty_label = QLabel("No results yet.\n\nRun a simulation first.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #666; font-size: 11pt;")
        self.empty_label.setMinimumHeight(200)
        self.empty_label.setVisible(True)
        layout.addWidget(self.empty_label)
        return page

    # ==================== 设置页面 ====================

    def _make_settings_page(self):
        page = QWidget()
        scroll = QVBoxLayout(page); scroll.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel("[ Parameter Settings ]")
        lbl.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 10pt;")
        scroll.addWidget(lbl)

        hint = QLabel("Modify parameters and click 'Apply' to update the active configuration.")
        hint.setStyleSheet("color: #888;"); hint.setWordWrap(True)
        scroll.addWidget(hint)

        sd_g = QGroupBox("Smoke Detector Parameters")
        sdl = QGridLayout()
        sdl.addWidget(QLabel("Detector Count:"), 0, 0)
        self.sd_qty = QSpinBox(); self.sd_qty.setRange(2, 20); self.sd_qty.setValue(6); self.sd_qty.setSingleStep(2)
        sdl.addWidget(self.sd_qty, 0, 1)
        sdl.addWidget(QLabel("False Alarm Rate:"), 1, 0)
        self.sd_far = QDoubleSpinBox(); self.sd_far.setRange(0, 1); self.sd_far.setValue(0.01); self.sd_far.setDecimals(4)
        sdl.addWidget(self.sd_far, 1, 1)
        sdl.addWidget(QLabel("Sensitivity:"), 2, 0)
        self.sd_sen = QDoubleSpinBox(); self.sd_sen.setRange(0, 1); self.sd_sen.setValue(0.98); self.sd_sen.setDecimals(4)
        sdl.addWidget(self.sd_sen, 2, 1)
        sd_g.setLayout(sdl); scroll.addWidget(sd_g)

        sim_g = QGroupBox("Simulation Parameters")
        siml = QGridLayout()
        siml.addWidget(QLabel("Arrangement:"), 0, 0)
        self.sim_method = QComboBox(); self.sim_method.addItems(["center", "side"])
        siml.addWidget(self.sim_method, 0, 1)
        siml.addWidget(QLabel("Alarm Threshold (s):"), 1, 0)
        self.sim_criteria = QSpinBox(); self.sim_criteria.setRange(1, 600); self.sim_criteria.setValue(60)
        siml.addWidget(self.sim_criteria, 1, 1)
        siml.addWidget(QLabel("Forward Spacing (mm):"), 2, 0)
        self.sim_fwd = QSpinBox(); self.sim_fwd.setRange(0, 5000); self.sim_fwd.setValue(100)
        siml.addWidget(self.sim_fwd, 2, 1)
        siml.addWidget(QLabel("Aft Spacing (mm):"), 3, 0)
        self.sim_aft = QSpinBox(); self.sim_aft.setRange(0, 5000); self.sim_aft.setValue(100)
        siml.addWidget(self.sim_aft, 3, 1)
        siml.addWidget(QLabel("Centerline Offset (mm):"), 4, 0)
        self.sim_disp = QSpinBox(); self.sim_disp.setRange(0, 5000); self.sim_disp.setValue(100)
        siml.addWidget(self.sim_disp, 4, 1)
        sim_g.setLayout(siml); scroll.addWidget(sim_g)

        apply_btn = QPushButton("Apply to Configuration")
        apply_btn.setIcon(_make_icon("#0078d4", _icon_config))
        apply_btn.setStyleSheet("""
            QPushButton { background: #0078d4; color: white; border: none; border-radius: 3px; font-weight: bold; min-height: 40px; }
            QPushButton:hover { background: #005a9e; }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        scroll.addWidget(apply_btn)
        scroll.addStretch()
        return page

    # ==================== 帮助页面 ====================

    def _make_help_page(self):
        page = QWidget()
        layout = QVBoxLayout(page); layout.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel("[ Help ]")
        lbl.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 10pt;")
        layout.addWidget(lbl)

        help_text = """================================================================
        Smoke Detection Simulation System  -  User Guide  v3.1
================================================================

[ Getting Started ]

  1. Click "Open Config" in toolbar to load inputs.json
  2. Click "Load Model" to load the .model prediction file
  3. (Optional) Go to Settings tab to adjust parameters
  4. Click "Run Simulation" to start smoke diffusion simulation
  5. View results in the Results tab

[ Cargo Bay Visualization ]

  Green dots  = Channel-A detectors
  Blue dots   = Channel-B detectors

================================================================
"""
        help_box = QTextEdit()
        help_box.setReadOnly(True)
        help_box.setPlainText(help_text)
        help_box.setFont(QFont("Consolas", 9))
        help_box.setStyleSheet("QTextEdit { background: #1e1e1e; color: #cccccc; border: 1px solid #3c3c3c; padding: 10px; }")
        layout.addWidget(help_box)

        about_g = QGroupBox("About")
        about_l = QVBoxLayout()
        about_l.addWidget(QLabel("Smoke Detection Simulation System  v3.1"))
        about_l.addWidget(QLabel("Machine learning based smoke detector response prediction"))
        about_l.addWidget(QLabel("2026 Xuan Yang"))
        about_g.setLayout(about_l)
        layout.addWidget(about_g)
        return page

    def _on_tab_changed(self, index):
        names = ["Simulation", "Results", "Settings", "Help"]
        if 0 <= index < len(names):
            self.statusBar().showMessage(names[index] + " tab")

    # ==================== 事件处理 ====================

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Configuration", "", "JSON Files (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.inputs = json.load(f)
            self.path_label.setText(os.path.basename(path))
            self.path_label.setStyleSheet("color: #10b010;")
            self.sd_qty.setValue(self.inputs.get('SD_num', 6))
            self.sim_criteria.setValue(self.inputs.get('criteria', 60))
            method = self.inputs.get('arrange', {}).get('method', 'center')
            idx = self.sim_method.findText(method)
            if idx >= 0:
                self.sim_method.setCurrentIndex(idx)
            self.sim_fwd.setValue(self.inputs.get('arrange', {}).get('fwd space', 100))
            self.sim_aft.setValue(self.inputs.get('arrange', {}).get('aft space', 100))
            self.sim_disp.setValue(self.inputs.get('arrange', {}).get('displace', 100))
            info = (f"Aircraft Type: {self.inputs.get('Type', 'N/A')}\n"
                    f"Detector Count: {self.inputs.get('SD_num', 'N/A')}\n"
                    f"Cargo Bay Size: {self.inputs.get('bay_dimension', 'N/A')}\n"
                    f"Alarm Threshold: {self.inputs.get('criteria', 'N/A')}s\n"
                    f"Arrangement: {self.inputs.get('arrange', {}).get('method', 'N/A')}")
            self.preview_text.setPlainText(info)
            self._update_vis()
            if self.predictor is not None:
                self._update_status("Ready", "#10b010")
            else:
                self._update_status("Config loaded, load model next", "#ffaa00")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config:\n{str(e)}")

    def _open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Model", "", "Model Files (*.model);;All Files (*.*)")
        if not path:
            return
        try:
            self.predictor = load_model(path)
            self.model_label.setText(os.path.basename(path))
            self.model_label.setStyleSheet("color: #10b010;")
            if self.inputs is not None:
                self._update_status("Ready", "#10b010")
            else:
                self._update_status("Model loaded, load config next", "#ffaa00")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")

    def _update_vis(self):
        if self.inputs is None:
            return
        bay_dim = self.inputs['bay_dimension']
        SD_NUM = self.inputs['SD_num']
        arrange = self.inputs['arrange']
        cargobay = CargoBay(width=bay_dim[0], length=bay_dim[1], height=bay_dim[2])
        try:
            from sklearn.tree import DecisionTreeRegressor
            dummy = DecisionTreeRegressor()
        except:
            dummy = None
        dets = [Detector(dummy or 'None', name=f'SD{i+1}') for i in range(SD_NUM)]
        env = Environment(cargobay_obj=cargobay, detector_series=dets,
                          detector_qty=SD_NUM, arrange=arrange,
                          time_criteria=self.inputs['criteria'])
        det_info = [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in dets]
        self.cargo_widget.set_layout(det_info, bay_dim[0], bay_dim[1])

    def _apply_settings(self):
        if self.inputs is None:
            QMessageBox.warning(self, "Warning", "Please load configuration file first!")
            return
        sd_num = self.sd_qty.value()
        if sd_num % 2 != 0:
            sd_num -= 1
            self.sd_qty.setValue(sd_num)
        self.inputs['SD_num'] = sd_num
        self.inputs['criteria'] = self.sim_criteria.value()
        self.inputs['arrange']['method'] = self.sim_method.currentText()
        self.inputs['arrange']['fwd space'] = self.sim_fwd.value()
        self.inputs['arrange']['aft space'] = self.sim_aft.value()
        self.inputs['arrange']['displace'] = self.sim_disp.value()
        info = (f"Aircraft Type: {self.inputs.get('Type', 'N/A')}\n"
                f"Detector Count: {sd_num}\n"
                f"Cargo Bay Size: {self.inputs.get('bay_dimension', 'N/A')}\n"
                f"Alarm Threshold: {self.inputs['criteria']}s\n"
                f"Arrangement: {self.inputs['arrange']['method']}\n\n"
                f"[Settings applied successfully]")
        self.preview_text.setPlainText(info)
        self._update_status("Parameters updated", "#ffaa00")

    def _run_simulation(self):
        if self.predictor is None:
            QMessageBox.warning(self, "Warning", "Please load prediction model first!")
            return
        if self.inputs is None:
            QMessageBox.warning(self, "Warning", "Please load configuration file first!")
            return
        self._clear_table()
        self._update_status("Simulating...", "#ffaa00")
        self.progress_bar.setValue(0)
        self.progress_label.setText("Running simulation...")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.sim_thread = SimulationThread(self.inputs, self.predictor)
        self.sim_thread.progress.connect(self._on_progress)
        self.sim_thread.finished.connect(self._on_finished)
        self.sim_thread.error.connect(self._on_error)
        self.sim_thread.detector_info.connect(self._on_detector_info)
        self.sim_thread.start()

    def _on_detector_info(self, det_info):
        if self.inputs:
            bay_dim = self.inputs['bay_dimension']
            self.cargo_widget.set_layout(det_info, bay_dim[0], bay_dim[1])

    def _on_progress(self, value, msg):
        self.progress_bar.setValue(value)
        self.progress_label.setText(msg)
        QApplication.processEvents()

    def _on_finished(self, elapsed, failed, total):
        try:
            self.sim_results = pd.read_csv('test_result.csv')
        except:
            self.sim_results = None
        self._update_status("Simulation complete", "#10b010")
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Done in {elapsed:.1f}s")
        self.total_label.setText(f"Total: {total}")
        self.success_label.setText(f"Success: {total - failed}")
        self.fail_label.setText(f"Failed: {failed}")
        self._update_result_table()
        self.empty_label.setVisible(False)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.tab_widget.setCurrentIndex(1)

    def _on_error(self, msg):
        self._update_status("Error", "#e01010")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Simulation error:\n{msg}")

    def _stop_simulation(self):
        if self.sim_thread and self.sim_thread.isRunning():
            self.sim_thread.stop()
        self._update_status("Stopping...", "#ffaa00")

    def _clear_results(self):
        self._clear_table()
        self._clear_stats()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Waiting for simulation...")
        self.sim_results = None
        self.empty_label.setVisible(True)
        self._update_status("Ready", "#888888")

    def _clear_table(self):
        self.result_table.setRowCount(0)

    def _clear_stats(self):
        self.total_label.setText("Total: 0")
        self.success_label.setText("Success: 0")
        self.fail_label.setText("Failed: 0")

    def _update_status(self, text, color):
        self._status_label.setText(f"  {text}  ")
        self._status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.statusBar().showMessage(text)

    def _update_result_table(self):
        if self.sim_results is None:
            return
        sd_cols = [c for c in self.sim_results.columns if c.startswith('SD')]
        total_cols = 3 + len(sd_cols) + 1
        self.result_table.setColumnCount(total_cols)
        self.result_table.setHorizontalHeaderLabels(["No.", "Smoke X", "Smoke Y"] + sd_cols + ["Alarm"])
        self.result_table.setRowCount(len(self.sim_results))
        for idx, row in self.sim_results.iterrows():
            alarm = "Yes" if row.get('Alarm', False) else "No"
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
                    item.setForeground(QColor("#10b010" if alarm == "Yes" else "#e01010"))
                self.result_table.setItem(idx, col, item)
        self.result_table.resizeColumnsToContents()

    def _show_chart(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "Info", "Please run simulation first!")
            return
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK JP', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
            alarm_data = self.sim_results[self.sim_results['Alarm'] == True]
            fig, axes = plt.subplots(1, 2, figsize=(12, 4))
            sd_cols = [c for c in self.sim_results.columns if c.startswith('SD')]
            if len(alarm_data) > 0 and len(sd_cols) > 0:
                vals = alarm_data[sd_cols[0]].dropna()
                if len(vals) > 0:
                    axes[0].hist(vals, bins=30, color='steelblue', alpha=0.7)
                    axes[0].set_xlabel('Alarm Time (s)')
                    axes[0].set_ylabel('Count')
                    axes[0].set_title(f'{sd_cols[0]} Alarm Time Distribution')
            total = len(self.sim_results)
            failed = len(self.sim_results[self.sim_results['Alarm'] == False])
            axes[1].bar(['Success', 'Failed'], [total - failed, failed], color=['green', 'red'], alpha=0.7)
            axes[1].set_ylabel('Test Count')
            axes[1].set_title(f'Result Summary (Total: {total})')
            plt.tight_layout()
            dialog = QDialog(self)
            dialog.setWindowTitle("Simulation Results Chart")
            dialog.resize(900, 500)
            dl = QVBoxLayout(dialog)
            dl.addWidget(FigureCanvasQTAgg(fig))
            dialog.exec()
        except ImportError:
            QMessageBox.information(self, "Info", "matplotlib not installed:\npip install matplotlib")

    def _export_results(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "Info", "No results to export!")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Results", "simulation_result.csv", "CSV Files (*.csv);;All Files (*.*)")
        if path:
            try:
                self.sim_results.to_csv(path, index=False)
                QMessageBox.information(self, "Success", f"Results saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Save failed:\n{str(e)}")


# ==================== 主程序入口 ====================

def main():
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    os.environ.setdefault("QT_SCALE_FACTOR", "2")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "Passthrough")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
