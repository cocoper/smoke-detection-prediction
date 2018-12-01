# -*- coding:utf-8  -*-

import os
import pickle
import pandas as pd
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment
from time import time


SD_NUM = 6
TIME_CRI = 60  # in seconds


def load_model(model_path):  # load model
    with open(model_path, 'rb') as f:
        predictor = pickle.load(f)
    return predictor


def check_status(parameter_list):  # 检查所有输入数据是否正确
    pass


def read_sd(data_path):
    pass

def print_results(Start_time,End_time,data_path = 'test_result.csv'):
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        df_res = pd.read_csv(data_path)

        print('\n\n\n************Test Summary***********')
        print('Time elapsed:{:.2f} seconds'.format(End_time-Start_time))
        print('Failed Test counts:{:d}\n\n'.format(len(df_res[df_res.Alarm == False])))
        print(df_res.to_string())

        # df_res

#TODO 通过文件读入全部的输入数据

def main():
    # 输入cargobay几何数据
    # 输入SD几何数据

    predictor = load_model(os.getcwd()+'\\rf_model_all.model')
    FWD_cargobay = CargoBay(width=4166, length=16184, height=1727.6)
    dets = [Detector(predictor,name='SD'+str(i+1)) for i in range(SD_NUM)]
    Env1 = Environment(cargobay_obj=FWD_cargobay,
                       detector_series=dets, detector_qty=SD_NUM)
    Env1.arrange(fwd_space=100, aft_space=100)
    Start_T = time()
    Env1.run(mode = 'all')
    End_T = time()

    print_results(Start_time=Start_T,End_time= End_T)

if __name__ == "__main__":
    main()
