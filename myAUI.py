# -*- coding:utf-8 -*-

import os
import wx
import wx.lib.agw.aui as aui


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

        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnClose(self, evt):
        self._mgr.UnInit()
        evt.Skip()


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
            self.tree.SetItemData(child, None)

        self.tree.Expand(self.root)

        treesizer = wx.BoxSizer(wx.VERTICAL)
        treesizer.Add(self.tree,1,wx.EXPAND)
        self.SetSizer(treesizer)

