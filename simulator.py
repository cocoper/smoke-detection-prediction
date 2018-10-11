# -*- coding:utf-8 -*-
import os
import pickle
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
        Env = Environment(cargobay,dets,sd_qty)
    def run(self,mode):
        pass
