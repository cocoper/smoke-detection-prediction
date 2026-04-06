# -*- coding:utf-8 -*-
"""
飞机货舱烟雾检测仿真系统 v4.0 (PySide6)

经典 Windows 原生风格界面：
  - 浅灰背景、直角控件、无圆角
  - 经典 Windows 菜单栏
  - Tab 页 + 日志区 + 状态栏
  - 纯中文界面

依赖安装: pip install PySide6 pandas numpy scikit-learn
运行方式: python gui_pyside6_winstyle.py
"""
import os, sys, json, pickle, math, warnings
import numpy as np
from time import time
import pandas as pd

warnings.filterwarnings('ignore')

# ==================== sklearn 旧模型兼容 ====================
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
    QPushButton, QLabel, QTextEdit, QSlider, QComboBox,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QGroupBox, QGridLayout,
    QSpinBox, QDoubleSpinBox, QTabWidget, QMenuBar, QMenu,
    QStatusBar, QFrame, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QAction, QKeySequence


# ==================== 货舱可视化 ====================

class CargoBayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background: #ffffff; border: 1px solid #808080;")
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
            p.setPen(QPen(QColor(0, 0, 0)))
            p.setFont(QFont("MS Sans Serif", 11))
            p.drawText(self.rect(), Qt.AlignCenter, "\u52a0\u8f7d\u914d\u7f6e\u540e\u663e\u793a\u8d27\u8239\u5e03\u5c40")
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

        # \u6807\u9898
        p.setPen(QPen(QColor(0, 0, 0)))
        p.setFont(QFont("MS Sans Serif", 10, QFont.Bold))
        p.drawText(int(w/2-150), 28, f"\u8d27\u8239 {self.bay_length} x {self.bay_width} mm  |  {len(self.detectors)} \u4e2a\u63a2\u6d4b\u5668")

        # \u8d27\u8239\u80cc\u666f
        p.setPen(QPen(QColor(0, 0, 128), 2))
        p.setBrush(QBrush(QColor(224, 224, 224)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        # \u7f51\u683c
        p.setPen(QPen(QColor(160, 160, 160), 1, Qt.DashLine))
        for g in range(2000, int(self.bay_length), 2000):
            gx = int(ox + g * s)
            p.drawLine(gx, int(oy), gx, int(oy + bh))
        p.setPen(QPen(QColor(100, 100, 100)))
        p.setFont(QFont("MS Sans Serif", 8))
        for g in range(0, int(self.bay_length)+1, 2000):
            gx = int(ox + g * s)
            p.drawText(gx - 10, int(oy + bh + 16), str(g))

        # \u4e2d\u7ebf
        cy = int(oy + bh / 2)
        p.setPen(QPen(QColor(128, 128, 128), 1, Qt.DashLine))
        p.drawLine(int(ox), cy, int(ox + bw), cy)

        # \u63a2\u6d4b\u5668
        for x, y, name, ch in self.detectors:
            dx, dy = ox + x * s, oy + y * s
            if ch == 0:
                c = QColor(0, 160, 0); label = f"{name}(A)"
            else:
                c = QColor(0, 0, 200); label = f"{name}(B)"
            p.setPen(QPen(c, 1))
            p.setBrush(QBrush(c))
            p.drawEllipse(int(dx-5), int(dy-5), 10, 10)
            p.setFont(QFont("MS Sans Serif", 8))
            p.drawText(int(dx + 7), int(dy + 4), label)

        # \u56fe\u4f8b
        lx = int(ox + bw - 115); ly = int(oy + bh - 38)
        p.setPen(QPen(QColor(0, 0, 0)))
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawRect(lx, ly, 110, 32)
        p.setPen(QPen(QColor(0, 160, 0)))
        p.setBrush(QBrush(QColor(0, 160, 0)))
        p.drawEllipse(lx+8, ly+6, 8, 8)
        p.setPen(QPen(QColor(0, 0, 0)))
        p.setFont(QFont("MS Sans Serif", 9))
        p.drawText(lx+20, ly+14, "A\u901a\u9053")
        p.setPen(QPen(QColor(0, 0, 200)))
        p.setBrush(QBrush(QColor(0, 0, 200)))
        p.drawEllipse(lx+8, ly+20, 8, 8)
        p.setPen(QPen(QColor(0, 0, 0)))
        p.drawText(lx+20, ly+28, "B\u901a\u9053")
        p.end()


# ==================== \u4eff\u771f\u7ebf\u7a0b ====================

class SimulationThread(QThread):
    progress = Signal(int, str)
    finished = Signal(float, int, int)
    error = Signal(str)
    detector_info = Signal(list)
    log_msg = Signal(str)

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
                cargobay_obj=cargobay, detector_series=dets,
                detector_qty=SD_NUM, arrange=arrange,
                time_criteria=self.inputs['criteria']
            )
            total_tests = math.ceil(bay_dim[1] / 1000) * math.ceil(bay_dim[0] / 1000)
            self._progress_total = total_tests
            env._progress_callback = self._on_progress
            env._stop_flag = lambda: self._stop_flag

            det_info = [(sd.x_pos, sd.y_pos, sd.name, sd.channel_id) for sd in dets]
            self.detector_info.emit(det_info)

            # \u6253\u5370\u8d44\u6e90\u4fe1\u606f
            for d in dets:
                self.log_msg.emit(f"[{d.name}] X={d.x_pos:.1f} Y={d.y_pos:.1f} Z={d.z_pos:.1f}")

            start_t = time()
            env.run(mode='all')
            end_t = time()
            df = pd.read_csv('test_result.csv')
            failed = len(df[df['Alarm'] == False])
            self.log_msg.emit(f"\u4eff\u771f\u5b8c\u6210\uff01\u8017\u65f6 {end_t-start_t:.1f}\u79d2\uff0c\u5171 {len(df)} \u6b21\u6d4b\u8bd5\uff0c\u5931\u8d25 {failed} \u6b21")
            self.progress.emit(100, "\u5b8c\u6210")
            self.finished.emit(end_t - start_t, failed, len(df))
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current, total, msg):
        pct = int(current / max(self._progress_total, 1) * 95) if self._progress_total > 0 else 0
        self.progress.emit(min(pct, 95), msg)

    def stop(self):
        self._stop_flag = True


