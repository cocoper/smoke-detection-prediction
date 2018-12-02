# -*- coding:utf-8 -*-
import os
import pickle
import pandas as pd
from Detector import Detector
from cargobay import CargoBay
from Environment import Environment
from time import time

class simulator(object):
    def __init__(self):
        self.__DetProp = {'Qty': 6,
                          'FAR': 0.01,
                          'Sen': 0.98,
                          'TBD': 0}
        self.__CargoBayProp = {'width': 4166,
                                'length': 16184,
                                'height': 1727.6} # unit:mm
        self.__pred_path = os.getcwd()+'\\rf_model_all.model'
        self.pred = self.__load_model(self.__pred_path)
        self.__generate_env()

    def __load_model(self,model_path):  # load prediction model
        with open(model_path, 'rb') as f:
            predictor = pickle.load(f)
        return predictor

    def set_det_prop(self,DetProp):
        self.__DetProp = DetProp
    
    def set_bay_prop(self,CargobayProp):
        self.__CargoBayProp = CargobayProp

    def set_pred_path(self,PredPath):
        assert type(PredPath) == str, 'Incorrect model path' 
        self.__pred_path = PredPath

    def __generate_env(self):
        sd_qty = self.__DetProp['Qty']
        dets = [Detector(self.pred) for i in range(sd_qty)]
        cargobay = CargoBay()
        cargobay.set_prop(self.__CargoBayProp)
        self.env = Environment(cargobay,dets,sd_qty)

    def run(self):
        src_pos = self.env.movesrc(1000,500)
        src_x = 0
        src_y = 0
        res_alarm = []
        test_num = 0
        index = 0
        sd_keys = []
        sd_alarm = []
        while True:
            try:
                test_num += 1
                self.env.set_source(src_x, src_y)
                res_alarm.append(self.env.run(mode = 'singal'))
                src_x, src_y = next(src_pos)

            except StopIteration as evt:
                return "Source moving complete"
                break

        for sd in self.env.detectors:
            index += 1
            sd_keys.append('SD'+str(index))
            sd_alarm.append(sd.alarm_time)

        res_sd = dict(zip(sd_keys,sd_alarm))
        
        result = pd.DataFrame(data = res_sd,index = range(1,test_num))
        
