# -*- coding:utf-8 -*-

import os
import wx
import json


class MainWindow(wx.Frame):
    def __init__(self,title,size=(1200,800)):
        wx.Frame.__init__(self,None,-1,title=title,size=size)
        
        