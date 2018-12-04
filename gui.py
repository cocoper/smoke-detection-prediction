# -*- coding:utf-8 -*-

import os

import wx
import wx.adv

from Detector import Detector
from cargobay import CargoBay
from Environment import Environment
from time import time


class MainWindow(wx.Frame):
    def __init__(self, title, size=(1200, 800)):
        wx.Frame.__init__(self, None, -1, title=title,
                          size=size)

        self.CreateMenu()
        # Frame layout

        sketchpnl = SysLayoutPanel(self, wx.ID_ANY)
        logpnl = LogPanel(self, wx.ID_ANY)

        vbs = wx.BoxSizer(orient=wx.VERTICAL)
        vbs.Add(sketchpnl)
        vbs.Add(logpnl, flag=wx.TOP |
                wx.EXPAND | wx.ALIGN_BOTTOM, border=10)
        self.SetSizer(vbs)

        self.Center()
        self.Show()

    def OnAbout(self, e):
        description = """ This is a generic aircraft smoke detection system simulator
        by machine learning

        Under developing

        """

        licence = """
        TBD
        """
        icon_path = os.path.join(os.path.dirname(__file__), 'icon_about.png')

        info = wx.adv.AboutDialogInfo()

        info.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_PNG))
        info.SetName('Smoke Detection System Simulator')
        info.SetVersion('0.1')
        info.SetDescription(description)
        info.SetCopyright('(C) 2018 Xuan Yang. All rights reserved')
        info.SetWebSite('')
        info.SetLicence(licence)
        info.AddDeveloper('Xuan Yang')
        info.AddDocWriter('Xuan Yang')

        wx.adv.AboutBox(info)

    def OnSetSmokeDetector(self, evt):
        SDDlg = SmokeDetectorSetDlg(None, title='设置烟雾探测器属性')
        if SDDlg.ShowModal() == wx.ID_OK:
            # print(SDDlg.prop)
            return SDDlg.prop
        SDDlg.Destroy()

    def OnExit(self, e):
        self.Close(True)

    def CreateLogPanel(self):
        pass

    def CreateSysLayoutPanel(self):
        pass

    def CreateMenu(self):
        # Creating MenuBar
        menubar = wx.MenuBar()
        self.SetMenuBar(menubar)

        # Setting up the menu
        file_menu = wx.Menu()
        menuOpen = file_menu.Append(wx.ID_OPEN, "&Open", "打开数据文件")
        # menuAbout = file_menu.Append(wx.ID_ABOUT,"&About","关于本软件的信息")
        menuExit = file_menu.Append(wx.ID_EXIT, "E&xit", "退出")
        menubar.Append(file_menu, "文件")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)

        model_menu = wx.Menu()
        menuload = model_menu.Append(wx.ID_ANY, "读取模型", "读取预测模型")
        menuEnv = model_menu.Append(wx.ID_ANY, "设置环境参数", "设置预测模型的环境参数")
        menuSD = model_menu.Append(wx.ID_ANY, "设置烟雾探测器", "设置烟雾探测器")
        menubar.Append(model_menu, "创建模型")
        self.Bind(wx.EVT_MENU, self.OnSetSmokeDetector, menuSD)

        run_menu = wx.Menu()
        menurun = run_menu.Append(wx.ID_ANY, "运行", "开始模拟")
        self.Bind(wx.EVT_MENU, self.OnRun, menurun)

        about_menu = wx.Menu()
        menuabt = about_menu.Append(wx.ID_ABOUT, "关于", "关于本软件的信息")
        menubar.Append(about_menu, "关于")
        self.Bind(wx.EVT_MENU, self.OnAbout, menuabt)

    def OnClose(self, e):
        self.Destroy()

    def OnOk(self, e):
        idx = 0
        for key in self.prop.keys():
            try:
                self.prop[key] = float(self.txtctrl[idx].GetValue())
                idx += 1

            except:
                wx.MessageBox("Enter a number", "Warning!",
                              wx.OK | wx.ICON_WARNING)

        self.SetReturnCode(wx.ID_OK)
        self.Destroy()
        return self.prop

    def OnRun(self, evt):
        pass


class LogPanel(wx.Panel):
    def __init__(self, parent, ID):
        wx.Panel.__init__(self, parent, ID, style=wx.RAISED_BORDER)

        vbs1 = wx.BoxSizer(orient=wx.VERTICAL)
        logtext = wx.TextCtrl(
            self, size=(-1, 800), id=wx.ID_ANY, style=wx.TE_READONLY | wx.TE_DONTWRAP | wx.TE_MULTILINE)
        # logtext.SetSize((-1,800))
        vbs1.Add(logtext, flag=wx.EXPAND | wx.ALIGN_BOTTOM, border=10)
        self.SetSizer(vbs1)
        vbs1.Fit(self)


class SysLayoutPanel(wx.Panel):
    def __init__(self, parent, ID):
        wx.Panel.__init__(self, parent, ID)
        vbs1 = wx.BoxSizer(orient=wx.VERTICAL)
        sketch = wx.TextCtrl(self, id=wx.ID_ANY, style=wx.TE_MULTILINE)
        # sketch.SetSize((-1,-1))
        vbs1.Add(sketch)
        self.SetSizer(vbs1)
        vbs1.Fit(self)


class SmokeDetectorSetDlg(wx.Dialog):
    def __init__(self, *args, **kw):
        super(SmokeDetectorSetDlg, self).__init__(*args, **kw)

        self.sd_prop = {'Quantity': 6,
                        'False Alarm Rate': 0.01,
                        'Sensitivity': 0.98,
                        'TBD': 0}
        self.InitUI()
        self.SetSize((300, 300))
        self.Centre()
        self.SetTitle("Smoke Detector Setting")

    def InitUI(self):
        pnl = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        sb = wx.StaticBox(pnl, label="Smoke Detector")
        sbs = wx.StaticBoxSizer(sb, orient=wx.VERTICAL)
        fgsizer = wx.FlexGridSizer(4, 2, 5, 5)

        self.txtctrl = [wx.TextCtrl(pnl) for i in range(len(self.sd_prop))]
        idx = 0
        for label in self.sd_prop.keys():
            fgsizer.Add(wx.StaticText(pnl, id=wx.ID_ANY, label=label),
                        flag=wx.ALIGN_LEFT | wx.BOTTOM | wx.TOP, border=0)
            fgsizer.Add(self.txtctrl[idx], flag=wx.ALIGN_LEFT)
            idx += 1

        sbs.Add(fgsizer)

        pnl.SetSizer(sbs)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        okButton = wx.Button(self, label='Ok')
        closeButton = wx.Button(self, label='Close')
        hbox2.Add(okButton)
        hbox2.Add(closeButton, flag=wx.LEFT, border=5)

        vbox.Add(pnl, proportion=1,
                 flag=wx.ALL | wx.EXPAND, border=5)
        vbox.Add(hbox2, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        self.SetSizer(vbox)
        okButton.Bind(wx.EVT_BUTTON, self.OnOk)
        closeButton.Bind(wx.EVT_BUTTON, self.OnClose)
