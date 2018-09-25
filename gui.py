# -*- coding:utf-8 -*-

import wx
import wx.adv
import os


class MainWindow(wx.Frame):
    def __init__(self, parent, title, size=(1200, 800)):
        wx.Frame.__init__(self, parent, title=title, size=size)

        # Creating MenuBar
        menubar = wx.MenuBar()
        self.SetMenuBar(menubar)

        # Setting up the menu
        filemenu = wx.Menu()
        menuOpen = filemenu.Append(wx.ID_OPEN, "&Open", "打开数据文件")
        # menuAbout = filemenu.Append(wx.ID_ABOUT,"&About","关于本软件的信息")
        menuExit = filemenu.Append(wx.ID_EXIT, "E&xit", "退出")
        menubar.Append(filemenu, "文件")

        modlemenu = wx.Menu()
        menuload = modlemenu.Append(wx.ID_ANY, "读取模型", "读取预测模型")
        menuEnv = modlemenu.Append(wx.ID_ANY, "设置环境参数", "设置预测模型的环境参数")
        menuSD = modlemenu.Append(wx.ID_ANY, "设置烟雾探测器", "设置烟雾探测器")
        menubar.Append(modlemenu, "创建模型")

        aboutmenu = wx.Menu()
        menuabt = aboutmenu.Append(wx.ID_ABOUT, "关于", "关于本软件的信息")
        menubar.Append(aboutmenu, "关于")
        self.Bind(wx.EVT_MENU, self.OnAbout, menuabt)
        self.Bind(wx.EVT_MENU, self.OnSetSmokeDetector, menuSD)

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

    def OnSetSmokeDetector(self, e):
        SDDlg = SmokeDetectorSetDlg(None,title = '')
        SDDlg.ShowModal()
        SDDlg.Destroy()


class SmokeDetectorSetDlg(wx.Dialog):
    def __init__(self, *args, **kw):
        super(SmokeDetectorSetDlg, self).__init__(*args, **kw)

        self.InitUI()
        self.SetSize((500, 300))
        self.SetTitle("Smoke Detector Setting")

    def InitUI(self):
        pnl = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        sb = wx.StaticBox(pnl, label="Smoke Detector")
        sbs = wx.StaticBoxSizer(sb, orient=wx.VERTICAL)
        hbox = []
        proptext = ['Quantity:  ',
                    'False Alarm Rate:  ',
                    'Sensitivity:  ',
                    'TBD:  ']
        hbox = [wx.BoxSizer(wx.HORIZONTAL) for i in range(4)]

        for i in range(4):
            hbox[i].Add(wx.StaticText(pnl, id=wx.ID_ANY, label=proptext[i]))
            hbox[i].Add(wx.TextCtrl(pnl), flag=wx.LEFT, border=20)
            sbs.Add(hbox[i])
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
        okButton.Bind(wx.EVT_BUTTON,self.OnClose)
        closeButton.Bind(wx.EVT_BUTTON,self.OnClose)
    def OnClose(self, e):
        self.Destroy()


app = wx.App(False)
MainWnd = MainWindow(None, "Cargo bay smoke detection system simulator")
app.MainLoop()
