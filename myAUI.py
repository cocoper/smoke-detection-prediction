# -*- coding:utf-8 -*-

import os
import wx
import wx.lib.agw.aui as aui

image_path = os.getcwd()+"\\src\\Images\\"


class MainAUI(wx.Frame):
    def __init__(self, parent, id=-1, title="Smoke Detection System Simulator",
                 size=(1248, 1024), style=wx.DEFAULT_FRAME_STYLE):
        wx.Frame.__init__(self, parent=parent, id=id, title=title,
                          size=size, style=style)
        self._mgr = aui.AuiManager()

        # notify AUI which frame to use
        self._mgr.SetManagedWindow(self)

        # create text controls
        # text1 = wx.TextCtrl(self,-1,"System Structure",
        #                     wx.DefaultPosition,wx.Size(200,150),
        #                     wx.NO_BORDER|wx.TE_MULTILINE)

        text2 = wx.TextCtrl(self, -1, "Main Window",
                            wx.DefaultPosition, wx.Size(200, 150),
                            wx.NO_BORDER | wx.TE_MULTILINE)

        text3 = wx.TextCtrl(self, -1, "Log Window",
                            wx.DefaultPosition, wx.Size(200, 150),
                            wx.NO_BORDER | wx.TE_MULTILINE)

        # panel1 = wx.Panel(self,-1,size=wx.Size(200,150))
        treepnl = TreeCtrlPanel(self,wx.Size(200,150))
        # Set pane 1 parameters

        paneinfo1 = aui.AuiPaneInfo()
        paneinfo1.Dock()
        paneinfo1.Left()
        paneinfo1.Floatable(False)
        paneinfo1.Caption("System Structure")
        paneinfo1.CloseButton(False)

        # Set pane 2 parameters
        paneinfo2 = aui.AuiPaneInfo()
        paneinfo2.Dock()
        paneinfo2.Center()
        paneinfo2.Floatable(False)
        paneinfo2.Caption("Main Window")
        paneinfo2.CloseButton(False)

        # Set pane 3 parameters
        paneinfo3 = aui.AuiPaneInfo()
        paneinfo3.Dock()
        paneinfo3.Bottom()
        paneinfo3.Floatable(False)
        paneinfo3.Caption("Log Window")
        paneinfo3.CloseButton(False)

        # add the panes to the manager

        self._mgr.AddPane(treepnl, paneinfo1)
        self._mgr.AddPane(text2, paneinfo2)
        self._mgr.AddPane(text3, paneinfo3)

        self._mgr.Update()
        
        # create menu
        menubar =wx.MenuBar()
        self.SetMenuBar(menubar)


        file_menu = wx.Menu()
        menuOpen = file_menu.Append(wx.ID_OPEN, "&Open", "打开数据文件")
        menuExit = file_menu.Append(wx.ID_EXIT, "E&xit", "退出")
        menubar.Append(file_menu, "文件")
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)

        model_menu = wx.Menu()
        menuload = model_menu.Append(wx.ID_ANY, "读取模型", "读取预测模型")
        menuEnv = model_menu.Append(wx.ID_ANY, "设置环境参数", "设置预测模型的环境参数")
        menuSD = model_menu.Append(wx.ID_ANY, "设置烟雾探测器", "设置烟雾探测器")
        menubar.Append(model_menu, "创建模型")
        # self.Bind(wx.EVT_MENU, self.OnSetSmokeDetector, menuSD)

        run_menu = wx.Menu()
        menurun = run_menu.Append(wx.ID_ANY, "运行", "开始模拟")
        # self.Bind(wx.EVT_MENU, self.OnRun, menurun)

        about_menu = wx.Menu()
        menuabt = about_menu.Append(wx.ID_ABOUT, "关于", "关于本软件的信息")
        menubar.Append(about_menu, "关于")
        self.Bind(wx.EVT_MENU, self.OnAbout, menuabt)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, evt):
        self._mgr.UnInit()
        evt.Skip()

    def OnExit(self, e):
        self.Close(True)

    def OnAbout(self, e):
        description = """ This is a generic aircraft smoke detection system simulator
        by machine learning

        Under developing

        """

        licence = """
        TBD
        """
        icon_path = os.path.join(image_path, 'icon_about.png')

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

class TreeCtrlPanel(wx.Panel):
    def __init__(self, parent, size=wx.DefaultSize):
        wx.Panel.__init__(self, parent, id=-1, size=size,
                          style=wx.WANTS_CHARS | wx.EXPAND | wx.ALL)
        self.tree = wx.TreeCtrl(self, -1, wx.DefaultPosition, size=size,
                                style=wx.TR_HAS_BUTTONS | wx.TR_EDIT_LABELS)

        self.root = self.tree.AddRoot("Fwd cargo bay")
        self.tree.SetItemData(self.root, None)

        for x in range(10):
            child = self.tree.AppendItem(
                self.root, "smoke detector {}".format(str(x)))
            # self.tree.SetItemData(child, None)

        self.tree.Expand(self.root)

        treesizer = wx.BoxSizer(wx.VERTICAL)
        treesizer.Add(self.tree,1,wx.EXPAND)
        self.SetSizer(treesizer)

