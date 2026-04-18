# -*- coding:utf-8 -*-
"""
飞机货舱烟雾检测仿真系统 v5.0 (PySide6)
经典 Windows 原生风格界面。
运行: python gui_pyside6_winstyle.py
"""
from __future__ import annotations

import os, sys, math, warnings, re
from pathlib import Path
from time import time
from datetime import datetime

import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

# ── 核心模块 ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sklearn_compat      import load_model
from simulation_config   import SimulationConfig, BayConfig, ArrangeConfig
from simulation          import SimulationEngine, GridScanCallbacks
from result_manager      import ResultManager
from Detector            import Detector
from cargobay            import CargoBay

# ── PySide6 ──────────────────────────────────────────────
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFormLayout,
    QPushButton, QLabel, QTextEdit, QComboBox,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QGroupBox, QInputDialog,
    QSpinBox, QDoubleSpinBox, QTabWidget,
    QMenuBar, QMenu, QDialog, QDialogButtonBox,
    QHeaderView, QAbstractItemView, QScrollArea,
    QCheckBox, QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QPointF
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QAction, QMouseEvent, QIcon


# ── 图标资源 ────────────────────────────────────────────────
_ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def _get_icon(name: str) -> QIcon:
    """加载 icons/ 目录下的 PNG 图标"""
    path = os.path.join(_ICON_DIR, f"icon_{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()   # 空图标兜底


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════
def parse_src_loc(s: str):
    """解析 'Src Loc.' 列的字符串如 '(0.0, 1000.0, 0.0)' → (x, y, z)"""
    if not s or not isinstance(s, str):
        return None, None, None
    m = re.findall(r"[-+]?\d+\.?\d*", s)
    if len(m) >= 3:
        return float(m[0]), float(m[1]), float(m[2])
    return None, None, None


# ═══════════════════════════════════════════════════════════════════════
# 货舱可视化（支持热力图）
# ═══════════════════════════════════════════════════════════════════════
class CargoBayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(500, 300)
        self.setStyleSheet("background:#ffffff;border:1px solid #808080;")
        self.detectors  = []      # [(x_mm, y_mm, name, channel), ...]
        self.heatmap    = {}      # {(x_mm, y_mm): alarm_bool}
        self.bay_width  = 1000
        self.bay_length = 5000

    def set_layout(self, detectors, bay_width, bay_length):
        self.detectors  = detectors
        self.bay_width  = bay_width
        self.bay_length = bay_length
        self.update()

    def set_heatmap(self, data: dict):
        """data: {(x_mm, y_mm): alarm_bool}"""
        self.heatmap = data
        self.update()

    def clear_heatmap(self):
        self.heatmap = {}
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if not self.detectors:
            p.setPen(QPen(QColor(0,0,0)))
            p.setFont(QFont("Microsoft YaHei", 11))
            p.drawText(self.rect(), Qt.AlignCenter, "加载配置后显示货舱布局")
            p.end()
            return

        mt, mb, ml, mr = 40, 40, 58, 20
        dw = w - ml - mr
        dh = h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s  = min(sx, sy)
        bw = self.bay_length * s
        bh = self.bay_width  * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2

        # 标题
        p.setPen(QPen(QColor(0,0,0)))
        p.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        title = (f"货舱 {int(self.bay_length)} x {int(self.bay_width)} mm  |  "
                 f"{len(self.detectors)} 个探测器")
        p.drawText(int(w/2 - p.fontMetrics().horizontalAdvance(title)/2), 26, title)

        # 货舱背景
        p.setPen(QPen(QColor(0,0,128), 2))
        p.setBrush(QBrush(QColor(230,230,255)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        # X 网格线
        p.setPen(QPen(QColor(160,160,160), 1, Qt.DashLine))
        for gx in range(2000, int(self.bay_length), 2000):
            px = int(ox + gx * s)
            p.drawLine(px, int(oy), px, int(oy+bh))
        for gy in range(2000, int(self.bay_width), 2000):
            py = int(oy + gy * s)
            p.drawLine(int(ox), py, int(ox+bw), py)

        # X 轴刻度
        p.setFont(QFont("Microsoft YaHei", 8))
        p.setPen(QPen(QColor(100,100,100)))
        for gx in range(0, int(self.bay_length)+1, 2000):
            px = int(ox + gx * s)
            lbl = str(gx)
            p.drawText(px - p.fontMetrics().horizontalAdvance(lbl)/2, int(oy+bh+16), lbl)
        p.drawText(int(ox + bw/2 - 30), int(oy+bh+30), "← 长度 X (mm) →")

        # Y 轴刻度
        for gy in range(0, int(self.bay_width)+1, 2000):
            py = int(oy + gy * s)
            lbl = str(gy)
            p.drawLine(int(ox-4), py, int(ox), py)
            p.drawText(int(ox - 6 - p.fontMetrics().horizontalAdvance(lbl)), py + 4, lbl)

        # Y 轴标签
        p.save()
        p.translate(14, int(oy + bh/2))
        p.rotate(-90)
        p.drawText(-p.fontMetrics().horizontalAdvance("← 宽度 Y (mm) →")//2, 0, "← 宽度 Y (mm) →")
        p.restore()

        # 中心线
        cx = int(ox + bw/2)
        p.setPen(QPen(QColor(128,128,128), 1, Qt.DashLine))
        p.drawLine(cx, int(oy), cx, int(oy+bh))
        p.setPen(QPen(QColor(100,100,100)))
        p.setFont(QFont("Microsoft YaHei", 7))
        p.drawText(cx+3, int(oy+bh/2)+4, "中线")

        # ── 热力图 ─────────────────────────────────────
        if self.heatmap:
            p.setFont(QFont("Microsoft YaHei", 8))
            for (hx, hy), alarm in self.heatmap.items():
                px_h = int(ox + hx * s)
                py_h = int(oy + hy * s)
                if not (int(ox) <= px_h <= int(ox+bw) and int(oy) <= py_h <= int(oy+bh)):
                    continue
                if alarm:
                    p.setPen(QPen(QColor(0, 180, 0, 200), 1))
                    p.setBrush(QBrush(QColor(0, 220, 0, 150)))
                else:
                    p.setPen(QPen(QColor(200, 0, 0, 200), 1))
                    p.setBrush(QBrush(QColor(255, 60, 60, 180)))
                p.drawEllipse(px_h-5, py_h-5, 10, 10)

        # ── 探测器 ─────────────────────────────────────
        for x, y, name, ch in self.detectors:
            dx = ox + x * s
            dy = oy + y * s
            if ch == 0:
                c = QColor(0,160,0)
            else:
                c = QColor(0,0,200)
            p.setPen(QPen(c, 2)); p.setBrush(QBrush(c.lighter(160)))
            p.drawEllipse(int(dx-6), int(dy-6), 12, 12)
            p.setFont(QFont("Microsoft YaHei", 9))
            p.setPen(QPen(QColor(0,0,0)))
            p.drawText(int(dx+8), int(dy+4), name)

        # ── 图例 ───────────────────────────────────────
        lx = int(ox + bw - 118)
        ly = int(oy + bh - (50 if self.heatmap else 34))
        lh = 50 if self.heatmap else 32
        p.setPen(QPen(QColor(0,0,0))); p.setBrush(QBrush(QColor(255,255,255)))
        p.drawRect(lx, ly, 114, lh)

        # 探测器图例
        p.setPen(QPen(QColor(0,160,0))); p.setBrush(QBrush(QColor(0,160,0)))
        p.drawEllipse(lx+8, ly+6, 8, 8)
        p.setPen(QPen(QColor(0,0,0))); p.setFont(QFont("Microsoft YaHei", 9))
        p.drawText(lx+20, ly+14, "A通道")
        p.setPen(QPen(QColor(0,0,200))); p.setBrush(QBrush(QColor(0,0,200)))
        p.drawEllipse(lx+8, ly+20, 8, 8)
        p.setPen(QPen(QColor(0,0,0))); p.drawText(lx+20, ly+28, "B通道")

        if self.heatmap:
            p.setPen(QPen(QColor(0,220,0))); p.setBrush(QBrush(QColor(0,220,0)))
            p.drawEllipse(lx+8, ly+35, 8, 8)
            p.setPen(QPen(QColor(0,0,0))); p.setFont(QFont("Microsoft YaHei", 9))
            p.drawText(lx+20, ly+42, "报警")
            p.setPen(QPen(QColor(255,60,60))); p.setBrush(QBrush(QColor(255,60,60)))
            p.drawEllipse(lx+60, ly+35, 8, 8)
            p.setPen(QPen(QColor(0,0,0))); p.drawText(lx+72, ly+42, "漏检")

        p.end()


# ═══════════════════════════════════════════════════════════════════════
# 探测器拖拽/定位界面（独立 Tab）
# ═══════════════════════════════════════════════════════════════════════
class DetectorDragWidget(QWidget):
    """
    探测器拖拽定位界面：
    - 左：货舱拖拽画布（鼠标拖动探测器位置）
    - 右：探测器列表（显示序号/X/Y/通道，双击也编辑）
    """
    detectors_changed = Signal(list)   # [(x,y,name,ch), ...] 更新时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detectors  = []      # 当前探测器列表
        self.bay_width  = 4166.0
        self.bay_length = 16184.0
        self._dragging  = None    # 当前拖拽的探测器索引
        self._drag_off  = 0, 0     # 鼠标相对探测器圆心偏移
        self._updating  = False   # 重入保护：防止 cellChanged 递归触发
        self._confirmed = False   # 确认状态：是否已点「确认布放」

        self._build_ui()

    def _build_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # ── 左：拖拽画布 ────────────────────────────────
        self.canvas = _DetectorCanvas()
        self.canvas.setMinimumSize(560, 380)
        self.canvas.detectors_changed.connect(self._on_canvas_changed)
        lay.addWidget(self.canvas, stretch=2)

        # ── 右：探测器参数列表 ──────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        rl.addWidget(QLabel("<b>探测器列表</b>（双击坐标编辑）"))

        self.det_table = QTableWidget()
        self.det_table.setColumnCount(4)
        self.det_table.setHorizontalHeaderLabels(["名称", "X (mm)", "Y (mm)", "通道"])
        self.det_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.det_table.setMaximumWidth(320)
        self.det_table.itemDoubleClicked.connect(self._on_cell_double_clicked)
        self.det_table.cellChanged.connect(self._on_table_cell_changed)
        rl.addWidget(self.det_table)

        # 布局按钮
        btn_fix    = QPushButton(_get_icon("bay"),    "自动均匀布局")
        self._btn_confirm = QPushButton(_get_icon("save"), "确认布放")
        self._btn_confirm.setStyleSheet("background:#27AE60; color:white; font-weight:bold;")
        self._btn_apply  = QPushButton(_get_icon("run"),   "应用到仿真")
        self._btn_apply.setStyleSheet("background:#2980B9; color:white; font-weight:bold;")
        self._btn_cancel = QPushButton(_get_icon("delete"), "取消确认")
        self._btn_cancel.setEnabled(False)
        self._btn_apply.setEnabled(False)

        btn_fix.clicked.connect(self._auto_layout)
        self._btn_confirm.clicked.connect(self._confirm_layout)
        self._btn_apply.clicked.connect(self._apply_to_simulation)
        self._btn_cancel.clicked.connect(self._cancel_confirm)

        for b in [btn_fix, self._btn_confirm, self._btn_apply, self._btn_cancel]:
            rl.addWidget(b)

        # 货舱尺寸
        size_gb = QGroupBox("货舱尺寸(mm)")
        sg = QFormLayout(size_gb)
        sg.setLabelAlignment(Qt.AlignRight)
        self.sp_bw = QSpinBox(); self.sp_bw.setRange(1,99999); self.sp_bw.setValue(4166); self.sp_bw.setMaximumWidth(120)
        self.sp_bl = QSpinBox(); self.sp_bl.setRange(1,99999); self.sp_bl.setValue(16184); self.sp_bl.setMaximumWidth(120)
        self.sp_bw.valueChanged.connect(self._on_bay_size_changed)
        self.sp_bl.valueChanged.connect(self._on_bay_size_changed)
        sg.addRow("宽度：", self.sp_bw)
        sg.addRow("长度：", self.sp_bl)
        rl.addWidget(size_gb)

        # 通道过滤
        self.ch_filter = QComboBox()
        self.ch_filter.addItems(["全部", "仅A通道", "仅B通道"])
        rl.addWidget(QLabel("显示通道："))
        rl.addWidget(self.ch_filter)
        self.ch_filter.currentIndexChanged.connect(self._apply_filter)

        rl.addStretch()

    def _on_bay_size_changed(self):
        self.bay_width  = float(self.sp_bw.value())
        self.bay_length = float(self.sp_bl.value())
        self.canvas.set_bay(self.bay_width, self.bay_length)
        self.canvas.refresh()

    def init_detectors(self, detectors, bay_width, bay_length):
        """外部调用：用仿真配置初始化探测器列表"""
        self.bay_width  = bay_width
        self.bay_length = bay_length
        self.sp_bw.setValue(int(bay_width))
        self.sp_bl.setValue(int(bay_length))
        self.detectors  = list(detectors)
        self._confirmed = False     # 重置确认状态
        self._update_confirm_ui()
        self.canvas.set_bay(bay_width, bay_length)
        self.canvas.set_detectors(self.detectors)
        self._fill_table()

    def _fill_table(self):
        if self._updating:
            return
        self._updating = True
        try:
            self.det_table.cellChanged.disconnect(self._on_table_cell_changed)
        except RuntimeError:
            pass
        self.det_table.setRowCount(len(self.detectors))
        for i, (x, y, name, ch) in enumerate(self.detectors):
            ch_str = "A" if ch == 0 else "B"
            for j, val in enumerate([name, f"{x:.1f}", f"{y:.1f}", ch_str]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.det_table.setItem(i, j, item)
                if j == 3:
                    item.setForeground(QColor(0,160,0) if ch == 0 else QColor(0,0,200))
        self.det_table.cellChanged.connect(self._on_table_cell_changed)
        self._updating = False

    def _on_canvas_changed(self, detectors):
        if self._updating:
            return
        self.detectors = detectors
        self._fill_table()
        self.detectors_changed.emit(detectors)

    def _on_cell_double_clicked(self, item):
        """双击坐标格进入编辑模式"""
        row, col = item.row(), item.col()
        if col in (1, 2):   # X 或 Y 列 → 弹出输入框
            cur = item.text()
            prompt = "X坐标(mm)" if col == 1 else "Y坐标(mm)"
            val, ok = QInputDialog.getDouble(self, "编辑坐标", prompt,
                                             float(cur), 0, 99999, 1)
            if ok:
                x, y, name, ch = self.detectors[row]
                if col == 1:
                    x = val
                else:
                    y = val
                self.detectors[row] = (x, y, name, ch)
                self.canvas.set_detectors(self.detectors)
                self._fill_table()
                self.detectors_changed.emit(self.detectors)

    def _on_table_cell_changed(self, row, col):
        """表格内容变化同步到 canvas"""
        if col == 0:   # 名称
            new_name = self.det_table.item(row, 0).text()
            x, y, _, ch = self.detectors[row]
            self.detectors[row] = (x, y, new_name, ch)
            self.canvas.set_detectors(self.detectors)
            self.detectors_changed.emit(self.detectors)

    def _auto_layout(self):
        """自动均匀布局"""
        n = len(self.detectors)
        if n == 0: return
        half = n // 2
        bw, bl = self.bay_width, self.bay_length
        # 均匀排列在货舱中心线两侧
        xg = np.linspace(bl*0.1, bl*0.9, max(half, 1))
        new_dets = []
        for i in range(n):
            ch  = 0 if i % 2 == 0 else 1
            xi  = xg[i // 2]
            yi  = bw/2 + (50 if ch == 0 else -50)
            new_dets.append((xi, yi, f"SD{i+1}", ch))
        self.detectors = new_dets
        self.canvas.set_detectors(new_dets)
        self._fill_table()
        self.detectors_changed.emit(new_dets)

    def _apply_filter(self):
        """根据通道过滤显示"""
        idx = self.ch_filter.currentIndex()
        all_dets = getattr(self, '_all_detectors', self.detectors)
        if idx == 0:
            shown = all_dets
        elif idx == 1:
            shown = [(x,y,n,0) for x,y,n,ch in all_dets if ch == 0]
        else:
            shown = [(x,y,n,1) for x,y,n,ch in all_dets if ch == 1]
        self.detectors = shown
        self.canvas.set_detectors(shown)
        self._fill_table()

    def _confirm_layout(self):
        """
        「确认布放」：锁定当前所有探测器位置。
        锁定后画布标题变色，探测器可继续拖拽编辑，
        点「应用到仿真」才真正生效。
        """
        self._confirmed = True
        self._update_confirm_ui()

    def _cancel_confirm(self):
        """取消确认状态"""
        self._confirmed = False
        self._update_confirm_ui()

    def _update_confirm_ui(self):
        """根据确认状态更新画布边框颜色和按钮可用性"""
        if self._confirmed:
            self.canvas.setStyleSheet(
                "background:#f8f8f8;border:3px solid #27AE60;")
            self._btn_confirm.setEnabled(False)
            self._btn_cancel.setEnabled(True)
            self._btn_apply.setEnabled(True)
        else:
            self.canvas.setStyleSheet(
                "background:#f8f8f8;border:1px solid #808080;")
            self._btn_confirm.setEnabled(True)
            self._btn_cancel.setEnabled(False)
            self._btn_apply.setEnabled(False)

    def _apply_to_simulation(self):
        """「应用到仿真」：仅在已确认状态下才真正同步到仿真参数"""
        if not self._confirmed:
            QMessageBox.warning(
                self, "请先确认",
                "请先点击「确认布放」锁定当前布局，再点击「应用到仿真」。")
            return
        dets = list(self.detectors)
        n    = len(dets)
        reply = QMessageBox.question(
            self, "确认应用",
            f"将把 {n} 个已确认的探测器应用到仿真：\n\n" +
            "\n".join(f"  {d[2]}: X={d[0]:.0f} Y={d[1]:.0f} {'A' if d[3]==0 else 'B'}通道"
                     for d in dets[:8]) +
            (f"\n  ... 共 {n} 个" if n > 8 else ""),
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply != QMessageBox.Ok:
            return
        if hasattr(self, '_main_win') and self._main_win:
            self._main_win.sync_from_drag_widget(dets, self.bay_width, self.bay_length)

    def get_detectors(self):
        return list(self.detectors)


# ── 拖拽画布（独立 QWidget）────────────────────────────────────
class _DetectorCanvas(QWidget):
    detectors_changed = Signal(list)
    # 工具模式
    MODE_DRAG = 0
    MODE_ADD  = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#f8f8f8;border:1px solid #808080;")
        self.detectors  = []
        self.bay_width  = 4166.0
        self.bay_length = 16184.0
        self._dragging  = None
        self._drag_off  = 0, 0
        self._mode      = self.MODE_DRAG    # 当前工具模式
        self._next_ch   = 0                 # 新建探测器轮换通道
        self._hover_idx = -1                # 鼠标悬停的探测器
        self._mouse_mm  = None, None        # 鼠标在货舱坐标(mm)
        self.setMouseTracking(True)

    def set_bay(self, w, l):
        self.bay_width, self.bay_length = w, l

    def set_detectors(self, dets):
        self.detectors = list(dets)
        self.update()

    def refresh(self):
        self.update()

    def _to_pixel(self, x_mm, y_mm):
        w, h = self.width(), self.height()
        mt, mb, ml, mr = 40, 40, 55, 15
        dw, dh = w - ml - mr, h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s  = min(sx, sy)
        bw = self.bay_length * s
        bh = self.bay_width  * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2
        return ox + x_mm * s, oy + y_mm * s

    def _to_mm(self, px, py):
        w, h = self.width(), self.height()
        mt, mb, ml, mr = 40, 40, 55, 15
        dw, dh = w - ml - mr, h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s  = min(sx, sy)
        bw = self.bay_length * s
        bh = self.bay_width  * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2
        return (px - ox) / s, (py - oy) / s

    def _is_in_bay(self, px, py):
        """判断像素坐标是否在货舱框内"""
        w, h = self.width(), self.height()
        mt, mb, ml, mr = 40, 40, 55, 15
        dw, dh = w - ml - mr, h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s  = min(sx, sy)
        bw = self.bay_length * s
        bh = self.bay_width  * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2
        return (ox <= px <= ox+bw and oy <= py <= oy+bh)

    def _hit_test(self, px, py):
        """返回探测器索引或-1"""
        for i, (x, y, _, _) in enumerate(self.detectors):
            dx, dy = self._to_pixel(x, y)
            if abs(px - dx) <= 10 and abs(py - dy) <= 10:
                return i
        return -1

    def mousePressEvent(self, e):
        idx = self._hit_test(e.pos().x(), e.pos().y())
        if e.button() == Qt.LeftButton:
            if idx >= 0:
                # 拖拽已有探测器
                self._dragging = idx
                cx, cy = self._to_pixel(*self.detectors[idx][:2])
                self._drag_off = e.pos().x() - cx, e.pos().y() - cy
            else:
                # 左键空白处 → 新建探测器（在货舱范围内）
                if self._is_in_bay(e.pos().x(), e.pos().y()):
                    mx, my = self._to_mm(e.pos().x(), e.pos().y())
                    mx = max(0, min(self.bay_length, mx))
                    my = max(0, min(self.bay_width,  my))
                    n  = len(self.detectors) + 1
                    ch = self._next_ch
                    self._next_ch = 1 - self._next_ch   # 轮换 A/B
                    name = f"SD{n}"
                    self.detectors.append((mx, my, name, ch))
                    self.detectors_changed.emit(list(self.detectors))
                    self.update()
        elif e.button() == Qt.RightButton:
            if idx >= 0:
                self._show_context_menu(e.pos(), idx)

    def mouseMoveEvent(self, e):
        px, py = e.pos().x(), e.pos().y()
        # 悬停检测
        new_hover = self._hit_test(px, py)
        if new_hover != self._hover_idx:
            self._hover_idx = new_hover
            self.update()
        # 鼠标坐标显示
        if self._is_in_bay(px, py):
            mx, my = self._to_mm(px, py)
            self._mouse_mm = mx, my
        else:
            self._mouse_mm = None, None
        self.update()

        if self._dragging is not None:
            mx, my = self._to_mm(e.pos().x() - self._drag_off[0],
                                 e.pos().y() - self._drag_off[1])
            mx = max(0, min(self.bay_length, mx))
            my = max(0, min(self.bay_width,  my))
            x, y, name, ch = self.detectors[self._dragging]
            self.detectors[self._dragging] = (mx, my, name, ch)
            self.update()

    def mouseReleaseEvent(self, e):
        if self._dragging is not None:
            self._dragging = None
            self.detectors_changed.emit(list(self.detectors))

    def _show_context_menu(self, pos, idx):
        menu = QMenu(self)
        x, y, name, ch = self.detectors[idx]
        ch_str = "A" if ch == 0 else "B"

        a_edit  = menu.addAction(_get_icon("settings"), f"编辑 [{name}]  (X={x:.0f} Y={y:.0f} {ch_str}通道)")
        a_del   = menu.addAction(_get_icon("delete"),   f"删除 [{name}]")
        menu.addSeparator()
        a_chA   = menu.addAction(_get_icon("chart"),    "改为 A通道")
        a_chB   = menu.addAction(_get_icon("chart"),    "改为 B通道")

        act = menu.exec(self.mapToGlobal(pos))
        if act == a_del:
            self.detectors.pop(idx)
            self.detectors_changed.emit(list(self.detectors))
            self.update()
        elif act == a_edit:
            # 弹出编辑对话框
            new_x, ok1 = QInputDialog.getDouble(self, "编辑坐标", f"{name} X坐标(mm)", x, 0, self.bay_length, 1)
            if ok1:
                new_y, ok2 = QInputDialog.getDouble(self, "编辑坐标", f"{name} Y坐标(mm)", y, 0, self.bay_width, 1)
                if ok2:
                    self.detectors[idx] = (new_x, new_y, name, ch)
                    self.detectors_changed.emit(list(self.detectors))
                    self.update()
        elif act == a_chA:
            self.detectors[idx] = (x, y, name, 0)
            self.detectors_changed.emit(list(self.detectors))
            self.update()
        elif act == a_chB:
            self.detectors[idx] = (x, y, name, 1)
            self.detectors_changed.emit(list(self.detectors))
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        mt, mb, ml, mr = 40, 40, 55, 15
        dw, dh = w - ml - mr, h - mt - mb
        sx = dw / self.bay_length
        sy = dh / self.bay_width
        s  = min(sx, sy)
        bw = self.bay_length * s
        bh = self.bay_width  * s
        ox = ml + (dw - bw) / 2
        oy = mt + (dh - bh) / 2

        # 标题
        p.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        p.setPen(QPen(QColor(0,0,0)))
        p.drawText(self.rect(), Qt.AlignTop | Qt.AlignHCenter,
                   f"左键新建探测器  |  右键菜单编辑/删除  |  拖拽移动位置  |  货舱 {int(self.bay_length)} x {int(self.bay_width)} mm")

        # 货舱框
        p.setPen(QPen(QColor(0,0,128), 2))
        p.setBrush(QBrush(QColor(230,230,255)))
        p.drawRect(int(ox), int(oy), int(bw), int(bh))

        # 网格
        p.setPen(QPen(QColor(160,160,160), 1, Qt.DashLine))
        for gx in range(2000, int(self.bay_length), 2000):
            px = int(ox + gx * s)
            p.drawLine(px, int(oy), px, int(oy+bh))
        for gy in range(2000, int(self.bay_width), 2000):
            py = int(oy + gy * s)
            p.drawLine(int(ox), py, int(ox+bw), py)

        # X 刻度
        p.setFont(QFont("Microsoft YaHei", 8))
        p.setPen(QPen(QColor(100,100,100)))
        for gx in range(0, int(self.bay_length)+1, 4000):
            px = int(ox + gx * s)
            p.drawText(px - p.fontMetrics().horizontalAdvance(str(gx))//2, int(oy+bh+14), str(gx))
        p.drawText(int(ox+bw/2-30), int(oy+bh+28), "X (mm)")

        # Y 刻度
        for gy in range(0, int(self.bay_width)+1, 2000):
            py = int(oy + gy * s)
            lbl = str(gy)
            p.drawLine(int(ox-4), py, int(ox), py)
            p.drawText(int(ox - 6 - p.fontMetrics().horizontalAdvance(lbl)), py+4, lbl)
        p.save()
        p.translate(12, int(oy+bh/2))
        p.rotate(-90)
        p.drawText(-p.fontMetrics().horizontalAdvance("Y (mm)")//2, 0, "Y (mm)")
        p.restore()

        # 中线
        cx = int(ox + bw/2)
        p.setPen(QPen(QColor(128,128,128), 1, Qt.DashLine))
        p.drawLine(cx, int(oy), cx, int(oy+bh))

        # 探测器
        for i, (x, y, name, ch) in enumerate(self.detectors):
            dx, dy = self._to_pixel(x, y)
            is_dragging = (i == self._dragging)
            is_hover    = (i == self._hover_idx)
            r = 12 if (is_dragging or is_hover) else 8

            if ch == 0:
                fill = QColor(0,180,0)
            else:
                fill = QColor(0,80,220)

            # 悬停/拖拽时画外发光圈
            if is_hover and not is_dragging:
                p.setPen(QPen(fill.lighter(150), 2)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(dx-r-3), int(dy-r-3), (r+3)*2, (r+3)*2)

            p.setPen(QPen(fill.lighter(130), 2 if is_dragging else 1))
            p.setBrush(QBrush(fill.lighter(160) if is_dragging else fill))
            p.drawEllipse(int(dx-r), int(dy-r), r*2, r*2)
            p.setPen(QPen(QColor(255,255,255) if is_dragging else QColor(0,0,0)))
            p.setFont(QFont("Microsoft YaHei", 8 if is_dragging else 9, QFont.Bold))
            p.drawText(int(dx+11), int(dy+4), name)

        # 坐标提示（拖拽时 + 鼠标悬停时）
        if self._dragging is not None:
            x, y, _, _ = self.detectors[self._dragging]
            p.setPen(QPen(QColor(0,0,0))); p.setBrush(QBrush(QColor(255,255,220)))
            p.drawRect(5, 5, 160, 28)
            p.setFont(QFont("Consolas", 9))
            p.drawText(10, 24, f"X={x:.1f}  Y={y:.1f}  (mm)")
        elif self._mouse_mm[0] is not None:
            mx, my = self._mouse_mm
            p.setPen(QPen(QColor(0,0,0))); p.setBrush(QBrush(QColor(255,255,220)))
            p.drawRect(5, 5, 160, 28)
            p.setFont(QFont("Consolas", 9))
            p.drawText(10, 24, f"X={mx:.1f}  Y={my:.1f}  (mm)")

        # 空状态提示
        if not self.detectors:
            p.setPen(QPen(QColor(150,150,150)))
            p.setFont(QFont("Microsoft YaHei", 12))
            p.drawText(int(w/2 - 150), int(h/2), "左键点击货舱区域添加探测器")
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(int(w/2 - 100), int(h/2)+22, "或使用「自动均匀布局」按钮")

        p.end()


# ═══════════════════════════════════════════════════════════════════════
# 探测器尺寸设置对话框
# ═══════════════════════════════════════════════════════════════════════
class DetectorSizeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("探测器尺寸设置")
        self.setMinimumSize(520, 340)
        self._build_ui()
        self._refresh_preview()

    def _build_ui(self):
        lay = QHBoxLayout(self)

        # 左：参数输入
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        g = QFormLayout()
        g.setLabelAlignment(Qt.AlignRight)
        g.setSpacing(8)

        self.sp_len = QDoubleSpinBox(); self.sp_len.setRange(1,9999); self.sp_len.setValue(140.0); self.sp_len.setMaximumWidth(120)
        self.sp_wd  = QDoubleSpinBox(); self.sp_wd.setRange(1,9999);  self.sp_wd.setValue(145.0);  self.sp_wd.setMaximumWidth(120)
        self.sp_h   = QDoubleSpinBox(); self.sp_h.setRange(1,9999);   self.sp_h.setValue(58.0);   self.sp_h.setMaximumWidth(120)

        for sp in [self.sp_len, self.sp_wd, self.sp_h]:
            sp.valueChanged.connect(lambda _: self._refresh_preview())

        g.addRow("长度 L (mm)：", self.sp_len)
        g.addRow("宽度  W (mm)：", self.sp_wd)
        g.addRow("高度  H (mm)：", self.sp_h)
        ll.addLayout(g)

        # 预置
        preset_gb = QGroupBox("预置尺寸")
        pg = QVBoxLayout(preset_gb)
        presets = [("标准型 140×145×58", 140, 145, 58),
                   ("小型  100×100×45",   100, 100, 45),
                   ("大型  180×160×70",   180, 160, 70)]
        for label, l, w, h in presets:
            b = QPushButton(_get_icon("detector"), label)
            b.clicked.connect(lambda _, ll=l, ww=w, hh=h: self._set(ll, ww, hh))
            pg.addWidget(b)
        ll.addWidget(preset_gb)

        ll.addStretch()

        lay.addWidget(left)

        # 右：尺寸示意图
        self.preview = _SizePreviewWidget()
        lay.addWidget(self.preview, stretch=1)

        # 按钮
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        ll.addWidget(bb)

    def _set(self, l, w, h):
        self.sp_len.setValue(l)
        self.sp_wd.setValue(w)
        self.sp_h.setValue(h)

    def _refresh_preview(self):
        self.preview.set_size(self.sp_len.value(), self.sp_wd.value(), self.sp_h.value())

    def get_size(self):
        return self.sp_len.value(), self.sp_wd.value(), self.sp_h.value()


class _SizePreviewWidget(QWidget):
    """探测器三视图示意图"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.l, self.w, self.h = 140.0, 145.0, 58.0
        self.setMinimumSize(220, 220)
        self.setStyleSheet("background:#fff;border:1px solid #808080;")

    def set_size(self, l, w, h):
        self.l, self.w, self.h = l, w, h
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # 归一化缩放
        max_dim = max(self.l, self.w, self.h)
        scale = min(w, h) * 0.7 / max_dim
        cx, cy = w/2, h/2

        # 顶视图 (X-Y 平面，货舱顶视图)
        p.setPen(QPen(QColor(0,0,0), 1))
        p.setBrush(QBrush(QColor(200,200,255,120)))
        rx = self.l * scale / 2
        ry = self.w * scale / 2
        p.drawEllipse(int(cx-rx), int(cy-80-ry), int(rx*2), int(ry*2))
        p.setFont(QFont("Microsoft YaHei", 9)); p.setPen(QPen(QColor(0,0,0)))
        p.drawText(int(cx-rx+2), int(cy-80-ry-4), "顶视图")

        # 侧视图 (X-Z 平面)
        rx2 = self.l * scale / 2
        ry2 = self.h * scale / 2
        p.setBrush(QBrush(QColor(180,255,180,120)))
        p.drawEllipse(int(cx-rx2), int(cy+30-ry2), int(rx2*2), int(ry2*2))
        p.setFont(QFont("Microsoft YaHei", 9)); p.setPen(QPen(QColor(0,0,0)))
        p.drawText(int(cx-rx2+2), int(cy+30-ry2-4), "侧视图")

        # 尺寸标注
        p.setFont(QFont("Consolas", 8)); p.setPen(QPen(QColor(80,0,0)))
        p.drawText(int(cx+rx+4), int(cy-80), f"L={self.l:.0f}")
        p.drawText(int(cx+rx+4), int(cy-60+ry+4), f"W={self.w:.0f}")
        p.drawText(int(cx+rx2+4), int(cy+30+ry2+12), f"H={self.h:.0f}")
        p.end()


# ═══════════════════════════════════════════════════════════════════════
# 配置加载线程
# ═══════════════════════════════════════════════════════════════════════
class ConfigLoadThread(QThread):
    loaded = Signal(SimulationConfig, str)
    error  = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            cfg = SimulationConfig.from_json(self.path)
            self.loaded.emit(cfg, self.path)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════════
# 仿真线程
# ═══════════════════════════════════════════════════════════════════════
class SimulationThread(QThread):
    progress   = Signal(int, str)
    finished   = Signal(float, int, int)
    error      = Signal(str)
    detector_inf = Signal(list)
    log_msg    = Signal(str)

    def __init__(self, config, predictor, output_dir="."):
        super().__init__()
        self.config    = config
        self.predictor = predictor
        self.output_dir = output_dir
        self._stop    = False

    def run(self):
        try:
            rm  = ResultManager(output_dir=self.output_dir)
            eng = SimulationEngine(self.config, self.predictor, result_manager=rm)

            dets = eng.detector_info()
            self.detector_inf.emit(dets)
            for x, y, name, ch in dets:
                self.log_msg.emit(f"  [{name}] X={x:.0f}  Y={y:.0f}  Z={eng.cargobay.height_mm:.0f}")

            def on_progress(cur, tot, msg):
                pct = int(cur / max(tot, 1) * 95)
                self.progress.emit(min(pct, 95), msg)

            def on_stop():
                return self._stop

            cbs = GridScanCallbacks(on_progress=on_progress, on_stop=on_stop)

            t0 = time()
            eng.run_grid(callbacks=cbs)
            t1 = time()

            df     = rm.latest_dataframe
            failed = int(len(df[df["Alarm"] == False]))
            total  = int(len(df))
            self.log_msg.emit(f"\n仿真完成！耗时 {t1-t0:.1f}秒，共 {total} 次测试，失败 {failed} 次")
            self.progress.emit(100, "完成")
            self.finished.emit(t1-t0, failed, total)

        except Exception as e:
            import traceback; traceback.print_exc()
            self.error.emit(str(e))

    def stop(self):
        self._stop = True


# ═══════════════════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.predictor    = None
        self.inputs       = None
        self.sim_thread   = None
        self.load_thread  = None
        self.output_dir   = "."
        self._build_ui()

    # ── UI 构建 ─────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("烟雾检测仿真系统 v5.0")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 820)
        self.setStyleSheet(self._style_sheet())

        cw = QWidget()
        self.setCentralWidget(cw)
        v = QVBoxLayout(cw)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(1)

        self._build_menu()
        self._build_toolbar(v)
        self._build_tabs(v)
        self._build_log(v)
        self._build_statusbar()

    def _style_sheet(self):
        return """
        QMainWindow, QWidget { background:#c0c0c0; font-family:"Segoe UI",Microsoft YaHei; font-size:11px; }
        QLabel { background:transparent; }
        QGroupBox {
            background:#e8e8e8;
            border:1px solid #808080;
            margin-top:8px;
            padding-top:8px;
            font-weight:bold;
        }
        QGroupBox::title { subcontrol-origin:margin; left:8px; padding:2px 6px; }
        QPushButton {
            background:#ece9d8; border:1px solid #808080;
            padding:4px 16px; min-width:75px;
        }
        QPushButton:hover { background:#d4d0c8; }
        QPushButton:pressed { background:#b8b4a8; }
        QPushButton:disabled { background:#e0e0e0; color:#a0a0a0; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background:#fff; border:1px solid #808080; padding:2px 4px;
        }
        QTextEdit, QTableWidget { background:#fff; border:1px solid #808080; }
        QProgressBar {
            border:1px solid #808080; background:#ece9d8;
            text-align:center; min-height:20px;
        }
        QTabWidget::pane { border:1px solid #808080; background:#fff; }
        QTabBar::tab {
            background:#c0c0c0; border:1px solid #808080;
            padding:5px 20px;
        }
        QTabBar::tab:selected { background:#fff; border-bottom-color:#fff; }
        QMenuBar { background:#ece9d8; border-bottom:1px solid #808080; }
        QMenuBar::item:selected { background:#c0c0c0; }
        QMenu { background:#ece9d8; border:1px solid #808080; }
        QMenu::item:selected { background:#c0c0c0; }
        QStatusBar { background:#ece9d8; border-top:1px solid #808080; }
        QToolBar { background:#ece9d8; border-bottom:1px solid #808080; }
        """

    # ── 菜单栏 ─────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()
        f  = mb.addMenu("文件(&F)")
        f.addAction(_get_icon("open"),    "打开配置...", self._open_config, "Ctrl+O")
        f.addAction(_get_icon("save"),    "保存配置...", self._save_config, "Ctrl+S")
        f.addAction(_get_icon("model"),   "加载模型...", self._open_model)
        f.addSeparator()
        f.addAction(_get_icon("detector"),"探测器尺寸...", self._open_detector_size)
        f.addSeparator()
        f.addAction("退出", self.close, "Ctrl+Q")

        h = mb.addMenu("帮助(&H)")
        h.addAction(_get_icon("help"), "关于", self._show_about)

    # ── 工具栏 ─────────────────────────────────────────
    def _build_toolbar(self, parent):
        tb = self.addToolBar("主工具栏")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))

        self.btn_open    = QPushButton(_get_icon("open"),   "打开")
        self.btn_model   = QPushButton(_get_icon("model"),  "加载模型")
        self.btn_run     = QPushButton(_get_icon("run"),    "运行")
        self.btn_stop    = QPushButton(_get_icon("stop"),   "停止")
        self.btn_chart   = QPushButton(_get_icon("chart"), "图表")
        self.btn_compare = QPushButton(_get_icon("compare"),"对比")
        self.btn_export  = QPushButton(_get_icon("export"), "导出")

        for b in [self.btn_open, self.btn_model, self.btn_run,
                  self.btn_stop, self.btn_chart, self.btn_compare, self.btn_export]:
            b.setMaximumHeight(28); b.setMinimumWidth(76)

        self.btn_stop.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_chart.setEnabled(False)
        self.btn_compare.setEnabled(False)
        self.btn_export.setEnabled(False)

        self.btn_open.clicked.connect(self._open_config)
        self.btn_model.clicked.connect(self._open_model)
        self.btn_run.clicked.connect(self._run)
        self.btn_stop.clicked.connect(self._stop)
        self.btn_chart.clicked.connect(self._show_chart)
        self.btn_compare.clicked.connect(self._show_compare)
        self.btn_export.clicked.connect(self._export)

        for w in [self.btn_open, self.btn_model, None,
                  self.btn_run, self.btn_stop, None,
                  self.btn_chart, self.btn_compare, self.btn_export]:
            if w is None: tb.addSeparator()
            else:          tb.addWidget(w)

        parent.addWidget(tb)

    # ── Tab 页 ─────────────────────────────────────────
    def _build_tabs(self, parent):
        self.tabs = QTabWidget()
        parent.addWidget(self.tabs, stretch=1)

        # ── Tab 0: 仿真 ──────────────────────────────
        sim = QWidget()
        simLay = QVBoxLayout(sim)
        simLay.setContentsMargins(6, 6, 6, 6)
        simLay.setSpacing(6)

        cfgTop = QHBoxLayout()
        cfgTop.setSpacing(10)

        gb1 = QGroupBox("基本参数")
        g1 = QFormLayout(gb1)
        g1.setLabelAlignment(Qt.AlignRight); g1.setSpacing(6); g1.setContentsMargins(8,18,8,8)

        self.le_type  = QLineEdit(); self.le_type.setMaximumWidth(200)
        self.sp_sdnum = QSpinBox(); self.sp_sdnum.setRange(2, 20); self.sp_sdnum.setSingleStep(2); self.sp_sdnum.setMaximumWidth(100)
        self.sp_width = QDoubleSpinBox(); self.sp_width.setRange(1,99999); self.sp_width.setMaximumWidth(100)
        self.sp_len   = QDoubleSpinBox(); self.sp_len.setRange(1,99999); self.sp_len.setMaximumWidth(100)
        self.sp_ht    = QDoubleSpinBox(); self.sp_ht.setRange(1,99999); self.sp_ht.setMaximumWidth(100)
        self.sp_crit  = QSpinBox(); self.sp_crit.setRange(1,9999); self.sp_crit.setMaximumWidth(100)

        g1.addRow("机型：", self.le_type)
        g1.addRow("探测器数量：", self.sp_sdnum)
        g1.addRow("货舱宽度(mm)：", self.sp_width)
        g1.addRow("货舱长度(mm)：", self.sp_len)
        g1.addRow("货舱高度(mm)：", self.sp_ht)
        g1.addRow("报警阈值(s)：", self.sp_crit)

        gb2 = QGroupBox("布局参数")
        g2 = QFormLayout(gb2)
        g2.setLabelAlignment(Qt.AlignRight); g2.setSpacing(6); g2.setContentsMargins(8,18,8,8)

        self.cb_method = QComboBox(); self.cb_method.addItems(["center","side"]); self.cb_method.setMaximumWidth(100)
        self.sp_fwd  = QSpinBox(); self.sp_fwd.setRange(0,99999); self.sp_fwd.setMaximumWidth(100)
        self.sp_aft  = QSpinBox(); self.sp_aft.setRange(0,99999); self.sp_aft.setMaximumWidth(100)
        self.sp_disp = QSpinBox(); self.sp_disp.setRange(0,99999); self.sp_disp.setMaximumWidth(100)

        g2.addRow("排布方式：", self.cb_method)
        g2.addRow("前端间距(mm)：", self.sp_fwd)
        g2.addRow("后端间距(mm)：", self.sp_aft)
        g2.addRow("偏移(mm)：", self.sp_disp)

        cfgTop.addWidget(gb1, stretch=1)
        cfgTop.addWidget(gb2, stretch=1)
        simLay.addLayout(cfgTop)

        # 参数变化 → 实时刷新
        for sp in [self.sp_sdnum, self.sp_width, self.sp_len,
                    self.sp_fwd, self.sp_aft, self.sp_disp]:
            sp.valueChanged.connect(self._refresh_vis_from_ui)
        self.cb_method.currentIndexChanged.connect(self._refresh_vis_from_ui)

        self.bay_wid = CargoBayWidget()
        simLay.addWidget(self.bay_wid, stretch=2)

        progLay = QHBoxLayout(); progLay.setSpacing(8)
        self.prog_bar = QProgressBar()
        self.lbl_st   = QLabel("未运行")
        self.lbl_st.setMinimumWidth(200)
        self.lbl_st.setStyleSheet("border:1px solid #808080; padding:2px 6px; background:#fff;")
        progLay.addWidget(QLabel("运行状态："))
        progLay.addWidget(self.prog_bar, stretch=1)
        progLay.addWidget(self.lbl_st)
        simLay.addLayout(progLay)

        self.tabs.addTab(sim, _get_icon("bay"), "仿真")

        # ── Tab 1: 探测器定位 ──────────────────────────
        self.drag_wid = DetectorDragWidget()
        self.drag_wid._main_win = self           # 反向引用，供 apply 按钮回调
        self.drag_wid.detectors_changed.connect(self._on_detectors_changed)
        self.tabs.addTab(self.drag_wid, _get_icon("drag"), "探测器定位")

        # ── Tab 2: 结果 ───────────────────────────────
        self.tbl = QTableWidget()
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tabs.addTab(self.tbl, _get_icon("chart"), "结果")

        # ── Tab 3: 设置 ───────────────────────────────
        setW = QWidget()
        setL = QFormLayout(setW)
        setL.setLabelAlignment(Qt.AlignRight); setL.setSpacing(8); setL.setContentsMargins(12,12,12,12)
        le_out = QLineEdit(); le_out.setText(self.output_dir)
        le_out.textChanged.connect(lambda t: setattr(self, 'output_dir', t))
        setL.addRow("输出目录：", le_out)

        lb_hist = QLabel("<b>仿真历史记录</b>（双击加载）")
        setL.addRow(lb_hist)
        self.lw_hist = QTableWidget()
        self.lw_hist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lw_hist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lw_hist.setColumnCount(4)
        self.lw_hist.setHorizontalHeaderLabels(["时间", "探测器", "总测试", "失败"])
        self.lw_hist.setMaximumHeight(160)
        self.lw_hist.itemDoubleClicked.connect(self._load_hist_result)
        setL.addRow(self.lw_hist)

        btn_reload = QPushButton(_get_icon("history"), "刷新历史")
        btn_reload.clicked.connect(self._reload_history)
        setL.addRow(btn_reload)
        self.tabs.addTab(setW, _get_icon("settings"), "设置")

        # ── Tab 4: 帮助 ───────────────────────────────
        helpW = QTextEdit(); helpW.setReadOnly(True)
        helpW.setHtml("""
        <h3>烟雾检测仿真系统 v5.0</h3><hr>
        <b>使用方法：</b>
        <ol>
          <li>「文件 → 打开配置」加载 <code>inputs.json</code></li>
          <li>「文件 → 加载模型」加载 <code>.model</code></li>
          <li>修改参数后「运行」</li>
          <li>「探测器定位」Tab 可拖拽调整每个探测器位置</li>
        </ol>
        <b>快捷键：</b><ul>
          <li><code>Ctrl+O</code> 打开配置  <code>Ctrl+S</code> 保存配置</li>
        </ul>
        <hr><small>v5.0 | 仿真引擎 + 结果管理架构</small>
        """)
        self.tabs.addTab(helpW, _get_icon("help"), "帮助")

    # ── 日志区 ─────────────────────────────────────────
    def _build_log(self, parent):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(4, 2, 4, 2); l.setSpacing(2)
        hdr = QLabel("日志")
        hdr.setStyleSheet("font-weight:bold; padding:2px;")
        self.log = QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(100)
        l.addWidget(hdr); l.addWidget(self.log)
        parent.addWidget(w)

    # ── 状态栏 ─────────────────────────────────────────
    def _build_statusbar(self):
        self.statusBar().showMessage("就绪")

    # ── 实时刷新可视化 ─────────────────────────────────
    def _refresh_vis_from_ui(self):
        try:
            n      = self.sp_sdnum.value()
            w      = self.sp_width.value()
            l      = self.sp_len.value()
            method = self.cb_method.currentText()
            fwd    = self.sp_fwd.value()
            aft    = self.sp_aft.value()
            disp   = self.sp_disp.value()
            sd_l   = getattr(self.inputs, 'sd_length_mm', 140.0)
            sd_w   = getattr(self.inputs, 'sd_width_mm',  145.0)
            sd_dim = (sd_l, sd_w)
            half   = n // 2

            if method == "center":
                gap = (l - fwd - aft - sd_dim[0]*half) / max(half-1, 1)
                xg  = [fwd + sd_dim[0]/2]
                for _ in range(half-1):
                    xg.append(xg[-1] + gap + sd_dim[0])
                xg[-1] = l - aft - sd_dim[0]/2
                yg = [w/2 + disp + sd_dim[1]/2, w/2 - disp - sd_dim[1]/2]
            else:
                gap = (l - fwd - aft - sd_dim[0]*n) / max(n-1, 1)
                xg  = [fwd + sd_dim[0]/2]
                for _ in range(n-1):
                    xg.append(xg[-1] + gap + sd_dim[0])
                xg[-1] = l - aft - sd_dim[0]/2
                yg = [w/2 + disp + sd_dim[1]/2, w/2 - disp - sd_dim[1]/2]

            dets = []
            for i in range(n):
                ch = 0 if i % 2 == 0 else 1
                x  = xg[i//2]
                y  = yg[0] if ch == 0 else yg[1]
                dets.append((x, y, f"SD{i+1}", ch))

            self.bay_wid.set_layout(dets, w, l)
            self.bay_wid.clear_heatmap()

            # 同步到拖拽界面
            self.drag_wid.init_detectors(dets, w, l)
        except Exception:
            pass

    # ── 探测器尺寸对话框 ───────────────────────────────
    def _open_detector_size(self):
        dlg = DetectorSizeDialog(self)
        if dlg.exec():
            l, w, h = dlg.get_size()
            if self.inputs:
                self.inputs.sd_length_mm = l
                self.inputs.sd_width_mm  = w
            self.log.append(f"探测器尺寸已更新: {l:.0f} x {w:.0f} x {h:.0f} mm")
            self._refresh_vis_from_ui()

    # ── 配置加载（异步）────────────────────────────────
    def _open_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开配置", ".", "JSON (*.json)")
        if not path: return

        self.btn_open.setEnabled(False)
        self.log.append(f"正在加载: {path} ...")
        self.statusBar().showMessage("加载中...")

        self.load_thread = ConfigLoadThread(path)
        self.load_thread.loaded.connect(self._on_config_loaded)
        self.load_thread.error.connect(self._on_config_error)
        self.load_thread.start()

    def _on_config_loaded(self, cfg, path):
        self.inputs = cfg
        self._sync_ui_from_cfg()          # ① 同步 UI 参数控件
        self._refresh_vis_from_ui()        # ② 刷新货舱可视化 + 拖拽页探测器列表
        self.log.append(f"已加载配置: {path}")
        self.statusBar().showMessage(f"配置: {os.path.basename(path)}")
        self.btn_open.setEnabled(True)
        self.btn_run.setEnabled(self.predictor is not None)
        # 加载配置后自动切换到探测器定位 Tab，让用户确认布局
        self.tabs.setCurrentWidget(self.drag_wid)
        self.log.append("[提示] 请检查探测器定位 Tab，确认布放后再运行仿真")

    def _on_config_error(self, msg):
        self.btn_open.setEnabled(True)
        self.statusBar().showMessage("加载失败")
        QMessageBox.critical(self, "错误", msg)

    def _save_config(self):
        if not self.inputs:
            QMessageBox.warning(self, "提示", "请先加载配置文件再保存")
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", "inputs.json", "JSON (*.json)")
        if not path: return
        try:
            self.inputs.type_      = self.le_type.text() or "unknown"
            self.inputs.sd_num     = self.sp_sdnum.value()
            self.inputs.bay.width_mm  = self.sp_width.value()
            self.inputs.bay.length_mm = self.sp_len.value()
            self.inputs.bay.height_mm  = self.sp_ht.value()
            self.inputs.criteria_s     = self.sp_crit.value()
            self.inputs.arrange.method      = self.cb_method.currentText()
            self.inputs.arrange.fwd_mm      = self.sp_fwd.value()
            self.inputs.arrange.aft_mm      = self.sp_aft.value()
            self.inputs.arrange.displace_mm = self.sp_disp.value()
            self.inputs.to_json(path)
            self.log.append(f"配置已保存: {path}")
            self.statusBar().showMessage(f"已保存: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载模型", ".", "Model (*.model)")
        if not path: return
        try:
            self.predictor = load_model(path)
            self.log.append(f"模型已加载: {path}")
            self.btn_run.setEnabled(self.inputs is not None)
            self.statusBar().showMessage(f"模型: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def _sync_ui_from_cfg(self):
        if not self.inputs: return
        self.le_type.setText(self.inputs.type_)
        self.sp_sdnum.setValue(self.inputs.sd_num)
        self.sp_width.setValue(self.inputs.bay.width_mm)
        self.sp_len.setValue(self.inputs.bay.length_mm)
        self.sp_ht.setValue(self.inputs.bay.height_mm)
        self.sp_crit.setValue(self.inputs.criteria_s)
        self.cb_method.setCurrentText(self.inputs.arrange.method)
        self.sp_fwd.setValue(self.inputs.arrange.fwd_mm)
        self.sp_aft.setValue(self.inputs.arrange.aft_mm)
        self.sp_disp.setValue(self.inputs.arrange.displace_mm)
        self.sp_sdnum.setValue(self.inputs.sd_num)

    # ── 探测器定位界面同步 ─────────────────────────────
    def _on_detectors_changed(self, detectors):
        """拖拽界面探测器位置变化，同步到主界面"""
        if not detectors:
            return
        w = self.sp_width.value()
        l = self.sp_len.value()
        self.bay_wid.set_layout(detectors, w, l)

    def sync_from_drag_widget(self, detectors, bay_width, bay_length):
        """
        「应用到仿真」按钮回调：
        把拖拽界面的探测器布局完全同步进仿真参数。
        1. 更新仿真 Tab 的探测器数量
        2. 更新货舱尺寸
        3. 同步到货舱可视化
        4. 仿真时会用这些精确坐标跑
        """
        n = len(detectors)
        self.sp_sdnum.setValue(n)
        self.sp_width.setValue(int(bay_width))
        self.sp_len.setValue(int(bay_length))
        self.bay_wid.set_layout(detectors, bay_width, bay_length)
        self.log.append(
            f"[探测器布局已更新] {n} 个探测器，"
            f"货舱 {int(bay_length)}x{int(bay_width)} mm，准备就绪"
        )

    # ── 仿真 ───────────────────────────────────────────
    def _run(self):
        if not self.predictor:
            QMessageBox.warning(self, "提示", "请先加载模型")
            return

        cfg = SimulationConfig(
            type_     = self.le_type.text() or "unknown",
            sd_num    = self.sp_sdnum.value(),
            bay       = BayConfig(
                width_mm  = self.sp_width.value(),
                length_mm = self.sp_len.value(),
                height_mm = self.sp_ht.value(),
            ),
            criteria_s = self.sp_crit.value(),
            arrange   = ArrangeConfig(
                method      = self.cb_method.currentText(),
                fwd_mm      = self.sp_fwd.value(),
                aft_mm      = self.sp_aft.value(),
                displace_mm = self.sp_disp.value(),
            ),
        )
        if self.inputs:
            cfg.sd_length_mm = self.inputs.sd_length_mm
            cfg.sd_width_mm  = self.inputs.sd_width_mm

        # 合并拖拽界面的探测器位置（如果用户在定位界面调整过）
        drag_dets = self.drag_wid.get_detectors()
        if drag_dets:
            cfg._custom_detectors = drag_dets

        errs = cfg.validate()
        if errs:
            QMessageBox.critical(self, "配置校验失败", "\n".join(errs))
            return

        self.inputs = cfg
        self.log.clear()
        self.log.append(f"开始仿真（{cfg.sd_num}探测器，网格{cfg.grid_points}点）...")

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.prog_bar.setValue(0)
        self.lbl_st.setText("运行中...")

        self.t = SimulationThread(cfg, self.predictor, self.output_dir)
        self.t.progress.connect(self._on_prog)
        self.t.finished.connect(self._on_done)
        self.t.error.connect(self._on_err)
        self.t.detector_inf.connect(self._on_det)
        self.t.log_msg.connect(self._on_log)
        self.t.start()

    def _stop(self):
        if self.t: self.t.stop()
        self.lbl_st.setText("已停止")

    def _on_prog(self, pct, msg):
        self.prog_bar.setValue(pct)
        self.lbl_st.setText(msg)

    def _on_done(self, elapsed, failed, total):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_st.setText(f"完成  —  {failed}/{total} 失败")
        self.btn_chart.setEnabled(True)
        self.btn_compare.setEnabled(True)
        self.btn_export.setEnabled(True)

        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if runs:
            df = rm.load_file(runs[0]["file"])
            self._fill_table(df)
            # ── 热力图（解析 Src Loc. 字符串）────────
            heatmap = {}
            for _, row in df.iterrows():
                loc_str = str(row.get("Src Loc.", ""))
                alarm   = bool(row.get("Alarm", False))
                x, y, _ = parse_src_loc(loc_str)
                if x is not None and (x > 0 or y > 0):
                    heatmap[(x, y)] = alarm
            self.bay_wid.set_heatmap(heatmap)
            self._reload_history()

    def _on_err(self, msg):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_st.setText("错误")
        QMessageBox.critical(self, "运行错误", msg)

    def _on_det(self, info):
        self.bay_wid.set_layout(info, self.sp_width.value(), self.sp_len.value())
        self.drag_wid.init_detectors(info, self.sp_width.value(), self.sp_len.value())

    def _on_log(self, msg):
        self.log.append(msg)

    # ── 结果表格 ───────────────────────────────────────
    def _fill_table(self, df):
        self.tbl.clear()
        self.tbl.setColumnCount(len(df.columns))
        self.tbl.setRowCount(len(df))
        self.tbl.setHorizontalHeaderLabels(list(df.columns))
        self.tbl.setSortingEnabled(True)
        for i, row in enumerate(df.itertuples(index=False)):
            for j, v in enumerate(row):
                self.tbl.setItem(i, j, QTableWidgetItem(str(v)))
        self.tbl.resizeColumnsToContents()
        self.tabs.setCurrentIndex(2)

    # ── 历史记录 ──────────────────────────────────────
    def _reload_history(self):
        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        self.lw_hist.setRowCount(len(runs))
        for i, r in enumerate(runs):
            meta = r.get("meta", {})
            ts   = meta.get("timestamp", "")
            sd   = meta.get("sd_num", "?")
            total = meta.get("n_rows", 0)
            failed = ""
            try:
                df = rm.load_file(r["file"])
                total  = len(df)
                failed = int(len(df[df["Alarm"] == False]))
            except Exception:
                pass
            self.lw_hist.setItem(i, 0, QTableWidgetItem(ts))
            self.lw_hist.setItem(i, 1, QTableWidgetItem(str(sd)))
            self.lw_hist.setItem(i, 2, QTableWidgetItem(str(total)))
            self.lw_hist.setItem(i, 3, QTableWidgetItem(str(failed)))

    def _load_hist_result(self, item):
        row = item.row()
        rm  = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if 0 <= row < len(runs):
            df = rm.load_file(runs[row]["file"])
            self._fill_table(df)
            # 同时刷新热力图
            heatmap = {}
            for _, row_df in df.iterrows():
                loc_str = str(row_df.get("Src Loc.", ""))
                alarm   = bool(row_df.get("Alarm", False))
                x, y, _ = parse_src_loc(loc_str)
                if x is not None and (x > 0 or y > 0):
                    heatmap[(x, y)] = alarm
            self.bay_wid.set_heatmap(heatmap)

    # ── 图表 ──────────────────────────────────────────
    def _show_chart(self):
        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if not runs: return
        df = rm.load_file(runs[0]["file"])

        import matplotlib
        matplotlib.use("Qt5Agg")
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(1, 2, figsize=(13, 5))

        alarm_df = df[df["Alarm"] == True]
        for col in [c for c in df.columns if c.startswith("SD")]:
            times = alarm_df[col].dropna()
            if len(times) > 0:
                axes[0].hist(times, bins=30, alpha=0.6, label=col)
        axes[0].set_xlabel("报警时间(s)"); axes[0].set_ylabel("频次")
        axes[0].legend(); axes[0].set_title("各通道报警时间分布")

        alarm_counts = df["Alarm"].value_counts()
        labels = ["报警", "未报警"]
        sizes  = [alarm_counts.get(True, 0), alarm_counts.get(False, 0)]
        colors = ["#4caf50", "#f44336"]
        axes[1].pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        axes[1].set_title("报警成功率")

        fig.tight_layout(); plt.show()

    # ── 对比 ───────────────────────────────────────────
    def _show_compare(self):
        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if len(runs) < 2:
            QMessageBox.information(self, "提示", "需要至少 2 次仿真记录才能对比")
            return

        run_names = [f"{i+1}. {r['meta'].get('timestamp','?')} ({r['meta'].get('sd_num','?')}探测器)"
                     for i, r in enumerate(runs[:10])]
        sel, ok = QInputDialog.getItem(self, "第一次仿真", "选择第一次：", run_names, 0, False)
        if not ok: return
        idx1 = run_names.index(sel)

        sel2, ok2 = QInputDialog.getItem(self, "第二次仿真", "选择第二次：",
                                          run_names, 1 if idx1 == 0 else 0, False)
        if not ok2: return
        idx2 = run_names.index(sel2)

        df1 = rm.load_file(runs[idx1]["file"])
        df2 = rm.load_file(runs[idx2]["file"])

        import matplotlib
        matplotlib.use("Qt5Agg")
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        width = 0.35

        fail1 = len(df1[df1["Alarm"] == False])
        fail2 = len(df2[df2["Alarm"] == False])
        alarm1, alarm2 = len(df1) - fail1, len(df2) - fail2
        x = range(2)
        axes[0].bar([i-width/2 for i in x], [alarm1, alarm2], width, label="报警", color="#4caf50")
        axes[0].bar([i+width/2 for i in x], [fail1, fail2], width, label="未报警", color="#f44336")
        axes[0].set_xticks(list(x)); axes[0].set_xticklabels(["第一次", "第二次"])
        axes[0].legend(); axes[0].set_title("报警 vs 未报警 对比"); axes[0].set_ylabel("次数")

        sd_cols = [c for c in df1.columns if c.startswith("SD")]
        if sd_cols:
            alarm_df1 = df1[df1["Alarm"] == True]
            alarm_df2 = df2[df2["Alarm"] == True]
            means1 = [alarm_df1[col].dropna().mean() if alarm_df1[col].notna().any() else 0 for col in sd_cols]
            means2 = [alarm_df2[col].dropna().mean() if alarm_df2[col].notna().any() else 0 for col in sd_cols]
            x2 = range(len(sd_cols))
            axes[1].bar([i-width/2 for i in x2], means1, width, label="第一次", color="#2196f3", alpha=0.8)
            axes[1].bar([i+width/2 for i in x2], means2, width, label="第二次", color="#ff9800", alpha=0.8)
            axes[1].set_xticks(list(x2)); axes[1].set_xticklabels(sd_cols, rotation=30, fontsize=8)
            axes[1].legend(); axes[1].set_title("各通道平均报警时间(s) 对比"); axes[1].set_ylabel("平均时间(s)")

        fig.tight_layout(); plt.show()

    # ── 导出 ───────────────────────────────────────────
    def _export(self):
        rm = ResultManager(output_dir=self.output_dir)
        runs = rm.list_runs()
        if not runs: return
        df = rm.load_file(runs[0]["file"])
        path, _ = QFileDialog.getSaveFileName(self, "导出结果", "result_export.csv", "CSV (*.csv)")
        if path:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            self.log.append(f"已导出: {path}")

    # ── 关于 ───────────────────────────────────────────
    def _show_about(self):
        QMessageBox.about(self, "关于",
            "<h3>烟雾检测仿真系统 v5.0</h3>"
            "<p>Python 3 + PySide6 + scikit-learn</p>"
            "<p>仿真引擎 + 结果管理架构</p>"
            "<p>新增：探测器拖拽定位 / 报警热力图 / 尺寸设置</p>"
        )


# ── 入口 ─────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w   = MainWindow()
    w.show()
    sys.exit(app.exec())
