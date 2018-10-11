# -*- coding:utf-8  -*-

import os
import pickle
import wx
import gui
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment
from time import time

# SD_NUM = 6
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
    app = wx.App(False)
    MainWnd = gui.MainWindow("CARGO BAY SMOKE DETECTION SYSTEM SIMULATOR")
    
    app.MainLoop()

    # predictor = load_model(os.getcwd()+'\\rf_model_all.model')
    # FWD_cargobay = CargoBay(width=4166, length=16184, height=1727.6)
    # dets = [Detector(predictor) for i in range(SD_NUM)]
    # Env1 = Environment(cargobay_obj=FWD_cargobay,
    #                    detector_series=dets, detector_qty=SD_NUM)
    # Env1.arrange(fwd_space=100, aft_space=100)
    # t1 = time()
    # Env1.run(mode = 'all')
    # t2 = time()
    # print('Time used:{:.2f} seconds'.format(t2-t1))
    # Env1.output()

if __name__ == "__main__":
    main()
