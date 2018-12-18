# -*- coding:utf-8  -*-

import os
import pickle
import pandas as pd
import json
import SimpleGUI
import wx
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment
from time import time


SD_NUM = 6
TIME_CRI = 60  # in seconds


def load_model(model_file):  # load model
    with open(model_file, 'rb') as f:
        predictor = pickle.load(f)
    return predictor


def load_inputs(inputs_file):
    with open(inputs_file, 'r', encoding='utf-8')as read_file:
        inputs = json.load(read_file)

    return inputs


def check_status(parameter_list):  # 检查所有输入数据是否正确
    pass


def read_sd(data_path):
    pass


def print_results(summary, data_path='test_result.csv'):
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        df_res = pd.read_csv(data_path)

        print('\n\n\n------------Test Summary--------------\n\n\n')
        print('Type:{:>10}\n\n'.format(summary['Type']))
        print('Time elapsed:{:.2f} seconds\n\n'.format(summary['Time']))
        print('Fail Test counts:{:d}\n\n'.format(
            len(df_res[df_res.Alarm == False])))
        print(df_res.to_string())

def main():
    # 输入cargobay几何数据
    # 输入SD几何数据
    # 初始化仿真数据

    inputs = load_inputs('inputs.json') #load inputs
    AirType = inputs['Type']
    SD_NUM = inputs['SD_num']
    bay_dim = inputs['bay_dimension']
    Time_Crit = inputs['criteria']
    arrange = inputs['arrange']

    predictor = load_model(os.getcwd()+'\\rf_model_all.model')
    FWD_cargobay = CargoBay(
        width=bay_dim[0], length=bay_dim[1], height=bay_dim[0])
    dets = [Detector(predictor, name='SD'+str(i+1)) for i in range(SD_NUM)]

    Env1 = Environment(
        cargobay_obj=FWD_cargobay,
        detector_series=dets,
        detector_qty=SD_NUM,
        arrange=arrange,
        time_criteria=Time_Crit
    )

    # Env1.arrange(arrange_method=arrange['method'],
    #              fwd_space=arrange['fwd space'],
    #              aft_space=arrange['aft space']
    #              )

    Start_T = time()
    Env1.run(mode='all')
    End_T = time()

    runs_summary = {
        'Type': AirType,
        'Date': 'tbd',
        'Time': End_T-Start_T
    }

    print_results(runs_summary)


if __name__ == "__main__":
    # main()
    # app = SimpleGUI.WizardGUIApp()
    app = wx.App()
    wizGUI = SimpleGUI.WizardGUIApp()
    app.MainLoop()
    

