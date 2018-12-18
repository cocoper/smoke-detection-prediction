# -*- coding:utf-8 -*-

import os
import wx
import wx.adv
from wx.adv import Wizard as wiz
from wx.adv import WizardPage, WizardPageSimple
import json


class TitledPage(wx.adv.WizardPageSimple):
    def __init__(self, parent, title):
        WizardPageSimple.__init__(self, parent)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        titleText = wx.StaticText(self, -1, title)
        # titleText.SetFont(
        #     wx.Font(18, wx.SWISS_FONT, wx.NORMAL_FONT, wx.FONTFLAG_BOLD)
        # )
        self.sizer.Add(titleText, 0,wx.ALIGN_CENTRE|wx.ALL,5)
        self.sizer.Add(wx.StaticLine(self,-1),0,wx.EXPAND|wx.ALL,5)

class WizardGUIApp():
    def __init__(self):
        wizard = wiz(None,-1,'Simple Wizard')
        page1 = TitledPage(wizard,"page1")
        page2 = TitledPage(wizard,"page2")
        page3 = TitledPage(wizard,"page3")
        page4 = TitledPage(wizard,"page4")
        page1.sizer.Add(wx.StaticText(page1,-1,'Testing the wizard'))
        page4.sizer.Add(wx.StaticText(page4,-1,'This is the last page.'))
        WizardPageSimple.Chain(page1,page2)
        WizardPageSimple.Chain(page2,page3)
        WizardPageSimple.Chain(page3,page4)
        wizard.FitToPage(page1)

        if wizard.RunWizard(page1):
            print("Sucess")
