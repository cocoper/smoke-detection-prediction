# -*- coding:utf-8 -*-
"""
飞机货舱烟雾检测仿真系统 v5.0 (PySide6)

经典 Windows 原生风格界面：
  - 浅灰背景、直角控件、无圆角
  - 经典 Windows 菜单栏
  - Tab 页 + 日志区 + 状态栏
  - 纯中文界面

依赖安装: pip install PySide6 pandas numpy scikit-learn matplotlib
运行方式: python gui_pyside6_winstyle.py

v5.0 变更：
  - sklearn_compat.py 独立模块，GUI 不再内联模型兼容代码
  - 新增 simulation_config.py：类型化配置，构造时即校验
  - 新增 result_manager.py：结果版本化管理，每次运行不覆盖
  - 新增 simulation.py：仿真核心引擎，与 GUI 完全解耦
  - 新增 cargobay.py / Detector.py 重构版
  - 修复进度条总数估算 bug（原来用 ceil 偏大，现用 floor）
  - 废弃文件 gui.py / gui_pyside6_v3.py 已删除
"""
import os
import sys
import json
import math
import warnings
from pathlib import Path

import numpy as np
from time import time
import pandas as pd

warnings.filterwarnings('ignore')

# ==================== 核心模块（v5.0 新结构）====================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn_compat         import load_model
from simulation_config      import SimulationConfig
from simulation            import SimulationEngine, GridScanCallbacks, SingleSimulationResult
from result_manager        import ResultManager
from Detector              import Detector
from cargobay              import CargoBay

