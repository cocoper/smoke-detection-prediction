import wx


class MyApp(wx.App):
    def __init__(self, redirect=False, filename=None):
        wx.App.__init__(self, redirect, filename)
        self.frame = wx.Frame(None, wx.ID_ANY, title='My Title')

        self.panel = wx.Panel(self.frame, wx.ID_ANY)


if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()
