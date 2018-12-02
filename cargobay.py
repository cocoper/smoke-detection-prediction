# -*- coding:utf-8 -*-


class CargoBay(object):
    def __init__(self, width=1000, length = 5000, height = 5000):
        assert width > 0,'width should be greater than 0'
        assert length > 0, 'length should be greater than 0'
        assert height > 0, 'height should be greater than 0'
        self.__width = width  # in millimeter
        self.__length = length  # in millimeter
        self.__height = height  # in millimeter
        self.detectorSeries = []

    def set_dimension(self, width=0,length=0,height=0):
        self.__width = width # in millimeter
        self.__length = length # in millimeter
        self.__height = height # in millimeter

    def set_prop(self,cargo_prop):
        self.__width = cargo_prop['width']
        self.__length = cargo_prop['length']
        self.__height = cargo_prop['height']
    
    def get_dimension(self):
        
        return tuple([self.__width,self.__length,self.__height])

    def isinbay(self,pos):  #判断提供的pos是否在货舱内
    
    #pos: list-like data
        
        isinwidth = pos[1] < self.__width
        isinlength = pos[0] < self.__length

        return isinlength & isinwidth

