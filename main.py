# -*- coding:utf-8  -*-

import numpy as np
import pandas as pd
import os
import pickle
import Detector

SD_NUM = 10 
TIME_CRI = 60 # in seconds

def LoadModel(model_path,**kwg):  # load model
    with open(model_path,'rb') as f:
        regr = pickle.load(f)
    return regr


def check_status(parameter_list): #检查所有输入数据是否正确
    pass

def read_sd(data_path):
    pass

def main():
    #输入cargobay几何数据
    #输入SD几何数据
    pass

if __name__ == "__main__":
    main()
