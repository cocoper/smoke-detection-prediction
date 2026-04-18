# -*- coding:utf-8 -*-
"""
sklearn_compat.py — 旧版 sklearn 模型兼容层

解决旧版 pickle 文件（sklearn < 1.0）与新版 sklearn (>= 1.3) 的兼容问题。
将 `sklearn.ensemble.forest` / `sklearn.tree.tree` 等旧模块路径重定向到新路径，
并对 Tree 对象补充缺失的 `missing_go_to_left` 字段。

用法：
    from sklearn_compat import load_model
    predictor = load_model('rf_model.model')
"""
from __future__ import annotations

import pickle
import numpy as np
import importlib as _importlib

# ------------------------------------------------------------------
# 1. 打补丁：把旧模块名映射到新模块
# ------------------------------------------------------------------
sys_modules = __import__('sys').modules
sys_modules['sklearn.ensemble.forest'] = _importlib.import_module('sklearn.ensemble._forest')
sys_modules['sklearn.tree.tree']       = _importlib.import_module('sklearn.tree')

from sklearn.tree._tree import Tree as _OrigTree

# ------------------------------------------------------------------
# 2. Tree 打补丁：补充 sklearn 1.1+ 新增的 missing_go_to_left 字段
# ------------------------------------------------------------------
class _PatchedTree(_OrigTree):
    """
    旧版 pickle 的 Tree 对象缺少 `missing_go_to_left` 字段，
    该字段在 sklearn 1.1+ 中引入，用于处理缺失值。
    这里在反序列化时动态补上。
    """
    def __setstate__(self, state):
        if isinstance(state, dict) and 'nodes' in state:
            nodes = state['nodes']
            if hasattr(nodes, 'dtype') and hasattr(nodes.dtype, 'names'):
                names = nodes.dtype.names or ()
                if 'missing_go_to_left' not in names:
                    new_names  = list(names) + ['missing_go_to_left']
                    new_formats = [nodes.dtype.fields[n][0].str for n in names] + ['u1']
                    new_dtype = np.dtype(list(zip(new_names, new_formats)))
                    new_arr = np.empty(nodes.shape, dtype=new_dtype)
                    for n in names:
                        new_arr[n] = nodes[n]
                    new_arr['missing_go_to_left'] = np.ones(len(new_arr), dtype='u1')
                    state = dict(state)
                    state['nodes'] = new_arr
        super().__setstate__(state)


# ------------------------------------------------------------------
# 3. Unpickler：遇到旧 Tree 时替换为 PatchedTree
# ------------------------------------------------------------------
class _CompatUnpickler(pickle.Unpickler):
    """
    自定义 unpickler，将旧版 sklearn 类替换为新版兼容类。
    """
    def find_class(self, module, name):
        new_mod = {
            'sklearn.ensemble.forest': 'sklearn.ensemble._forest',
            'sklearn.tree.tree':       'sklearn.tree',
        }.get(module, module)
        cls = super().find_class(new_mod, name)
        if cls is _OrigTree:
            return _PatchedTree
        return cls


# ------------------------------------------------------------------
# 4. 公开 API
# ------------------------------------------------------------------
class LegacyModelWrapper:
    """
    封装旧版 sklearn 模型，提供统一的 predict 接口。

    支持：
    - RandomForestRegressor
    - DecisionTreeRegressor
    - 任意实现了 .predict() 和 .estimators_ 的 sklearn 模型
    """
    def __init__(self, model):
        self._model          = model
        self.n_outputs_      = getattr(model, 'n_outputs_', 1)
        self.n_features_in_  = getattr(model, 'n_features_in_', None)
        self.estimators_     = getattr(model, 'estimators_', [])
        self.classes_        = getattr(model, 'classes_', None)

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, dtype=float))
        if X.ndim == 1:
            X = X.reshape(1, -1)
        predictions = np.array([t.predict(X) for t in self.estimators_])
        if self.n_outputs_ == 1:
            return np.mean(predictions, axis=0)
        return np.array([np.mean(predictions[:, i]) for i in range(self.n_outputs_)])

    def __repr__(self):
        return f"<LegacyModelWrapper: {self._model.__class__.__name__} n_estimators={len(self.estimators_)}>"


def load_model(path: str) -> LegacyModelWrapper:
    """
    加载旧版 sklearn pickle 模型文件，自动处理兼容性问题。

    Args:
        path: .model 文件路径（pickle 格式）

    Returns:
        LegacyModelWrapper 封装后的模型，可直接调用 .predict()
    """
    with open(path, 'rb') as f:
        raw = _CompatUnpickler(f).load()
    return LegacyModelWrapper(raw)
