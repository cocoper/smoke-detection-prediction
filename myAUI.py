# -*- coding:utf-8 -*-

import os
import wx
import wx.lib.agw.aui as aui


class MainAUI(wx.Frame):
    def __init__(self,parent,id=-1,title="Smoke Detection System Simulator",
                size = (1248,1024),style=wx.DEFAULT_FRAME_STYLE):
        wx.Frame.__init__(self,parent=parent,id=id,title=title,
                        size=size,style=style)
        self._mgr = aui.AuiManager()

        #notify AUI which frame to use
        self._mgr.SetManagedWindow(self)

        # create text controls
        text1 = wx.TextCtrl(self,-1,"System Structure",
                            wx.DefaultPosition,wx.Size(200,150),
                            wx.NO_BORDER|wx.TE_MULTILINE)
        
        text2 = wx.TextCtrl(self,-1,"Main Window",
                            wx.DefaultPosition,wx.Size(200,150),
                            wx.NO_BORDER|wx.TE_MULTILINE)
        
        text3 = wx.TextCtrl(self,-1,"Log Window",
                            wx.DefaultPosition,wx.Size(200,150),
                            wx.NO_BORDER|wx.TE_MULTILINE)

        
        #Set pane 1 parameters

        paneinfo1 = aui.AuiPaneInfo()
        paneinfo1.Dock()
        paneinfo1.Left()
        paneinfo1.Floatable(False)

        #Set pane 2 parameters
        paneinfo2 = aui.AuiPaneInfo()
        paneinfo2.Dock()
        paneinfo2.Center()
        paneinfo2.Floatable(False)

        #Set pane 3 parameters
        paneinfo3 = aui.AuiPaneInfo()
        paneinfo3.Dock()
        paneinfo3.Bottom()
        paneinfo3.Floatable(False)


        
        #add the panes to the manager



        self._mgr.AddPane(text1,paneinfo1)
        self._mgr.AddPane(text2,paneinfo2)
        self._mgr.AddPane(text3,paneinfo3)
        
        self._mgr.Update()

        self.Bind(wx.EVT_CLOSE,self.OnClose)


    def OnClose(self,evt):
        self._mgr.UnInit()
        evt.Skip()


