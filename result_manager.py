# -*- coding:utf-8 -*-
"""
result_manager.py — 仿真结果管理抽象

原来 Environment.run() 里直接 `open('test_result.csv', 'w')` 写死文件名，
结果文件无法版本化管理，每次运行都覆盖，且无法指定输出目录。

ResultManager 解决：
- 每次运行生成带时间戳的独立文件，不覆盖旧结果
- 可配置输出目录
- 结果在内存中按 DataFrame 管理，按需导出
- 支持 CSV / JSON 多种格式
- 支持追加模式（同一实验的多次仿真）

用法：
    rm = ResultManager(output_dir="results")
    rm.start_run(include_inputs=True)
    for row in simulation_rows:
        rm.append_row(row)
    rm.finalize()
    print(rm.latest_file)   # /path/to/result_20260418_143022.csv
"""
from __future__ import annotations

import csv
import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


class ResultManager:
    """
    仿真结果管理器。

    每一次仿真是一次 "run"：
        rm.start_run()       → 打开新文件，写 header
        rm.append_row(dict) → 写入一行
        rm.finalize()        → 关闭文件，写入元信息

    同一 run 内可以追加多次仿真结果，共享同一个 CSV 文件。
    """

    DEFAULT_FILENAME_FMT = "result_{timestamp}.csv"

    def __init__(
        self,
        output_dir: str | Path = ".",
        filename_fmt: str | None = None,
        timestamp_fmt: str = "%Y%m%d_%H%M%S",
    ):
        """
        Args:
            output_dir:   结果文件输出目录（不存在则自动创建）
            filename_fmt: 文件名格式字符串，可用 {timestamp}。
                          默认为 `result_{timestamp}.csv`
            timestamp_fmt: timestamp 格式化字符串，传入 datetime.strftime()
        """
        self.output_dir   = Path(output_dir)
        self.filename_fmt = filename_fmt or self.DEFAULT_FILENAME_FMT
        self.timestamp_fmt = timestamp_fmt

        self._current_file:  Path | None = None
        self._writer:        csv.DictWriter | None = None
        self._file_handle:   object | None = None
        self._rows:           list[dict] = []
        self._run_started:    bool = False
        self._n_rows:        int = 0
        self._timestamp:      str = ""
        self._meta:           dict = {}

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def start_run(
        self,
        fieldnames: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        开始一次新的仿真 run，打开新文件并写入 header。

        Args:
            fieldnames: CSV 列名列表。如果 None，则在 append_row 时自动从第一行推导。
            metadata:   元信息 dict，会写入同名的 .meta.json 文件。
        """
        if self._run_started:
            self.finalize()

        self._timestamp = datetime.now().strftime(self.timestamp_fmt)
        filename = self.filename_fmt.format(timestamp=self._timestamp)
        self._current_file = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 元信息
        self._meta = dict(metadata or {})
        self._meta["timestamp"] = self._timestamp
        self._meta["n_rows"] = 0

        if fieldnames:
            self._file_handle = open(self._current_file, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file_handle, fieldnames=fieldnames)
            self._writer.writeheader()
            self._fieldnames = fieldnames

        self._rows = []
        self._n_rows = 0
        self._run_started = True

    def append_row(self, row: dict) -> None:
        """
        追加一行结果到当前 run。

        如果 start_run() 时没有传 fieldnames，则从第一行自动推导。
        """
        if not self._run_started:
            raise RuntimeError("Must call start_run() before append_row()")

        if self._writer is None:
            # 第一次写入，推导 fieldnames
            fieldnames = list(row.keys())
            self._file_handle = open(self._current_file, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file_handle, fieldnames=fieldnames)
            self._writer.writeheader()
            self._fieldnames = fieldnames

        self._writer.writerow(row)
        self._rows.append(row)
        self._n_rows += 1
        self._meta["n_rows"] = self._n_rows

    def append_dataframe(self, df: pd.DataFrame) -> None:
        """追加整个 DataFrame（一次性写入多行）"""
        for _, row in df.iterrows():
            self.append_row(row.to_dict())

    def finalize(self) -> None:
        """
        关闭当前 run 的文件，写入元信息。
        多次调用是安全的（幂等）。
        """
        if not self._run_started:
            return

        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
            self._writer = None

        # 写元信息文件
        meta_file = self._current_file.with_suffix(".meta.json")
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self._meta, f, indent=2, ensure_ascii=False)

        self._run_started = False

    @property
    def latest_file(self) -> Path | None:
        """最新一次 run 的结果文件路径"""
        return self._current_file

    @property
    def latest_dataframe(self) -> pd.DataFrame | None:
        """读取最新 run 的结果为 DataFrame"""
        if self._current_file is None or not self._current_file.exists():
            return None
        return pd.read_csv(self._current_file, encoding="utf-8")

    def load_file(self, path: str | Path) -> pd.DataFrame:
        """加载指定路径的 CSV 结果文件"""
        return pd.read_csv(Path(path), encoding="utf-8")

    def list_runs(self) -> list[dict]:
        """
        列出 output_dir 下所有 run（按修改时间倒序）。
        返回 [{"file": Path, "meta": dict, "n_rows": int}, ...]
        """
        runs = []
        for csv_file in sorted(self.output_dir.glob("result_*.csv"), key=os.path.getmtime, reverse=True):
            meta_file = csv_file.with_suffix(".meta.json")
            meta = {}
            if meta_file.exists():
                with open(meta_file, encoding="utf-8") as f:
                    meta = json.load(f)
            runs.append({
                "file":   csv_file,
                "meta":   meta,
                "n_rows": meta.get("n_rows", 0),
            })
        return runs

    def summary(self) -> pd.DataFrame:
        """
        返回所有 run 的摘要表格（文件 / 时间戳 / 行数）。
        """
        rows = []
        for run in self.list_runs():
            rows.append({
                "file":      run["file"].name,
                "timestamp": run["meta"].get("timestamp", ""),
                "n_rows":    run["n_rows"],
            })
        return pd.DataFrame(rows)

    def __enter__(self):
        self.start_run()
        return self

    def __exit__(self, *args):
        self.finalize()

    def __repr__(self):
        return (f"<ResultManager output_dir={str(self.output_dir)!r} "
                f"runs={len(self.list_runs())}>")
