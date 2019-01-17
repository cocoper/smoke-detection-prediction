# -*- coding:utf-8 -*-

import os
import json
import wx
import wx.adv
import wx.lib.agw.advancedsplash as AS
from main import RunMain
from wx.adv import Wizard as wiz
from wx.adv import WizardPageSimple


image_path = os.getcwd()+"\\src\\Images\\"


class MyGUIApp(wx.App):
    def OnInit(self):
        # self.frame = wx.Frame(parent=None, title="烟雾探测系统设计平台")
        self.frame = MainFrame()
        splashPath = image_path+"\\cargo_fire.png"
        splashBitmap = wx.Bitmap(splashPath,wx.BITMAP_TYPE_ANY)
        shadow =  wx.WHITE
        splash = AS.AdvancedSplash(self.frame,bitmap=splashBitmap,timeout = 100,
                                    agwStyle=AS.AS_TIMEOUT|
                                   AS.AS_CENTER_ON_SCREEN |
                                    AS.AS_SHADOW_BITMAP,
                                    shadowcolour=shadow
                                    )
        self.SetTopWindow(self.frame)
        self.frame.Show()
        return True


class MainFrame(wx.Frame):
    def __init__(self, 
                parent=None, 
                id=-1, 
                title="烟雾探测系统设计平台", 
                pos=wx.DefaultPosition):
        wx.Frame.__init__(self, parent, id, title,
                          size=(650, 1000), style=wx.DEFAULT_FRAME_STYLE)
        pnl = wx.Panel(self,-1)
        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        hbsizer = wx.BoxSizer(wx.VERTICAL)
        BtnPfrm = wx.Button(parent=pnl, label="系统性能分析")
        BtnOpt = wx.Button(parent=pnl, label="系统布置优化")
        BtnOpt.Enable(False)
        BtnExit = wx.Button(parent=pnl, label="系统退出")
        LogWnd = wx.TextCtrl(parent=pnl,id=-1,value="",
                            style=wx.TE_READONLY|
                            wx.TE_MULTILINE,size=(600,800))

        btnsizer.AddMany([BtnPfrm,BtnOpt,BtnExit])
        hbsizer.Add(btnsizer)
        hbsizer.Add(LogWnd)
        pnl.SetSizer(hbsizer)
        pnl.SetBackgroundColour('white')
        self.Bind(wx.EVT_BUTTON, self.OnBtnPfrm, BtnPfrm)
        self.Bind(wx.EVT_BUTTON, self.OnBtnOpt, BtnOpt)
        self.Bind(wx.EVT_BUTTON, self.OnBtnExit, BtnExit)

    def OnBtnPfrm(self,evt):
        # print("test")
        wizGUI = WizardGUI()
        if wizGUI.RunWizard():
            RunMain()
        else:
            wx.MessageBox("Wizard Canceled","Wizard Message")

    
    def OnBtnOpt(self,evt):
        pass
    def OnBtnExit(self,evt):
        self.Close()

class TitledPage(wx.adv.WizardPageSimple):
    def __init__(self, parent, title, name):
        WizardPageSimple.__init__(self, parent)
        self.radio_selection = 0
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.SetName(name)
        titleText = wx.StaticText(self, -1, title)
        # titleText.SetFont(
        #     wx.Font(18, wx.SWISS_FONT, wx.NORMAL_FONT, wx.FONTFLAG_BOLD)
        # )
        self.sizer.Add(titleText, 0, wx.ALIGN_CENTRE | wx.ALL, 5)
        self.sizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.ALL, 5)