# ==================== PySide6 ====================
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

        p.setPen(QPen(QColor(0, 0, 0)))
        p.setFont(QFont("MS Sans Serif", 10, QFont.Bold))
        p.drawText(int(w/2-150), 28, f"\u8d27\u8239 {self.bay_length} x {self.bay_width} mm  |  {len(self.detectors)} \u4e2a\u63a2\u6d4b\u5668")

        p.setPen(QPen(QColor(0, 0, 128), 2))
        p.setBrush(QBrush(QColor(224, 224, 224)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        p.setPen(QPen(QColor(160, 160, 160), 1, Qt.DashLine))
        for g in range(2000, int(self.bay_length), 2000):
            gx = int(ox + g * s)
            p.drawLine(gx, int(oy), gx, int(oy + bh))
        p.setPen(QPen(QColor(100, 100, 100)))
        p.setFont(QFont("MS Sans Serif", 8))
        for g in range(0, int(self.bay_length)+1, 2000):
            gx = int(ox + g * s)
            p.drawText(gx - 10, int(oy + bh + 16), str(g))

        cy = int(oy + bh / 2)
        p.setPen(QPen(QColor(128, 128, 128), 1, Qt.DashLine))
        p.drawLine(int(ox), cy, int(ox + bw), cy)

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


# ==================== 仿真线程（使用 SimulationEngine）====================

class SimulationThread(QThread):
    progress      = Signal(int, str)
    finished      = Signal(float, int, int)
    error         = Signal(str)
    detector_info = Signal(list)
    log_msg       = Signal(str)

    def __init__(self, config: SimulationConfig, predictor, output_dir: str = "."):
        super().__init__()
        self.config    = config
        self.predictor = predictor
        self.output_dir = output_dir
        self._stop_flag = False

    def run(self):
        try:
            # v5.0: 使用 ResultManager + SimulationEngine
            rm = ResultManager(output_dir=self.output_dir)

            eng = SimulationEngine(
                config    = self.config,
                predictor = self.predictor,
                result_manager = rm,
            )

            # 探测器信息用于可视化
            det_info = eng.detector_info()
            self.detector_info.emit(det_info)
            for x, y, name, ch in det_info:
                self.log_msg.emit(f"[{name}] X={x:.1f} Y={y:.1f} Z={eng.cargobay.height_mm:.1f}")

            # 进度回调
            def on_progress(current, total, msg):
                pct = int(current / max(total, 1) * 95)
                self.progress.emit(min(pct, 95), msg)

            def on_stop():
                return self._stop_flag

            cbs = GridScanCallbacks(on_progress=on_progress, on_stop=on_stop)

            start_t = time()
            eng.run_grid(callbacks=cbs)
            end_t = time()

            # 读取结果
            df = rm.latest_dataframe
            if df is None:
                raise RuntimeError("结果文件未生成")

            failed = int(len(df[df['Alarm'] == False]))
            total  = int(len(df))
            elapsed = end_t - start_t

            self.log_msg.emit(
                f"\u4eff\u771f\u5b8c\u6210\uff01\u8017\u65f6 {elapsed:.1f}\u79d2\uff0c"
                f"\u5171 {total} \u6b21\u6d4b\u8bd5\uff0c\u5931\u8d25 {failed} \u6b21"
            )
            self.progress.emit(100, "\u5b8c\u6210")
            self.finished.emit(elapsed, failed, total)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    def stop(self):
        self._stop_flag = True


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.predictor   = None     # ML predictor
        self.inputs      = None     # SimulationConfig
        self.sim_thread  = None
        self.sim_results = None
        self.output_dir  = "."
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v5.0")
        self.setMinimumSize(1100, 760)
        self.resize(1380, 900)

        self._apply_classic_theme()

        central = QWidget()
        self.setCentralWidget(central)
        main_v = QVBoxLayout(central)
        main_v.setContentsMargins(2, 2, 2, 2)
        main_v.setSpacing(0)

        self._create_menu()
        self._create_tabs(main_v)
        self._create_log_area(main_v)
        self._create_status_bar()

    def _apply_classic_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #c0c0c0; font-family: "Segoe UI", "MS Sans Serif"; font-size: 11px; }
            QLabel { background: transparent; }
            QGroupBox { background: #dfdfdf; border: 1px solid #808080; margin-top: 6px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 2px 4px; }
            QPushButton { background: #ece9d8; border: 1px solid #808080; padding: 4px 12px; min-width: 70px; }
            QPushButton:hover { background: #d4d0c8; }
            QPushButton:pressed { background: #b8b4a8; }
            QPushButton:disabled { background: #e0e0e0; color: #a0a0a0; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: white; border: 1px solid #808080; padding: 2px; }
            QTextEdit, QTableWidget { background: white; border: 1px solid #808080; }
            QProgressBar { border: 1px solid #808080; background: #ece9d8; text-align: center; }
            QTabWidget::pane { border: 1px solid #808080; background: white; }
            QTabBar::tab { background: #c0c0c0; border: 1px solid #808080; padding: 4px 12px; }
            QTabBar::tab:selected { background: white; border-bottom-color: white; }
            QMenuBar { background: #ece9d8; border-bottom: 1px solid #808080; }
            QMenuBar::item:selected { background: #c0c0c0; }
            QMenu { background: #ece9d8; border: 1px solid #808080; }
            QMenu::item:selected { background: #c0c0c0; }
            QStatusBar { background: #ece9d8; border-top: 1px solid #808080; }
            QToolBar { background: #ece9d8; border-bottom: 1px solid #808080; spacing: 2px; }
            QToolButton { background: #ece9d8; border: 1px solid transparent; }
            QToolButton:hover { background: #d4d0c8; border: 1px solid #808080; }
        """)

    def _create_menu(self):
        menubar = self.menuBar()
        m_file = menubar.addMenu("\u6587\u4ef6(&F)")
        a_open = QAction("\u6253\u5f00\u914d\u7f6e...", self)
        a_open.setShortcut("Ctrl+O")
        a_open.triggered.connect(self._open_config)
        a_model = QAction("\u52a0\u8f7d\u6a21\u578b...", self)
        a_model.triggered.connect(self._open_model)
        a_exit = QAction("\u9000\u51fa", self)
        a_exit.setShortcut("Ctrl+Q")
        a_exit.triggered.connect(self.close)
        m_file.addAction(a_open)
        m_file.addAction(a_model)
        m_file.addSeparator()
        m_file.addAction(a_exit)

        m_help = menubar.addMenu("\u5e2e\u52a9(&H)")
        a_about = QAction("\u5173\u4e8e", self)
        a_about.triggered.connect(self._show_about)
        m_help.addAction(a_about)

        toolbar = self.addToolBar("\u4e3b\u8981\u5de5\u5177")
        toolbar.setMovable(False)

        self._btn_open   = QPushButton("\u6253\u5f00")
        self._btn_model  = QPushButton("\u52a0\u8f7d\u6a21\u578b")
        self._btn_run     = QPushButton("\u8fd0\u884c")
        self._btn_stop   = QPushButton("\u505c\u6b62")
        self._btn_chart  = QPushButton("\u56fe\u8868")
        self._btn_export = QPushButton("\u5bfc\u51fa")

        self._btn_stop.setEnabled(False)
        self._btn_run.setEnabled(False)
        self._btn_chart.setEnabled(False)
        self._btn_export.setEnabled(False)

        for btn in [self._btn_open, self._btn_model, self._btn_run,
                    self._btn_stop, self._btn_chart, self._btn_export]:
            btn.setMaximumHeight(28)

        self._btn_open.clicked.connect(self._open_config)
        self._btn_model.clicked.connect(self._open_model)
        self._btn_run.clicked.connect(self._run_simulation)
        self._btn_stop.clicked.connect(self._stop_simulation)
        self._btn_chart.clicked.connect(self._show_chart)
        self._btn_export.clicked.connect(self._export_results)

        for w in [self._btn_open, self._btn_model, None,
                  self._btn_run, self._btn_stop, None,
                  self._btn_chart, self._btn_export]:
            if w is None:
                toolbar.addSeparator()
            else:
                toolbar.addWidget(w)

    def _create_tabs(self, parent):
        self.tabs = QTabWidget()
        parent.addWidget(self.tabs, stretch=1)

        # ---- Tab 0: Simulation ----
        sim_w = QWidget()
        sim_h = QHBoxLayout(sim_w)

        # 左侧：配置面板
        cfg_scroll = QWidget()
        cfg_grid = QGridLayout(cfg_scroll)
        cfg_grid.setContentsMargins(8, 8, 8, 8)

        r = 0
        cfg_grid.addWidget(QLabel("\u673a\u578b\uff1a"), r, 0)
        self.le_type = QLineEdit()
        cfg_grid.addWidget(self.le_type, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u63a2\u6d4b\u5668\u6570\uff1a"), r, 0)
        self.sp_sdnum = QSpinBox()
        self.sp_sdnum.setRange(2, 20)
        self.sp_sdnum.setSingleStep(2)
        cfg_grid.addWidget(self.sp_sdnum, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u5bb4\u8239\u5bb4\u5ea6(mm)\uff1a"), r, 0)
        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(1, 50000)
        cfg_grid.addWidget(self.sp_width, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u5bb4\u8239\u957f\u5ea6(mm)\uff1a"), r, 0)
        self.sp_length = QDoubleSpinBox()
        self.sp_length.setRange(1, 100000)
        cfg_grid.addWidget(self.sp_length, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u5bb4\u8239\u9ad8\u5ea6(mm)\uff1a"), r, 0)
        self.sp_height = QDoubleSpinBox()
        self.sp_height.setRange(1, 50000)
        cfg_grid.addWidget(self.sp_height, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u62a5\u8b66\u9608\u503c(s)\uff1a"), r, 0)
        self.sp_crit = QSpinBox()
        self.sp_crit.setRange(1, 9999)
        cfg_grid.addWidget(self.sp_crit, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u6392\u5e03\u65b9\u5f0f\uff1a"), r, 0)
        self.cb_method = QComboBox()
        self.cb_method.addItems(["center", "side"])
        cfg_grid.addWidget(self.cb_method, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u524d\u7aef\u95f4\u9699(mm)\uff1a"), r, 0)
        self.sp_fwd = QSpinBox()
        self.sp_fwd.setRange(0, 99999)
        cfg_grid.addWidget(self.sp_fwd, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u540e\u7aef\u95f4\u9699(mm)\uff1a"), r, 0)
        self.sp_aft = QSpinBox()
        self.sp_aft.setRange(0, 99999)
        cfg_grid.addWidget(self.sp_aft, r, 1); r += 1

        cfg_grid.addWidget(QLabel("\u504f\u79fb(mm)\uff1a"), r, 0)
        self.sp_disp = QSpinBox()
        self.sp_disp.setRange(0, 99999)
        cfg_grid.addWidget(self.sp_disp, r, 1); r += 1

        cfg_grid.setRowStretch(r, 1)
        left_w = QWidget()
        left_w.setLayout(cfg_grid)

        # 中间：可视化
        self.bay_widget = CargoBayWidget()
        self.bay_widget.setMinimumWidth(500)

        # 右侧：进度
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.addWidget(QLabel("\u8fd0\u884c\u72b6\u6001"))
        self.prog_bar = QProgressBar()
        right_l.addWidget(self.prog_bar)
        self.lbl_status = QLabel("\u5c1a\u672a\u8fd0\u884c")
        right_l.addWidget(self.lbl_status)
        right_l.addStretch()

        sim_h.addWidget(left_w, stretch=1)
        sim_h.addWidget(self.bay_widget, stretch=3)
        sim_h.addWidget(right_w, stretch=1)

        self.tabs.addTab(sim_w, "\u4eff\u771f")

        # ---- Tab 1: Results ----
        self.tbl_results = QTableWidget()
        self.tabs.addTab(self.tbl_results, "\u7ed3\u679c")

        # ---- Tab 2: Settings ----
        settings = QScrollArea()
        settings.setWidgetResizable(True)
        sw = QWidget()
        sgrid = QGridLayout(sw)
        sgrid.addWidget(QLabel("\u8f93\u51fa\u76ee\u5f55\uff1a"), 0, 0)
        le_out = QLineEdit()
        le_out.setText(self.output_dir)
        le_out.textChanged.connect(lambda t: setattr(self, 'output_dir', t))
        sgrid.addWidget(le_out, 0, 1)
        sgrid.setRowStretch(1, 1)
        settings.setWidget(sw)
        self.tabs.addTab(settings, "\u8bbe\u7f6e")

        # ---- Tab 3: Help ----
        help_w = QTextEdit()
        help_w.setReadOnly(True)
        help_w.setHtml("""
<h3>\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v5.0</h3>
<p><b>\u4f7f\u7528\u8bf4\u660e\uff1a</b></p>
<ol>
<li>\u6253\u5f00\u914d\u7f6e\u6587\u4ef6 <code>inputs.json</code></li>
<li>\u52a0\u8f7d ML \u6a21\u578b <code>.model</code> \u6587\u4ef6</li>
<li>\u70b9\u51fb\u201c\u8fd0\u884c\u201d\u5f00\u59cb\u4eff\u771f</li>
<li>\u67e5\u770b\u7ed3\u679c\u8868</li>
</ol>
<p><b>\u914d\u7f6e\u8bf4\u660e\uff1a</b></p>
<ul>
<li>\u673a\u578b\uff1a\u53ea\u662f\u6807\u8bb0\uff0c\u4e0d\u5f71\u54cd\u8fd0\u7b97</li>
<li>\u63a2\u6d4b\u5668\u6570\uff1a\u5fc5\u987b\u4e3a\u5076\u6570</li>
<li>\u5bb4\u8239\u5c3a\u5bf8\uff1a\u5355\u4f4d mm\uff0c\u5fc5\u987b\u5927\u4e8e 0</li>
<li>\u62a5\u8b66\u9608\u503c\uff1a\u5355\u4f4d s\uff0c\u8d85\u8fc7\u6b64\u503c\u89e6\u53d1\u62a5\u8b66</li>
<li>\u6392\u5e03\u65b9\u5f0f\uff1a<code>center</code>\u2014\u6210\u5bf9\u5e03\u7f6e\uff1b<code>side</code>\u2014\u5212\u5206\u5e03\u7f6e</li>
</ul>
<hr>
<p><small>v5.0 \u4f7f\u7528 SimulationEngine + ResultManager \u65b0\u67b6\u6784\uff0c\u7ed3\u679c\u6587\u4ef6\u81ea\u52a8\u52a0\u65f6\u95f4\u6233\u3002</small></p>
        """)
        self.tabs.addTab(help_w, "\u5e2e\u52a9")

    def _create_log_area(self, parent):
        log_w = QWidget()
        log_l = QVBoxLayout(log_w)
        log_l.setContentsMargins(4, 2, 4, 2)
        log_l.setSpacing(2)
        lbl = QLabel("\u65e5\u5fd7")
        lbl.setStyleSheet("font-weight: bold; padding: 2px;")
        self.log_edit = QTextEdit()
        self.log_edit.setMaximumHeight(120)
        self.log_edit.setReadOnly(True)
        log_l.addWidget(lbl)
        log_l.addWidget(self.log_edit)
        parent.addWidget(log_w)

    def _create_status_bar(self):
        self.statusBar().showMessage("\u5c1a\u672a\u52a0\u8f7d\u914d\u7f6e")

    # ------------------------------------------------------------------
    # 菜单动作
    # ------------------------------------------------------------------
    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "\u6253\u5f00\u914d\u7f6e", ".", "JSON (*.json)")
        if not path:
            return
        try:
            self.inputs = SimulationConfig.from_json(path)
            self._sync_ui_from_config()
            self.log_edit.append(f"\u5df2\u52a0\u8f7d\u914d\u7f6e: {path}")
            self.statusBar().showMessage(f"\u5df2\u52a0\u8f7d: {path}")
            self._update_vis()
            self._btn_run.setEnabled(self.predictor is not None)
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", str(e))

    def _open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "\u52a0\u8f7d\u6a21\u578b", ".", "Model (*.model)")
        if not path:
            return
        try:
            self.predictor = load_model(path)
            self.log_edit.append(f"\u6a21\u578b\u52a0\u8f7d: {path} ({self.predictor})")
            self._btn_run.setEnabled(self.inputs is not None)
            self.statusBar().showMessage(f"\u6a21\u578b: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "\u9519\u8bef", str(e))

    def _sync_ui_from_config(self):
        if self.inputs is None:
            return
        self.le_type.setText(self.inputs.type_)
        self.sp_sdnum.setValue(self.inputs.sd_num)
        self.sp_width.setValue(self.inputs.bay.width_mm)
        self.sp_length.setValue(self.inputs.bay.length_mm)
        self.sp_height.setValue(self.inputs.bay.height_mm)
        self.sp_crit.setValue(self.inputs.criteria_s)
        self.cb_method.setCurrentText(self.inputs.arrange.method)
        self.sp_fwd.setValue(self.inputs.arrange.fwd_mm)
        self.sp_aft.setValue(self.inputs.arrange.aft_mm)
        self.sp_disp.setValue(self.inputs.arrange.displace_mm)

    def _update_vis(self):
        if self.inputs is None:
            return
        w = self.inputs.bay.width_mm
        l = self.inputs.bay.length_mm
        n = self.inputs.sd_num
        dets = []
        method = self.inputs.arrange.method
        fwd  = self.inputs.arrange.fwd_mm
        aft  = self.inputs.arrange.aft_mm
        disp = self.inputs.arrange.displace_mm
        sd_dim = (140.0, 145.0)
        half_sd_num = n // 2

        if method == "center":
            gap = (l - fwd - aft - sd_dim[0]*half_sd_num) / max(half_sd_num-1, 1)
            x_group = []
            x0 = fwd + sd_dim[0]/2
            x_group.append(x0)
            for _ in range(half_sd_num-1):
                x0 = x0 + gap + sd_dim[0]
                x_group.append(x0)
            x_group[-1] = l - aft - sd_dim[0]/2
            y_group = [w/2 + disp + sd_dim[1]/2, w/2 - disp - sd_dim[1]/2]
        else:
            gap = (l - fwd - aft - sd_dim[0]*n) / max(n-1, 1)
            x_group = []
            x0 = fwd + sd_dim[0]/2
            x_group.append(x0)
            for _ in range(n-1):
                x0 = x0 + gap + sd_dim[0]
                x_group.append(x0)
            x_group[-1] = l - aft - sd_dim[0]/2
            y_group = [w/2 + disp + sd_dim[1]/2, w/2 - disp - sd_dim[1]/2]

        for i in range(n):
            ch = 0 if i % 2 == 0 else 1
            x = x_group[i//2]
            y = y_group[0] if ch == 0 else y_group[1]
            dets.append((x, y, f"SD{i+1}", ch))

        self.bay_widget.set_layout(dets, w, l)

    def _run_simulation(self):
        if self.inputs is None or self.predictor is None:
            QMessageBox.warning(self, "\u63d0\u793a", "\u8bf7\u5148\u52a0\u8f7d\u914d\u7f6e\u548c\u6a21\u578b")
            return

        # 同步配置从 UI
        from simulation_config import BayConfig, ArrangeConfig
        self.inputs = SimulationConfig(
            type_     = self.le_type.text() or "unknown",
            sd_num    = self.sp_sdnum.value(),
            bay       = BayConfig(
                width_mm  = self.sp_width.value(),
                length_mm = self.sp_length.value(),
                height_mm = self.sp_height.value(),
            ),
            criteria_s = self.sp_crit.value(),
            arrange   = ArrangeConfig(
                method     = self.cb_method.currentText(),
                fwd_mm     = self.sp_fwd.value(),
                aft_mm     = self.sp_aft.value(),
                displace_mm = self.sp_disp.value(),
            ),
        )
        errs = self.inputs.validate()
        if errs:
            QMessageBox.critical(self, "\u914d\u7f6e\u6821\u9a8c\u5931\u8d25", "\n".join(errs))
            return

        self.log_edit.clear()
        self.log_edit.append(f"\u5f00\u59cb\u4eff\u771f\uff08{self.inputs.sd_num} \u63a2\u6d4b\u5668\uff09...")

        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("\u8fd0\u884c\u4e2d...")

        self.sim_thread = SimulationThread(self.inputs, self.predictor, self.output_dir)
        self.sim_thread.progress.connect(self._on_progress)
        self.sim_thread.finished.connect(self._on_finished)
        self.sim_thread.error.connect(self._on_error)
        self.sim_thread.detector_info.connect(self._on_detector_info)
        self.sim_thread.log_msg.connect(self._append_log)
        self.sim_thread.start()

    def _stop_simulation(self):
        if self.sim_thread:
            self.sim_thread.stop()
            self.lbl_status.setText("\u6b63\u5728\u505c\u6b62...")

    def _on_progress(self, pct, msg):
        self.prog_bar.setValue(pct)
        self.lbl_status.setText(msg)

    def _on_finished(self, elapsed, failed, total):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self.lbl_status.setText(f"\u5b8c\u6210 \u2014 {failed}/{total} \u5931\u8d25")
        self._btn_chart.setEnabled(True)
        self._btn_export.setEnabled(True)

        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if runs:
            df = rm.load_file(runs[0]["file"])
            self._populate_table(df)

    def _on_error(self, msg):
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self.lbl_status.setText("\u9519\u8bef")
        QMessageBox.critical(self, "\u8fd0\u884c\u9519\u8bef", msg)

    def _on_detector_info(self, info):
        if self.inputs:
            self.bay_widget.set_layout(info, self.inputs.bay.width_mm, self.inputs.bay.length_mm)

    def _append_log(self, msg):
        self.log_edit.append(msg)

    def _populate_table(self, df):
        self.tbl_results.clear()
        self.tbl_results.setColumnCount(len(df.columns))
        self.tbl_results.setRowCount(len(df))
        self.tbl_results.setHorizontalHeaderLabels(list(df.columns))
        for i, row in enumerate(df.itertuples(index=False)):
            for j, val in enumerate(row):
                self.tbl_results.setItem(i, j, QTableWidgetItem(str(val)))
        self.tbl_results.resizeColumnsToContents()
        self.tabs.setCurrentIndex(1)

    def _show_chart(self):
        import matplotlib
        matplotlib.use("Qt5Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQgg

        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if not runs:
            return
        df = rm.load_file(runs[0]["file"])

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))
        fig.suptitle("\u62a5\u8b66\u65f6\u95f4\u5206\u5e03", fontproperties=matplotlib.font_manager.FontProperties(fname="C:/Windows/Fonts/simhei.ttf"))

        # 直方图
        alarm_df = df[df["Alarm"] == True]
        for col in [c for c in df.columns if c.startswith("SD")]:
            times = alarm_df[col].dropna()
            if len(times) > 0:
                axes[0].hist(times, bins=30, alpha=0.6, label=col)
        axes[0].set_xlabel("\u62a5\u8b66\u65f6\u95f4(s)")
        axes[0].set_ylabel("\u983b\u6b21")
        axes[0].legend()
        axes[0].set_title("\u5404\u901a\u9053\u62a5\u8b66\u65f6\u95f4")

        # 统计汇总
        alarm_counts = df["Alarm"].value_counts()
        axes[1].bar(["\u62a5\u8b66", "\u672a\u62a5\u8b66"], [alarm_counts.get(True, 0), alarm_counts.get(False, 0)], color=["green", "red"])
        axes[1].set_ylabel("\u6b21\u6570")
        axes[1].set_title("\u62a5\u8b66\u72b6\u6001\u7ed3\u679c")
        plt.tight_layout()
        plt.show()

    def _export_results(self):
        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if not runs:
            return
        df = rm.load_file(runs[0]["file"])
        path, _ = QFileDialog.getSaveFileName(self, "\u5bfc\u51fa\u7ed3\u679c", "result_export.csv", "CSV (*.csv)")
        if path:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.log_edit.append(f"\u5bfc\u51fa\u5230: {path}")

    def _show_about(self):
        QMessageBox.about(self, "\u5173\u4e8e",
            "<h3>\u98d8\u96fe\u68c0\u6d4b\u4eff\u771f\u7cfb\u7edf v5.0</h3>"
            "<p>Python + PySide6 + scikit-learn</p>"
            "<p>\u57fa\u4e8e SimulationEngine + ResultManager \u65b0\u67b6\u6784</p>"
            "<p>GitHub: <a href='https://github.com/cocoper/smoke-detection-prediction'>cocoper/smoke-detection-prediction</a></p>"
        )


# ==================== 入口 ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
