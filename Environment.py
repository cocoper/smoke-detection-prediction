# -*- coding:utf-8 -*-
from Detector import Detector
import csv
import pandas as pd


class Environment(object):
    def __init__(self, cargobay_obj, detector_series, detector_qty, arrange, time_criteria,move_interval):
        self.detectors = detector_series  # 创建探测器组
        # self.detectors =[]
        self.det_qty = detector_qty
        self.cargobay = cargobay_obj
        self.CHA_SD = []  # A通道组
        self.CHB_SD = []  # B通道组
        self.SD_dim = self.detectors[0].get_dimension()
        self.smoke_src_pos = (0, 0, 0)
        self.move_interval = move_interval
        self.crit = time_criteria
        self.sys_arrange = arrange
        self.log = {}  # 每次试验的记录
        dim = self.cargobay.get_dimension()
        self.bay_dim = {'width': dim[0],
                        'length': dim[1],
                        'height': dim[2]
                        }
        self.test = {'No.': 0,
                     'Smoke Location': (0, 0, 0),
                     'Detector Location': (0, 0, 0),
                     'Alarm': False,
                     'Resp time': 0}
        # 初始化每次试验的log字典
        self.log['No.'] = 0
        self.log['Src Loc.'] = 0
        for sd in self.detectors:
            self.log[sd.name] = 0
        self.log['Alarm'] = 0

        self.__set_detector_id()  # 顺序设置探测器Id
        self.__set_channel_id()  # 设置AB通道的探测器

        self.arrange(arrange_method=self.sys_arrange['method'],
                     fwd_gap=self.sys_arrange['fwd_gap'],
                     aft_gap=self.sys_arrange['aft_gap'],
                     displace=self.sys_arrange['displace'])

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

    def arrange(self, arrange_method='center', fwd_gap=0, aft_gap=0, displace=100):
        assert self.det_qty > 0, 'the qty of detector should be more than 1'
        if arrange_method == 'center':
            x_group, y_group = self.__center_arrange(
                self.det_qty, fwd_gap, aft_gap, displace=displace)  # 计算各组的坐标
            i = 0
            for sd in self.CHA_SD:
                sd.set_pos(x_group[i], y_group[0], self.bay_dim['height'])
                i += 1
            i = 0
            for sd in self.CHB_SD:
                sd.set_pos(x_group[i], y_group[1], self.bay_dim['height'])
                i += 1
        if arrange_method == 'side':
            x_group, y_group = self.__side_arrange(
                self.det_qty, fwd_gap, aft_gap, displace=displace)  # 计算各组的坐标
            y = y_group[0]
            for sd in self.detectors:
                for x in x_group:
                    sd.set_pos(x, y, self.bay_dim['height'])
                    if y == y_group[0]:
                        y = y_group[1]
                    else:
                        y = y_group[0]

    def __center_arrange(self, SD_NUM, fwd_gap, aft_gap, displace=0):  # 中心排布方案
        '''
        SD_NUM: 烟雾探测器数量
        fwd_gap:第一个探测器与前壁板的距离
        aft_gap:最后一个探测器与后壁版距离
        displace:烟雾探测器与中线的偏移

        '''
        assert SD_NUM % 2 == 0, 'The qty of detector should be even'
        group_NUM = int(SD_NUM/2)
        x_group = list(range(group_NUM))  # 沿航向的探测器坐标组
        y_group = list(range(2))  # 沿展向的探测器坐标组

        # x_group.append(fwd_gap + self.SD_dim[0]/2)
        x_group[0] = fwd_gap + self.SD_dim[0]/2
        gap = (self.bay_dim['length'] - (fwd_gap+aft_gap)
               - self.SD_dim[0]*group_NUM)/(group_NUM-1)
        # x1 = x0 + gap + self.SD_dim[0]
        first_sd_x = x_group[0]
        for i in range(1, group_NUM-1):

            x_group[i] = first_sd_x + gap + self.SD_dim[0]/2
            first_sd_x = x_group[i]
        x_group[-1] = (self.bay_dim['length'] - aft_gap - self.SD_dim[0]/2)

        y_group[0] = self.bay_dim['width']/2 + displace + self.SD_dim[1]/2
        y_group[1] = self.bay_dim['width']/2 - displace - self.SD_dim[1]/2

        return x_group, y_group

    def __side_arrange(self, SD_NUM, fwd_gap, aft_gap, displace=50):  # 间隔排布方案
        '''
        SD_NUM: 烟雾探测器数量
        fwd_gap:第一个探测器与前壁板的距离
        aft_gap:最后一个探测器与后壁版距离
        displace:烟雾探测器与中线的偏移
        '''
        assert SD_NUM % 2 == 0, 'The qty of detector should be even'
        # group_NUM = int(SD_NUM/2)
        x_group = list(range(SD_NUM))
        y_group = list(range(2))

        # x_group.append(fwd_gap + self.SD_dim[0]/2)
        x_group[0] = fwd_gap + self.SD_dim[0]/2
        gap = (self.bay_dim['length'] - (fwd_gap+aft_gap)
               - self.SD_dim[0]*SD_NUM)/(SD_NUM-1)
        # x1 = x0 + gap + self.SD_dim[0]
        first_sd_x = x_group[0]
        for i in range(1, SD_NUM-1):

            x_group[i] = first_sd_x + gap + self.SD_dim[0]/2
            first_sd_x = x_group[i]
        x_group[-1] = (self.bay_dim['length'] - aft_gap - self.SD_dim[0]/2)

        y_group[0] = self.bay_dim['width']/2 + displace + self.SD_dim[1]/2
        y_group[1] = self.bay_dim['width']/2 - displace - self.SD_dim[1]/2

        return x_group, y_group

    def run(self, mode='singal'):
        if mode == 'singal':
            for sd in self.detectors:
                sd.alarm(self.smoke_src_pos)
            return self.det_logic(self.CHA_SD, self.CHB_SD, mode='AND')

            # self.output(mode)

        if mode == 'all':
            failed_test = []  # 记录失败试验的编号
            rec_src_x = []  # 记录烟雾x位置
            rec_src_y = []  # 记录烟雾y位置
            test_num = 0  # 试验编号
            g_src_pos = self.MoveSrc(self.move_interval, self.smoke_src_pos)
            logfile = open('test_result.csv', 'w',
                           newline='', encoding='utf-8')
            logger = csv.DictWriter(logfile, self.log.keys(), delimiter=',')
            logger.writeheader()
            while True:
                try:
                    test_num += 1
                    self.log['No.'] = test_num
                    src_x, src_y = next(g_src_pos)
                    rec_src_x.append(src_x)
                    rec_src_y.append(src_y)
                    self.set_source(src_x, src_y)
                    self.log['Src Loc.'] = (
                        src_x, src_y, self.smoke_src_pos[2])

                    for sd in self.detectors:
                        sd.alarm(self.smoke_src_pos)  # 得到每个烟雾探测器的告警时间并存入对象内
                        self.log[sd.name] = sd.alarm_time[0]
                    self.output()
                    alarm_res = self.det_logic(
                        self.CHA_SD, self.CHB_SD, mode='AND')
                    self.log['Alarm'] = alarm_res
                    if not alarm_res:
                        failed_test.append(test_num)
                    print(self.log)
                    # self.write_test_log(test_res,logfile)
                    logger.writerow(self.log)

                except StopIteration as e:
                    print(e.value)
                    break
            logfile.close()
            print(failed_test)
            # self.res = pd.DataFrame(
            #     data={'alarm': results,
            #           'smoke_x': rec_src_x,
            #           'smoke_y': rec_src_y
            #           }
            # )
            # print(self.res)
            # print('{:d} failed tests'.format(results.count(False)))

    def det_logic(self, signal_CHA, signal_CHB, mode='AND'):
        assert len(signal_CHA) == len(
            signal_CHB), 'A and B channel signal should be same length'
        if mode == 'AND':
            return (True in self.alarm2binary(self.crit, signal_CHA))\
                & (True in self.alarm2binary(self.crit, signal_CHB))
        if mode == 'OR':
            return (True in self.alarm2binary(self.crit, signal_CHA))\
                | (True in self.alarm2binary(self.crit, signal_CHB))

    def MoveSrc(self, move_interval, initial_pos=(0, 0, 0)):
        index = 0
        step_x = move_interval[0]
        step_y = move_interval[1]
        assert step_x > 0, 'Step in length should be greater than zero'
        assert step_y > 0, 'Step in width should be greater than zero'
        src_x = initial_pos[0]
        # 先在width方向上移动，再在length方向上移动
        while src_x < self.bay_dim['length']:
            src_y = initial_pos[1]
            while src_y < self.bay_dim['width']:
                # self.set_source(src_x,src_y)
                yield src_x, src_y  # 创建一个迭代器来返回每次的值
                # 如果超出货舱尺寸范围，则取货舱边缘
                if src_y + step_y > self.bay_dim['width']:
                    src_y = self.bay_dim['width']
                else:
                    src_y += step_y
                index += 1
            # 如果超出货舱尺寸范围，则取货舱边缘
            if src_x + step_x > self.bay_dim['length']:
                src_x = self.bay_dim['length']
            else:
                src_x += step_x
        return 'Smoke Source moving finished'

    def alarm2binary(self, crit, det_series):  # 返回整个烟雾探测器的告警与否序列
        alarm_bin = [True if sd.alarm_time[0] <=
                     crit else False for sd in det_series]
        # print(alarm_bin)
        return alarm_bin

    def output(self):
        for sd in self.detectors:
            print('The No.{:d} CH{:d} Smoke Detecotor is at {:.2f},{:.2f},{:.2f}, distance is {:.2f} alarm time is {:f}'
                  .format(sd.SD_id, sd.channel_id, sd.x_pos, sd.y_pos, sd.z_pos, sd.dis, sd.alarm_time[0]))
        # self.alarm2binary(self.crit,self.CHA_SD)
        # self.alarm2binary(self.crit,self.CHB_SD)
        # print(self.det_logic(self.CHA_SD,self.CHB_SD))

    # def write_test_log(self, test_res, logfile, **kwargs):
    #     writer = csv.DictWriter(logfile, list(
    #         test_res.keys()), delimiter=',')
    #     writer.writeheader()
    #     writer.writerow(test_res)
