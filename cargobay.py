# -*- coding:uft-8 -*-


class CargoBay(object):
    def __init__(self, width=1000, length = 5000, height = 5000):
        self.width = width  # in millimeter
        self.length = length  # in millimeter
        self.height = height  # in millimeter

    def set_dimension(self, width=0,length=0,height=0):
        self.width = width # in millimeter
        self.length = length # in millimeter
        self.height = height # in millimeter
    
    def get_dimension():
        
        return tuple(self.width,self.length,self.height)

    def isinbay(pos):  #pos: list-like data
        
        isinwidth = pos[0] < self.width
        isinlength = pos[1] < self.length

        return isinlength & isinwidth