class WizardGUI():
    def __init__(self):
        self.model_path = os.getcwd()+'\\rf_model_all.model'
        self.SimParam = {}
        self.logfrm = wx.Frame(parent=None, id=-1, title="log window",
                               size=(650, 1000), style=wx.DEFAULT_FRAME_STYLE)
        self.LogWnd = wx.TextCtrl(parent=self.logfrm, id=-1, value="",
                             style=wx.TE_READONLY |
                             wx.TE_MULTILINE, size=(600, 800))
        self.wizard = wiz(None, -1, 'Smoke detection prediction')
        self.page_title = ["设置货舱尺寸",
                           "设置探测器布置参数",
                           "设置探测器参数",
                           "设置仿真参数"]
        self.page_name = ["Bay Page", "Layout Page",
                          "Detector Page", "Param Setting Page"]
        self.page1 = TitledPage(
            self.wizard, self.page_title[0], self.page_name[0])
        self.page2 = TitledPage(
            self.wizard, self.page_title[1], self.page_name[1])
        self.page3 = TitledPage(
            self.wizard, self.page_title[2], self.page_name[2])
        self.page4 = TitledPage(
            self.wizard, self.page_title[3], self.page_name[3])

        # Layout Page1
        self.page1.sizer.Add((0, 30))
        page1_label = ['长(mm)', '宽(mm)', '高(mm)']
        page1_ctrlname = ['bay_length', 'bay_width', 'bay_height']
        # 注意，父窗口应该是page,不是wizard
        self.page1.sizer.Add(self.InputBox(
            self.page1, page1_label, page1_ctrlname))
        self.page1.Bind(
            wx.adv.EVT_WIZARD_PAGE_CHANGING, self.OnPageChange)
        self.page1.sizer.Add(wx.StaticLine(self.page1, -1),
                             0, wx.EXPAND | wx.ALL, 5)

        img1_1 = self.ScaleBitmap(image_path+"bay_fig.bmp", 2)
        img_sb1_1 = wx.StaticBitmap(self.page1, -1, img1_1)

        self.page1.sizer.Add(img_sb1_1)
        self.page1.SetSizerAndFit(self.page1.sizer)
        self.page1.Fit()
        self.wizard.FitToPage(self.page1)

        # /////////////////////////////////////////////////////////////
        # layout page2
        page2_label = ['探测器数量(个)', 'Gap1(mm)', 'Gap2(mm)', '偏移(mm)']
        page2_ctrlname = ['SD_qty', 'Gap1', 'Gap2', 'displace']

        img2_1 = self.ScaleBitmap(image_path+"center.jpg", 6)
        radio1 = wx.RadioButton(self.page2, -1, "居中布置", pos=(0, 30))
        img_sb2_1 = wx.StaticBitmap(self.page2, -1, img2_1)
        self.page2.sizer.Add(radio1)
        self.page2.sizer.Add(img_sb2_1)

        radio2 = wx.RadioButton(self.page2, -1, "交错布置", pos=(0, 70))
        img2_2 = self.ScaleBitmap(image_path+"side.jpg", 6)
        img_sb2_2 = wx.StaticBitmap(self.page2, -1, img2_2)
        self.page2.sizer.Add(radio2)
        self.page2.sizer.Add(img_sb2_2)

        # self.page2.sizer.AddMany([radio1, radio2])
        self.page2.sizer.Add((0, 30))
        self.page2.sizer.Add(self.InputBox(
            self.page2, page2_label, page2_ctrlname))
        self.page2.Bind(
            wx.adv.EVT_WIZARD_PAGE_CHANGING, self.OnPageChange)
        self.page2.Bind(wx.EVT_RADIOBUTTON, self.OnRadioLayout, radio1)
        self.page2.Bind(wx.EVT_RADIOBUTTON, self.OnRadioLayout, radio2)
        self.wizard.FitToPage(self.page2)

        # //////////////////////////////////////////////////////////////
        # layout page3
        page3_label = ['灵敏度(0.1~1)', '虚警率(0~1)', '探测器-长(mm)', '探测器-宽(mm)']
        self.page3_ctrlname = ['Sen', 'FAR', 'SD_len', 'SD_width']
        radio1 = wx.RadioButton(self.page3, -1, "默认", pos=(0, 40))
        radio2 = wx.RadioButton(self.page3, -1, "自定义", pos=(0, 60))
        self.page3.sizer.Add((0, 70))
        self.page3.sizer.Add(self.InputBox(
            self.page3, page3_label, self.page3_ctrlname))

        self.page3.Bind(wx.EVT_RADIOBUTTON, self.OnRadioDimension, radio1)
        self.page3.Bind(wx.EVT_RADIOBUTTON, self.OnRadioDimension, radio2)
        self.page3.Bind(wx.adv.EVT_WIZARD_PAGE_CHANGING, self.OnPageChange)

        # /////////////////////////////////////////////////////////////
        # layout page4
        page4_label = ['响应时间标准(秒)', '型号', '烟雾移动间隔(X向)', '烟雾移动间隔(Y向)']
        page4_ctrlname = ['criteria', 'Type', 'x_interval', 'y_interval']
        self.page4.sizer.Add((0, 30))
        self.page4.sizer.Add(self.InputBox(
            self.page4, page4_label, page4_ctrlname))
        model_selection_list = ['默认模型', '选择自定义模型']
        model_selection = wx.RadioBox(
            self.page4, -1, "选择预测模型", (0, 150), wx.DefaultSize,
            model_selection_list, 1, wx.RA_SPECIFY_COLS)
        self.page4.sizer.Add(model_selection)
        self.page4.Bind(wx.EVT_RADIOBOX, self.OnRadioModelSelection)
        self.page4.Bind(
            wx.adv.EVT_WIZARD_PAGE_CHANGING, self.OnPageChange)

        WizardPageSimple.Chain(self.page1, self.page2)
        WizardPageSimple.Chain(self.page2, self.page3)
        WizardPageSimple.Chain(self.page3, self.page4)

        self.logfrm.Show()
    
    def log(self,text):
        self.LogWnd.AppendText(text+'\n')


    def InputBox(self, parent, labels, names):
        rows = len(labels)
        cols = 2
        sizer = wx.FlexGridSizer(rows=rows, cols=cols, hgap=10, vgap=20)
        # sizer.Add(wx.StaticText(parent, -1, label), wx.ALIGN_LEFT)
        # sizer.Add(wx.TextCtrl(parent,-1),wx.ALIGN_LEFT)
        # sizer.Add((0, 20))  # 居中输入栏
        for label, name in zip(labels, names):
            sizer.Add(wx.StaticText(parent, -1, label),
                      wx.ALL | wx.ALIGN_LEFT, 0)
            # sizer.Add((10, 0))  # Add a spacer
            inputText = wx.TextCtrl(
                parent, -1, style=wx.TE_PROCESS_ENTER, name=name)
            inputText.SetInsertionPoint(0)
            sizer.Add(inputText)

        return sizer

    def OnRadioLayout(self, evt):
        radioSelected = evt.GetEventObject()
        self.page2.radio_selection = "center" if radioSelected.GetLabel() == "居中布置" else "side"
        # print(self.page2.radio_selection)
        self.SimParam['method'] = self.page2.radio_selection

    def OnRadioDimension(self, evt):
        radioSelected = evt.GetEventObject()
        if radioSelected.GetLabel() == "默认":
            # print("default")
            children_widgets = self.page3.sizer.GetChildren()

            for child in children_widgets:
                if child.GetSizer():
                    for sub_child in child.GetSizer():
                        widget = sub_child.GetWindow()
                # print(widget)
                        if isinstance(widget, wx.TextCtrl):
                            # print(widget)
                            widget.Enable(False)
            self.page3.radio_selection = "default"

        if radioSelected.GetLabel() == "自定义":
            # print("customize")
            children_widgets = self.page3.sizer.GetChildren()

            for child in children_widgets:
                if child.GetSizer():
                    for sub_child in child.GetSizer():
                        widget = sub_child.GetWindow()
                # print(widget)
                        if isinstance(widget, wx.TextCtrl):
                            # print(widget)
                            widget.Enable(True)
            self.page3.radio_selection = "custom"

    def OnRadioModelSelection(self, evt):
        rbox = evt.GetEventObject()
        # print(rbox.GetString(rbox.GetSelection()))
        if rbox.GetSelection() == 1:
            file_dlg = wx.FileDialog(self.page4, "Select your model file..."
                                     "", "", "Model files (.model)|.model",
                                     style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            if file_dlg.ShowModal() == wx.ID_OK:
                model_path = file_dlg.GetPath()
                if not os.path.splitext(model_path)[1]:
                    model_path = model_path + '.model'
                self.model_path = model_path
            # print(model_path)
            file_dlg.Destroy()
        else:
            self.model_path = os.getcwd()+'\\rf_model_all.model'

    def OnPageChange(self, evt):
        page = evt.GetPage()
        print(page.GetName())
        self.log(page.GetName())
        HasBlankValue = False
        children = page.sizer.GetChildren()
        params = self.GetValueFromSizer(children)
        for value in params.values():
            if value == "":
                HasBlankValue = True

        # 如果选择了默认，那么不判断是否有空值
        if page.GetName() == self.page_name[2] and page.radio_selection == "default":
            HasBlankValue = False
        # 如果inputbox有空值，提示不能为空
        if HasBlankValue is True:
            msgbox = wx.MessageBox("必须输入必要的参数", caption="请输入参数",
                                   style=wx.OK | wx.ICON_INFORMATION)
            evt.Veto()  # 事件停止
        else:
            self.SimParam.update(params)

    def GetValueFromSizer(self, sizeritems):
        value = {}
        for child in sizeritems:
            sub_sizer = child.GetSizer()
            if sub_sizer:
                for child in sub_sizer:
                    widget = child.GetWindow()
                    if isinstance(widget, wx.TextCtrl):
                        try:
                            value[widget.GetName()] = float(widget.GetValue())
                        except:
                            value[widget.GetName()] = widget.GetValue()

        return value

    def ScaleBitmap(self, bitmap, scale=2):
        '''
        bitmap: bitmap name in wx.ImageFromBitmap
        scale: scale factor
        '''
        image = wx.Image(bitmap, wx.BITMAP_TYPE_ANY)
        w = image.GetWidth()
        h = image.GetHeight()
        image = image.Scale(w/scale, h/scale, wx.IMAGE_QUALITY_HIGH)
        img = wx.Bitmap(image)
        return img

    def ReadDefaultParams(self):
        params = self.ReadInputs(os.getcwd()+"\\default.json")

        if self.page3.radio_selection == "default":
            for key in self.page3_ctrlname:
                self.SimParam[key] = params[key]

    def ReadInputs(self, file_path):
        with open(file_path, 'r', encoding='utf-8')as fp:
            inputs = json.load(fp)

        return inputs

    def CreateInputs(self, file_path):
        with open(file_path, 'w', encoding='utf-8')as fp:
            json.dump(self.SimParam, fp)

    def RunWizard(self):
        if self.wizard.RunWizard(self.page1):
            print("Sucess")
            self.ReadDefaultParams()
            print(self.SimParam)
            self.CreateInputs(os.getcwd()+"\\inputs.json")
            return True

#TODO: 单独创建每个页面的类
# TODO: 创建一个关于页面，声明版权
# TODO: 添加一个确认输入的对话框
# TODO: 创建一个Test summary页面，把在控制台中输出的信息放到这个页面中去，text ctrl, multi-line
# TODO: 优化UI代码结构,
# TODO:利用全局变量优化代码
# TODO: 修正点击了cancel按钮之后程序仍然在循环,和app.loop()有关