# ==================== \u4e3b\u7a97\u53e3 ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.predictor = None
        self.inputs = None
        self.sim_thread = None
        self.sim_results = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v4.0")
        self.setMinimumSize(1100, 760)
        self.resize(1380, 900)

        # -------- \u7c97\u7c9f Windows \u98ce\u683c --------
        self._apply_classic_theme()

        central = QWidget()
        self.setCentralWidget(central)
        main_v = QVBoxLayout(central)
        main_v.setContentsMargins(2, 2, 2, 2)
        main_v.setSpacing(0)

        # \u83dc\u5355\u680f
        self._create_menu()

        # \u6807\u7b7e\u9875
        self._create_tabs(main_v)

        # \u65e5\u5fd7\u533a
        self._create_log_area(main_v)

        # \u72b6\u6001\u680f
        self.statusBar().showMessage("\u5c31\u7eea")
        self._create_statusbar()

        # \u6784\u5efa\u9875\u9762
        self._build_pages()

    def _apply_classic_theme(self):
        # \u7c97\u7c9f Windows 2000/XP \u6df7\u5408\u98a8\u683c\uff08\u6df7\u5408\u6837\u5f0f\uff09
        self.setStyleSheet("""
            QMainWindow {
                background: #c0c0c0;
            }
            QWidget {
                background: #c0c0c0;
                font-family: "MS Sans Serif";
                font-size: 11px;
                color: #000000;
            }
            QMenuBar {
                background: #c0c0c0;
                border-bottom: 1px solid #808080;
            }
            QMenuBar::item {
                background: #c0c0c0;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background: #000080;
                color: #ffffff;
            }
            QMenu {
                background: #c0c0c0;
                border: 1px solid #808080;
            }
            QMenu::item {
                padding: 4px 24px;
            }
            QMenu::item:selected {
                background: #000080;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #808080;
                margin: 4px 0;
            }
            QLabel {
                background: transparent;
                color: #000000;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #808080;
                border-radius: 0px;
                margin-top: 8px;
                padding-top: 8px;
                background: #c0c0c0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QTextEdit, QListWidget {
                background: #ffffff;
                border: 1px solid #808080;
                border-radius: 0px;
                font-family: "Fixedsys";
                font-size: 11px;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #808080;
                border-radius: 0px;
                gridline-color: #c0c0c0;
            }
            QTableWidget::item {
                border: none;
                border-bottom: 1px solid #e0e0e0;
            }
            QTableWidget::item:selected {
                background: #000080;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #c0c0c0;
                border: none;
                border-right: 1px solid #808080;
                border-bottom: 1px solid #808080;
                padding: 4px;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #808080;
                border-radius: 0px;
                background: #ffffff;
                text-align: center;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background: #000080;
            }
            QTabWidget::pane {
                border: 1px solid #808080;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #c0c0c0;
                border: 1px solid #808080;
                border-bottom: none;
                padding: 6px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: 1px solid #ffffff;
                font-weight: bold;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #808080;
                border-radius: 0px;
                background: #ffffff;
                min-height: 22px;
                padding: 1px 4px;
            }
            QComboBox::drop-down {
                border: none;
                border-left: 1px solid #808080;
                width: 16px;
            }
            QComboBox::down-arrow {
                width: 16px;
                height: 16px;
            }
            QStatusBar {
                background: #c0c0c0;
                border-top: 1px solid #808080;
            }
        """)

    # ==================== \u83dc\u5355\u680f ====================

    def _create_menu(self):
        menubar = self.menuBar()

        # \u6587\u4ef6
        m_file = menubar.addMenu("\u6587\u4ef6(&F)")
        a_open = QAction("\u6253\u5f00\u914d\u7f6e...(&O)", self)
        a_open.setShortcut(QKeySequence("Ctrl+O"))
        a_open.triggered.connect(self._open_config)
        m_file.addAction(a_open)

        a_model = QAction("\u52a0\u8f7d\u6a21\u578b...(&M)", self)
        a_model.setShortcut(QKeySequence("Ctrl+M"))
        a_model.triggered.connect(self._open_model)
        m_file.addAction(a_model)

        m_file.addSeparator()

        a_export = QAction("\u5bfc\u51fa\u7ed3\u679c...(&E)", self)
        a_export.setShortcut(QKeySequence("Ctrl+E"))
        a_export.triggered.connect(self._export_results)
        m_file.addAction(a_export)

        m_file.addSeparator()

        a_exit = QAction("\u9000\u51fa(&X)", self)
        a_exit.setShortcut(QKeySequence("Alt+F4"))
        a_exit.triggered.connect(self.close)
        m_file.addAction(a_exit)

        # \u4eff\u771f
        m_sim = menubar.addMenu("\u4eff\u771f(&S)")
        a_run = QAction("\u5f00\u59cb\u4eff\u771f(&R)", self)
        a_run.setShortcut(QKeySequence("F5"))
        a_run.triggered.connect(self._run_simulation)
        m_sim.addAction(a_run)

        a_stop = QAction("\u505c\u6b62\u4eff\u771f(&S)", self)
        a_stop.setShortcut(QKeySequence("Shift+F5"))
        a_stop.triggered.connect(self._stop_simulation)
        m_sim.addAction(a_stop)

        m_sim.addSeparator()

        a_clear = QAction("\u6e05\u9664\u7ed3\u679c(&C)", self)
        a_clear.triggered.connect(self._clear_results)
        m_sim.addAction(a_clear)

        # \u89c6\u56fe
        m_view = menubar.addMenu("\u89c6\u56fe(&V)")
        a_tab0 = QAction("\u4eff\u771f\u9875", self)
        a_tab0.triggered.connect(lambda: self.tab_widget.setCurrentIndex(0))
        m_view.addAction(a_tab0)

        a_tab1 = QAction("\u7ed3\u679c\u9875", self)
        a_tab1.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))
        m_view.addAction(a_tab1)

        a_tab2 = QAction("\u8bbe\u7f6e\u9875", self)
        a_tab2.triggered.connect(lambda: self.tab_widget.setCurrentIndex(2))
        m_view.addAction(a_tab2)

        # \u5e2e\u52a9
        m_help = menubar.addMenu("\u5e2e\u52a9(&H)")
        a_help = QAction("\u4f7f\u7528\u8bf4\u660e(&H)", self)
        a_help.triggered.connect(self._show_help)
        m_help.addAction(a_help)

        m_help.addSeparator()

        a_about = QAction("\u5173\u4e8e(&A)", self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

    # ==================== \u6807\u7b7e\u9875 ====================

    def _create_tabs(self, parent_layout):
        self.tab_widget = QTabWidget()
        parent_layout.addWidget(self.tab_widget)

    # ==================== \u65e5\u5fd7\u533a ====================

    def _create_log_area(self, parent_layout):
        log_frame = QFrame()
        log_frame.setStyleSheet("background: #c0c0c0; border-top: 1px solid #808080;")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.setSpacing(2)

        lbl = QLabel("\u65e5\u5fd7:")
        lbl.setStyleSheet("font-weight: bold; background: transparent;")
        log_layout.addWidget(lbl)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setPlainText("\u7cfb\u7edf\u5df2\u542f\u52a8\uff0c\u8bf7\u52a0\u8f7d\u914d\u7f6e\u6587\u4ef6\u548c\u6a21\u578b\u6587\u4ef6\u5f00\u59cb\u4eff\u771f\u3002")
        log_layout.addWidget(self.log_text)
        parent_layout.addWidget(log_frame)

    # ==================== \u72b6\u6001\u680f ====================

    def _create_statusbar(self):
        self.status_ready = QLabel("\u5c31\u7eea")
        self.status_ready.setStyleSheet("color: #008000; font-weight: bold; padding: 0 8px;")
        self.statusBar().addPermanentWidget(self.status_ready)

        self.status_label = QLabel("\u672a\u52a0\u8f7d\u914d\u7f6e")
        self.statusBar().addPermanentWidget(self.status_label, 1)

    def _append_log(self, msg):
        self.log_text.append(msg)
        self.log_text.ensureCursorVisible()

    # ==================== \u6784\u5efa\u56db\u4e2a Tab ====================

    def _build_pages(self):
        self.tab_widget.addTab(self._make_sim_page(), "\u4eff\u771f")
        self.tab_widget.addTab(self._make_result_page(), "\u7ed3\u679c")
        self.tab_widget.addTab(self._make_settings_page(), "\u8bbe\u7f6e")
        self.tab_widget.addTab(self._make_help_page(), "\u5e2e\u52a9")

    # ==================== \u4eff\u771f\u9875\u9762 ====================

    def _make_sim_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # \u5de6\uff1a\u914d\u7f6e\u9762\u677f
        left = QWidget()
        left.setStyleSheet("background: #c0c0c0;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)

        cfg_g = QGroupBox("\u914d\u7f6e\u6587\u4ef6")
        cgl = QVBoxLayout()
        self.path_label = QLabel("\u672a\u52a0\u8f7d")
        cgl.addWidget(self.path_label)
        btn = QPushButton("\u6253\u5f00...")
        btn.setMinimumHeight(28)
        btn.clicked.connect(self._open_config)
        cgl.addWidget(btn)
        cfg_g.setLayout(cgl)
        ll.addWidget(cfg_g)

        model_g = QGroupBox("\u9884\u6d4b\u6a21\u578b")
        mgl = QVBoxLayout()
        self.model_label = QLabel("\u672a\u52a0\u8f7d")
        mgl.addWidget(self.model_label)
        btn2 = QPushButton("\u52a0\u8f7d...")
        btn2.setMinimumHeight(28)
        btn2.clicked.connect(self._open_model)
        mgl.addWidget(btn2)
        model_g.setLayout(mgl)
        ll.addWidget(model_g)

        preview_g = QGroupBox("\u914d\u7f6e\u9884\u89c8")
        pgl = QVBoxLayout()
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlainText("\u672a\u52a0\u8f7d\u914d\u7f6e\u6587\u4ef6\uff0c\u8bf7\u5148\u52a0\u8f7d inputs.json")
        pgl.addWidget(self.preview_text)
        preview_g.setLayout(pgl)
        ll.addWidget(preview_g)
        ll.addStretch()
        layout.addWidget(left, 3)

        # \u4e2d\uff1a\u53ef\u89c6\u5316
        center = QWidget()
        center.setStyleSheet("background: #c0c0c0;")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(4, 4, 4, 4)

        vis_g = QGroupBox("\u8d27\u8239\u5e03\u5c40\u53ef\u89c6\u5316")
        vgl = QVBoxLayout()
        self.cargo_widget = CargoBayWidget()
        vgl.addWidget(self.cargo_widget)
        vis_g.setLayout(vgl)
        cl.addWidget(vis_g)
        layout.addWidget(center, 5)

        # \u53f3\uff1a\u72b6\u6001\u4e0e\u63a7\u5236
        right = QWidget()
        right.setStyleSheet("background: #c0c0c0;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)

        ctrl_g = QGroupBox("\u8fd0\u884c\u63a7\u5236")
        ctrl = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        ctrl.addWidget(QLabel("\u8fdb\u5ea6:"))
        ctrl.addWidget(self.progress_bar)

        self.progress_label = QLabel("\u7b49\u5f85\u4eff\u771f...")
        ctrl.addWidget(self.progress_label)

        stats_g = QGroupBox("\u7edf\u8ba1\u4fe1\u606f")
        sl = QVBoxLayout()
        self.total_label = QLabel("\u603b\u6d4b\u8bd5\u6570: 0")
        self.success_label = QLabel("\u6210\u529f: 0")
        self.success_label.setStyleSheet("color: #008000;")
        self.fail_label = QLabel("\u5931\u8d25: 0")
        self.fail_label.setStyleSheet("color: #ff0000;")
        for l in [self.total_label, self.success_label, self.fail_label]:
            sl.addWidget(l)
        stats_g.setLayout(sl)
        ctrl.addWidget(stats_g)

        self.run_btn = QPushButton("\u5f00\u59cb\u4eff\u771f")
        self.run_btn.setMinimumHeight(36)
        self.run_btn.clicked.connect(self._run_simulation)
        ctrl.addWidget(self.run_btn)

        self.stop_btn = QPushButton("\u505c\u6b62\u4eff\u771f")
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_simulation)
        ctrl.addWidget(self.stop_btn)

        clear_btn = QPushButton("\u6e05\u9664\u7ed3\u679c")
        clear_btn.setMinimumHeight(28)
        clear_btn.clicked.connect(self._clear_results)
        ctrl.addWidget(clear_btn)

        ctrl_g.setLayout(ctrl)
        rl.addWidget(ctrl_g)
        rl.addStretch()
        layout.addWidget(right, 3)
        return page

    # ==================== \u7ed3\u679c\u9875\u9762 ====================

    def _make_result_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)

        toolbar = QHBoxLayout()
        lbl = QLabel("\u4eff\u771f\u7ed3\u679c\u6570\u636e")
        lbl.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()

        chart_btn = QPushButton("\u67e5\u770b\u56fe\u8868")
        chart_btn.setMinimumHeight(28)
        chart_btn.clicked.connect(self._show_chart)
        toolbar.addWidget(chart_btn)

        export_btn = QPushButton("\u5bfc\u51fa CSV")
        export_btn.setMinimumHeight(28)
        export_btn.clicked.connect(self._export_results)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels(
            ["\u5e8f\u53f7", "\u98d8\u96feX", "\u98d8\u96feY", "SD1", "SD2", "SD3", "SD4", "\u62a5\u8b66"])
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.result_table)

        self.empty_label = QLabel("\u6682\u65e0\u4eff\u771f\u7ed3\u679c\uff0c\u8bf7\u5148\u8fd0\u884c\u4eff\u771f")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #808080; font-size: 13px;")
        self.empty_label.setMinimumHeight(200)
        self.empty_label.setVisible(True)
        layout.addWidget(self.empty_label)
        return page

    # ==================== \u8bbe\u7f6e\u9875\u9762 ====================

    def _make_settings_page(self):
        page = QWidget()
        scroll = QVBoxLayout(page)
        scroll.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("\u53c2\u6570\u8bbe\u7f6e")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        scroll.addWidget(lbl)

        hint = QLabel("\u4fee\u6539\u53c2\u6570\u540e\u70b9\u51fb\u300a\u5e94\u7528\u914d\u7f6e\u300b\uff0c\u6216\u76f4\u63a5\u5f00\u59cb\u4eff\u771f\u65f6\u81ea\u52a8\u5e94\u7528\u3002")
        hint.setStyleSheet("color: #505050;")
        hint.setWordWrap(True)
        scroll.addWidget(hint)

        sd_g = QGroupBox("\u63a2\u6d4b\u5668\u53c2\u6570")
        sdl = QGridLayout()
        sdl.addWidget(QLabel("\u63a2\u6d4b\u5668\u6570\u91cf:"), 0, 0)
        self.sd_qty = QSpinBox()
        self.sd_qty.setRange(2, 20)
        self.sd_qty.setValue(6)
        self.sd_qty.setSingleStep(2)
        sdl.addWidget(self.sd_qty, 0, 1)

        sdl.addWidget(QLabel("\u8bef\u62a5\u7387:"), 1, 0)
        self.sd_far = QDoubleSpinBox()
        self.sd_far.setRange(0, 1)
        self.sd_far.setValue(0.01)
        self.sd_far.setDecimals(4)
        sdl.addWidget(self.sd_far, 1, 1)

        sdl.addWidget(QLabel("\u7075\u654f\u5ea6:"), 2, 0)
        self.sd_sen = QDoubleSpinBox()
        self.sd_sen.setRange(0, 1)
        self.sd_sen.setValue(0.98)
        self.sd_sen.setDecimals(4)
        sdl.addWidget(self.sd_sen, 2, 1)
        sd_g.setLayout(sdl)
        scroll.addWidget(sd_g)

        sim_g = QGroupBox("\u4eff\u771f\u53c2\u6570")
        siml = QGridLayout()

        siml.addWidget(QLabel("\u6392\u5217\u65b9\u5f0f:"), 0, 0)
        self.sim_method = QComboBox()
        self.sim_method.addItems(["center", "side"])
        siml.addWidget(self.sim_method, 0, 1)

        siml.addWidget(QLabel("\u62a5\u8b66\u65f6\u95f4\u9608\u503c(\u79d2):"), 1, 0)
        self.sim_criteria = QSpinBox()
        self.sim_criteria.setRange(1, 600)
        self.sim_criteria.setValue(60)
        siml.addWidget(self.sim_criteria, 1, 1)

        siml.addWidget(QLabel("\u524d\u58c1\u677f\u95f4\u8ddd(mm):"), 2, 0)
        self.sim_fwd = QSpinBox()
        self.sim_fwd.setRange(0, 5000)
        self.sim_fwd.setValue(100)
        siml.addWidget(self.sim_fwd, 2, 1)

        siml.addWidget(QLabel("\u540e\u58c1\u677f\u95f4\u8ddd(mm):"), 3, 0)
        self.sim_aft = QSpinBox()
        self.sim_aft.setRange(0, 5000)
        self.sim_aft.setValue(100)
        siml.addWidget(self.sim_aft, 3, 1)

        siml.addWidget(QLabel("\u4e2d\u7ebf\u504f\u79fb(mm):"), 4, 0)
        self.sim_disp = QSpinBox()
        self.sim_disp.setRange(0, 5000)
        self.sim_disp.setValue(100)
        siml.addWidget(self.sim_disp, 4, 1)
        sim_g.setLayout(siml)
        scroll.addWidget(sim_g)

        apply_btn = QPushButton("\u5e94\u7528\u5230\u914d\u7f6e")
        apply_btn.setMinimumHeight(40)
        apply_btn.clicked.connect(self._apply_settings)
        scroll.addWidget(apply_btn)
        scroll.addStretch()
        return page

    # ==================== \u5e2e\u52a9\u9875\u9762 ====================

    def _make_help_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        lbl = QLabel("\u4f7f\u7528\u8bf4\u660e")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl)

        help_text = """========================================================
         \u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf  v4.0  \u4f7f\u7528\u8bf4\u660e
========================================================

【\u4f7f\u7528\u6b65\u9aa4】

  1. \u70b9\u51fb"\u6587\u4ef6 \u2192 \u6253\u5f00\u914d\u7f6e"...\u52a0\u8f7d inputs.json
  2. \u70b9\u51fb"\u6587\u4ef6 \u2192 \u52a0\u8f7d\u6a21\u578b"...\u52a0\u8f7d .model \u6587\u4ef6
  3. (\u53ef\u9009)\u8bbe\u7f6e\u9875\u4fee\u6539\u53c2\u6570\u540e\u70b9\u51fb"\u5e94\u7528\u5230\u914d\u7f6e"
  4. \u70b9\u51fb"\u4eff\u771f \u2192 \u5f00\u59cb\u4eff\u771f" \u6216\u6309 F5 \u8fd0\u884c\u4eff\u771f
  5. \u7ed3\u679c\u9875\u67e5\u770b\u6570\u636e\u7ed3\u679c

【\u8d27\u8239\u53ef\u89c6\u5316】

  \u7eff\u8272\u5706\u70b9  = A\u901a\u9053\u63a2\u6d4b\u5668
  \u84dd\u8272\u5706\u70b9  = B\u901a\u9053\u63a2\u6d4b\u5668

【\u952e\u76d8\u5feb\u6377\u65b9】

  Ctrl+O  \u6253\u5f00\u914d\u7f6e
  Ctrl+E  \u5bfc\u51fa\u7ed3\u679c
  F5      \u5f00\u59cb\u4eff\u771f
  Shift+F5 \u505c\u6b62\u4eff\u771f

========================================================
"""
        help_box = QTextEdit()
        help_box.setReadOnly(True)
        help_box.setPlainText(help_text)
        help_box.setFont(QFont("Fixedsys", 10))
        layout.addWidget(help_box)

        about_g = QGroupBox("\u5173\u4e8e")
        about_l = QVBoxLayout()
        about_l.addWidget(QLabel("\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v4.0"))
        about_l.addWidget(QLabel("\u57fa\u4e8e\u673a\u5668\u5b66\u4e60\u7684\u98d8\u96fe\u63a2\u6d4b\u5668\u54cd\u5e94\u65f6\u95f4\u9884\u6d4b"))
        about_l.addWidget(QLabel("2026 Xuan Yang"))
        about_g.setLayout(about_l)
        layout.addWidget(about_g)
        return page

    # ==================== \u83dc\u5355\u64cd\u4f5c ====================

    def _show_help(self):
        self.tab_widget.setCurrentIndex(3)

    def _show_about(self):
        QMessageBox.about(self, "\u5173\u4e8e",
            "\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v4.0\n\n"
            "\u57fa\u4e8e\u673a\u5668\u5b66\u4e60\u7684\u98d8\u96fe\u63a2\u6d4b\u5668\u54cd\u5e94\u65f6\u95f4\u9884\u6d4b\n\n"
            "2026 Xuan Yang")

    # ==================== \u4e8b\u4ef6\u5904\u7406 ====================

    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "\u6253\u5f00\u914d\u7f6e\u6587\u4ef6", "", "JSON \u6587\u4ef6 (*.json);;\u6240\u6709\u6587\u4ef6 (*.*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.inputs = json.load(f)
            self.path_label.setText(os.path.basename(path))
            self.path_label.setStyleSheet("color: #008000;")
            self.sd_qty.setValue(self.inputs.get('SD_num', 6))
            self.sim_criteria.setValue(self.inputs.get('criteria', 60))
            method = self.inputs.get('arrange', {}).get('method', 'center')
            idx = self.sim_method.findText(method)
            if idx >= 0:
                self.sim_method.setCurrentIndex(idx)
            self.sim_fwd.setValue(self.inputs.get('arrange', {}).get('fwd space', 100))
            self.sim_aft.setValue(self.inputs.get('arrange', {}).get('aft space', 100))
            self.sim_disp.setValue(self.inputs.get('arrange', {}).get('displace', 100))
            info = (f"\u98d8\u673a\u578b\u53f7: {self.inputs.get('Type', 'N/A')}\n"
                    f"\u63a2\u6d4b\u5668\u6570\u91cf: {self.inputs.get('SD_num', 'N/A')}\n"
                    f"\u8d27\u8239\u5c3a\u5bf8: {self.inputs.get('bay_dimension', 'N/A')}\n"
                    f"\u62a5\u8b66\u9608\u503c: {self.inputs.get('criteria', 'N/A')}\u79d2\n"
                    f"\u6392\u5217\u65b9\u5f0f: {self.inputs.get('arrange', {}).get('method', 'N/A')}")
            self.preview_text.setPlainText(info)
            self._update_vis()
            self._append_log(f"\u914d\u7f6e\u52a0\u8f7d\u6210\u529f: {os.path.basename(path)}")
            if self.predictor is not None:
                self._update_status("\u5c31\u7eea", "\u5c31\u7eea", "#008000")
            else:
                self._update_status("\u914d\u7f6e\u5df2\u52a0\u8f7d\uff0c\u8bf7\u52a0\u8f7d\u6a21\u578b", "\u914d\u7f6e\u5df2\u52a0\u8f7d", "#808080")
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u52a0\u8f7d\u914d\u7f6e\u5931\u8d25:\n{str(e)}")

    def _open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "\u52a0\u8f7d\u6a21\u578b\u6587\u4ef6", "", "\u6a21\u578b\u6587\u4ef6 (*.model);;\u6240\u6709\u6587\u4ef6 (*.*)")
        if not path:
            return
        try:
            self.predictor = load_model(path)
            self.model_label.setText(os.path.basename(path))
            self.model_label.setStyleSheet("color: #008000;")
            self._append_log(f"\u6a21\u578b\u52a0\u8f7d\u6210\u529f: {os.path.basename(path)}")
            if self.inputs is not None:
                self._update_status("\u5c31\u7eea", "\u5c31\u7eea", "#008000")
            else:
                self._update_status("\u6a21\u578b\u5df2\u52a0\u8f7d\uff0c\u8bf7\u52a0\u8f7d\u914d\u7f6e", "\u6a21\u578b\u5df2\u52a0\u8f7d", "#808080")
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", f"\u52a0\u8f7d\u6a21\u578b\u5931\u8d25:\n{str(e)}")

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
        self._append_log(f"\u8d27\u8239\u5e03\u5c40\u5df2\u66f4\u65b0\uff0c\u5171 {len(dets)} \u4e2a\u63a2\u6d4b\u5668")

    def _apply_settings(self):
        if self.inputs is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u5148\u52a0\u8f7d\u914d\u7f6e\u6587\u4ef6\uff01")
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
        info = (f"\u98d8\u673a\u578b\u53f7: {self.inputs.get('Type', 'N/A')}\n"
                f"\u63a2\u6d4b\u5668\u6570\u91cf: {sd_num}\n"
                f"\u8d27\u8239\u5c3a\u5bf8: {self.inputs.get('bay_dimension', 'N/A')}\n"
                f"\u62a5\u8b66\u9608\u503c: {self.inputs['criteria']}\u79d2\n"
                f"\u6392\u5217\u65b9\u5f0f: {self.inputs['arrange']['method']}\n\n"
                f"[\u8bbe\u7f6e\u5df2\u5e94\u7528]")
        self.preview_text.setPlainText(info)
        self._append_log("\u53c2\u6570\u5df2\u66f4\u65b0\uff0c\u70b9\u51fb\u5f00\u59cb\u4eff\u771f\u751f\u6548")
        self._update_status("\u53c2\u6570\u5df2\u66f4\u65b0", "\u53c2\u6570\u5df2\u66f4\u65b0", "#808080")

    def _run_simulation(self):
        if self.predictor is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u5148\u52a0\u8f7d\u9884\u6d4b\u6a21\u578b\uff01")
            return
        if self.inputs is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u5148\u6253\u5f00\u914d\u7f6e\u6587\u4ef6\uff01")
            return
        self._clear_table()
        self._update_status("\u4eff\u771f\u4e2d...", "\u4eff\u771f\u4e2d...", "#0000ff")
        self.progress_bar.setValue(0)
        self.progress_label.setText("\u6b63\u5728\u8fd0\u884c\u4eff\u771f...")
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._append_log("\u2014\u2014\u4eff\u771f\u5f00\u59cb\u2014\u2014")
        self.sim_thread = SimulationThread(self.inputs, self.predictor)
        self.sim_thread.progress.connect(self._on_progress)
        self.sim_thread.finished.connect(self._on_finished)
        self.sim_thread.error.connect(self._on_error)
        self.sim_thread.detector_info.connect(self._on_detector_info)
        self.sim_thread.log_msg.connect(self._append_log)
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
        self._update_status("\u5b8c\u6210", f"\u5b8c\u6210\u2014\u8017\u65f6{elapsed:.1f}\u79d2", "#008000")
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"\u5b8c\u6210\uff01\u8017\u65f6 {elapsed:.1f}\u79d2")
        self.total_label.setText(f"\u603b\u6d4b\u8bd5\u6570: {total}")
        self.success_label.setText(f"\u6210\u529f: {total - failed}")
        self.fail_label.setText(f"\u5931\u8d25: {failed}")
        self._update_result_table()
        self.empty_label.setVisible(False)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.tab_widget.setCurrentIndex(1)
        self._append_log(f"\u2014\u2014\u4eff\u771f\u5b8c\u6210\u2014\u2014")

    def _on_error(self, msg):
        self._update_status("\u9519\u8bef", msg, "#ff0000")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._append_log(f"[\u9519\u8bef] {msg}")
        QMessageBox.critical(self, "\u9519\u8bef", f"\u4eff\u771f\u51fa\u9519:\n{msg}")

    def _stop_simulation(self):
        if self.sim_thread and self.sim_thread.isRunning():
            self.sim_thread.stop()
        self._update_status("\u6b63\u5728\u505c\u6b62", "\u6b63\u5728\u505c\u6b62...", "#808080")
        self._append_log("\u4eff\u771f\u505c\u6b62\u4e2d...")

    def _clear_results(self):
        self._clear_table()
        self._clear_stats()
        self.progress_bar.setValue(0)
        self.progress_label.setText("\u7b49\u5f85\u4eff\u771f...")
        self.sim_results = None
        self.empty_label.setVisible(True)
        self._update_status("\u5c31\u7eea", "\u5df2\u6e05\u9664", "#808080")
        self._append_log("\u7ed3\u679c\u5df2\u6e05\u9664")

    def _clear_table(self):
        self.result_table.setRowCount(0)

    def _clear_stats(self):
        self.total_label.setText("\u603b\u6d4b\u8bd5\u6570: 0")
        self.success_label.setText("\u6210\u529f: 0")
        self.fail_label.setText("\u5931\u8d25: 0")

    def _update_status(self, ready_text, status_text, color):
        self.status_ready.setText(ready_text)
        self.status_ready.setStyleSheet(f"color: {color}; font-weight: bold; padding: 0 8px;")
        self.status_label.setText(status_text)
        self.statusBar().showMessage(status_text)

    def _update_result_table(self):
        if self.sim_results is None:
            return
        sd_cols = [c for c in self.sim_results.columns if c.startswith('SD')]
        total_cols = 3 + len(sd_cols) + 1
        self.result_table.setColumnCount(total_cols)
        self.result_table.setHorizontalHeaderLabels(
            ["\u5e8f\u53f7", "\u98d8\u96feX", "\u98d8\u96feY"] + sd_cols + ["\u62a5\u8b66"])
        self.result_table.setRowCount(len(self.sim_results))
        for idx, row in self.sim_results.iterrows():
            alarm = "\u662f" if row.get('Alarm', False) else "\u5426"
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
                    item.setForeground(QColor("#008000" if alarm == "\u662f" else "#ff0000"))
                self.result_table.setItem(idx, col, item)
        self.result_table.resizeColumnsToContents()

    def _show_chart(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u5148\u8fd0\u884c\u4eff\u771f\uff01")
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
                    axes[0].set_xlabel('\u62a5\u8b66\u65f6\u95f4 (s)')
                    axes[0].set_ylabel('\u983b\u6b21')
                    axes[0].set_title(f'{sd_cols[0]} \u62a5\u8b66\u65f6\u95f4\u5206\u5e03')
            total = len(self.sim_results)
            failed = len(self.sim_results[self.sim_results['Alarm'] == False])
            axes[1].bar(['\u6210\u529f', '\u5931\u8d25'], [total - failed, failed], color=['green', 'red'], alpha=0.7)
            axes[1].set_ylabel('\u6d4b\u8bd5\u6570')
            axes[1].set_title(f'\u7ed3\u679c\u7edf\u8ba1 (\u5171{total}\u6b21)')
            plt.tight_layout()
            dialog = QDialog(self)
            dialog.setWindowTitle("\u4eff\u771f\u7ed3\u679c\u56fe\u8868")
            dialog.resize(900, 500)
            dl = QVBoxLayout(dialog)
            dl.addWidget(FigureCanvasQTAgg(fig))
            dialog.exec()
        except ImportError:
            QMessageBox.information(self, "\u63d0\u793a", "\u672a\u5b89\u88c5 matplotlib:\npip install matplotlib")

    def _export_results(self):
        if self.sim_results is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u6ca1\u6709\u53ef\u5bfc\u51fa\u7684\u7ed3\u679c\uff01")
            return
        path, _ = QFileDialog.getSaveFileName(self, "\u4fdd\u5b58\u7ed3\u679c", "simulation_result.csv", "CSV \u6587\u4ef6 (*.csv);;\u6240\u6709\u6587\u4ef6 (*.*)")
        if path:
            try:
                self.sim_results.to_csv(path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "\u6210\u529f", f"\u7ed3\u679c\u5df2\u4fdd\u5b58\u5230:\n{path}")
                self._append_log(f"\u5bfc\u51fa\u6210\u529f: {path}")
            except Exception as e:
                QMessageBox.critical(self, "\u9519\u8bef", f"\u4fdd\u5b58\u5931\u8d25:\n{str(e)}")


# ==================== \u4e3b\u7a0b\u5e8f\u5165\u53e3 ====================

def main():
    app = QApplication(sys.argv)
    app.setStyle("windows")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
