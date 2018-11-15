# -*- coding:utf-8  -*-

import numpy as np
import pandas as pd
import os
import pickle
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment

SD_NUM = 10
TIME_CRI = 60  # in seconds


def load_model(model_path):  # load model
    with open(model_path, 'rb') as f:
        predictor = pickle.load(f)
    return predictor


def check_status(parameter_list):  # 检查所有输入数据是否正确
    pass


def read_sd(data_path):
    pass


def main():
    # 输入cargobay几何数据
    # 输入SD几何数据
    predictor = load_model(os.getcwd()+'\\rf_model_all.model')
    FWD_cargobay = CargoBay(width=4166, length=16184, height=1727.6)
    dets = [Detector(predictor) for i in range(SD_NUM)]
    Env1 = Environment(cargobay_obj=FWD_cargobay,
                       detector_series=dets, detector_qty=SD_NUM)
    Env1.arrange(fwd_space=100, aft_space=100)
    # Env1.set_source(3000, 2000)
    Env1.run(mode = 'all')
    Env1.output()


if __name__ == "__main__":
    main()
