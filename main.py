# -*- coding:utf-8  -*-

import os
import json
from time import time
import pickle
import pandas as pd
import SimpleGUI
import wx
import myAUI
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment

LOAD_DEF = True

def load_model(model_file):  # load model
    with open(model_file, 'rb') as f:
        predictor = pickle.load(f)
    return predictor


def ReadInputs(inputs_file):
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


def RunMain():
    # 输入cargobay几何数据
    # 输入SD几何数据
    # 初始化仿真数据

    if LOAD_DEF:
        inputs = ReadInputs('default.json')  # load inputs
    else:
        inputs = ReadInputs('inputs.json')
    airplaneType = inputs['Type']
    SD_qty = int(inputs['SD_qty'])
    bay_width = inputs['bay_width']
    bay_length = inputs['bay_length']
    bay_height = inputs['bay_height']
    Time_Crit = inputs['criteria']
    arrange_method = inputs['method']
    SD_len = inputs['SD_len']
    SD_width = inputs['SD_width']
    SD_FAR = inputs['FAR']
    arrange = {
        'method': inputs['method'],
        'fwd_gap': inputs['Gap1'],
        'aft_gap': inputs['Gap2'],
        'displace': inputs['displace']
    }
    move_interval = [inputs['x_interval'],inputs['y_interval']]

    predictor = load_model(os.getcwd()+'\\rf_model_all.model')
    FWD_cargobay = CargoBay(
        width=bay_width, length=bay_length, height=bay_height)
    dets = [Detector(predictor, (SD_width, SD_len), name='SD' +
                     str(i+1), FalseAlarmRate=SD_FAR) for i in range(SD_qty)]

    Env1 = Environment(
        cargobay_obj=FWD_cargobay,
        detector_series=dets,
        detector_qty=SD_qty,
        arrange=arrange,
        time_criteria=Time_Crit,
        move_interval=move_interval
    )

    Start_T = time()
    Env1.run(mode='all')
    End_T = time()

    runs_summary = {
        'Type': airplaneType,
        'Date': 'tbd',
        'Time': End_T-Start_T
    }

    print_results(runs_summary)


if __name__ == "__main__":
    # main()
    # app = SimpleGUI.MyGUIApp(redirect=False,useBestVisual=True)
    app = wx.App()

    AUIfrm = myAUI.MainAUI(None)
    app.SetTopWindow(AUIfrm)
    AUIfrm.Show()
    app.MainLoop()
