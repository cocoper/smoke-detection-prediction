# -*- coding:utf-8 -*-
from Detector import Detector


class Environment(object):
    def __init__(self, cargobay_obj, detector_series, detector_qty, time_criteria=60):
        self.detectors = detector_series  # 创建探测器组
        # self.detectors =[]
        self.det_qty = detector_qty
        self.cargobay = cargobay_obj
        self.CHA_SD = []  # A通道组
        self.CHB_SD = []  # B通道组
        self.SD_dim = self.detectors[0].get_dimension()
        self.smoke_src_pos = (0, 0, 0)
        self.crit = time_criteria

        self.__set_detector_id()  # 顺序设置探测器Id
        self.__set_channel_id()  # 设置AB通道的探测器

    def add_detector(self, detector):
        if detector.__class__.__name__ == "Detector":
            self.detectors.append(detector)
        else:
            print("This is not a Detector instance")

    def set_source(self, x_pos, y_pos):
        if self.cargobay.isinbay((x_pos, y_pos)):
            self.smoke_src_pos = (x_pos, y_pos, 0)
        else:
            print("wrong source location: out of boundary")

    def __set_detector_id(self):  # 顺序设置探测器Id
        SD_id = 1  # 烟雾探测器从1开始编号
        for sd in self.detectors:
            sd.set_SD_id(SD_id)
            SD_id += 1

    def __set_channel_id(self):
        for sd in self.detectors:
            if sd.SD_id % 2 == 1:
                sd.set_channel_id(0)
                self.CHA_SD.append(sd)
            else:
                sd.set_channel_id(1)
                self.CHB_SD.append(sd)

    def arrange(self, arrange_method='center', fwd_space=0, aft_space=0):
        assert self.det_qty > 0, 'the qty of detector should be more than 1'
        if arrange_method == 'center':
            X_group, Y_group = self.__center_arrange(
                self.det_qty, fwd_space, aft_space, displace=100)  # 计算各组的坐标
            i = 0
            for sd in self.CHA_SD:
                sd.set_pos(X_group[i], Y_group[0], self.cargobay.height)
                i += 1
            i = 0
            for sd in self.CHB_SD:
                sd.set_pos(X_group[i], Y_group[1], self.cargobay.height)
                i += 1

    def __center_arrange(self, SD_NUM, fwd_space, aft_space, displace=0):
        '''
        SD_NUM: 烟雾探测器数量
        fwd_space:第一个探测器与前壁板的距离
        aft_space:最后一个探测器与后壁版距离
        displace:烟雾探测器与中线的偏移
        '''
        assert SD_NUM % 2 == 0, 'The qty of detector should be even'
        group_NUM = int(SD_NUM/2)
        X_group = list(range(group_NUM))
        Y_group = list(range(2))

        # X_group.append(fwd_space + self.SD_dim[0]/2)
        X_group[0] = fwd_space + self.SD_dim[0]/2
        gap = (self.cargobay.length - (fwd_space+aft_space)
                    - self.SD_dim[0]*group_NUM)/(group_NUM-1)
        # x1 = x0 + gap + self.SD_dim[0]
        tmp = X_group[0]
        for i in range(1, group_NUM-1):

            X_group[i] = tmp + gap + self.SD_dim[0]/2
            tmp = X_group[i]
        X_group[-1] = (self.cargobay.length - aft_space - self.SD_dim[0]/2)

        Y_group[0] = self.cargobay.width/2 + displace + self.SD_dim[1]/2
        Y_group[1] = self.cargobay.width/2 - displace - self.SD_dim[1]/2

        return X_group, Y_group

    def run(self, mode='singal'):
        if mode == 'singal':
            for sd in self.detectors:
                sd.alarm(self.smoke_src_pos)
            self.output()
        if mode == 'all':
            g_src_pos = self.movesrc(300, 300, self.smoke_src_pos)
            while True:
                try:
                    x_src_pos, y_src_pos = next(g_src_pos)
                    self.set_source(x_src_pos, y_src_pos)
                    for sd in self.detectors:
                        sd.alarm(self.smoke_src_pos)
                    self.output()
                except StopIteration as e:
                    print(e.value)

    def det_logic(self, signal_CHA, signal_CHB, mode='AND'):
        assert len(signal_CHA) == len(
            signal_CHB), 'A and B channel signal should be same length'
        if mode == 'AND':
            return (True in self.alarm2binary(self.crit, signal_CHA))\
                & (True in self.alarm2binary(self.crit, signal_CHB))
        if mode == 'OR':
            return (True in self.alarm2binary(self.crit, signal_CHA))\
                | (True in self.alarm2binary(self.crit, signal_CHB))

    def movesrc(self, step_x, step_y, initial_pos=(0, 0, 0)):
        index = 0
        assert step_x >0, 'Step in length should be greater than zero'
        assert step_y >0, 'Step in width should be greater than zero'
        x_src_pos = initial_pos[0]
        y_src_pos = initial_pos[1]
        while x_src_pos <= self.cargobay.length: #先在width方向上移动，再在length方向上移动
            while y_src_pos <= self.cargobay.width:
                # self.set_source(x_src_pos,y_src_pos)
                yield x_src_pos,y_src_pos #创建一个迭代器来返回每次的值
                if y_src_pos + step_y > self.cargobay.width: #如果超出货舱尺寸范围，则取货舱边缘
                    y_src_pos = self.cargobay.width
                else:
                    y_src_pos += step_y
                index +=1
            if x_src_pos +step_x >self.cargobay.length:# 如果超出货舱尺寸范围，则取货舱边缘
                x_src_pos =self.cargobay.length
            else:
                x_src_pos += step_x
        return 'Source moving finished'

                
    
    def alarm2binary(self, crit,det_series):
        alarm_bin = [True if sd.alarm_time[0]<=crit else False for sd in det_series]
        print(alarm_bin)
        return alarm_bin

        

    def output(self):
        for sd in self.detectors:
            print('The No.{:d} CH{:d} Smoke Detecotor is at {:.2f},{:.2f},{:.2f}, distance is {:.2f} alarm time is {:f}'
                    .format(sd.SD_id,sd.channel_id,sd.x_pos,sd.y_pos,sd.z_pos,sd.dis,sd.alarm_time[0]))
        self.alarm2binary(self.crit,self.CHA_SD)
        self.alarm2binary(self.crit,self.CHB_SD)
        print(self.det_logic(self.CHA_SD,self.CHB_SD))
