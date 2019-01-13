# -*- coding:utf-8  -*-

import numpy as np
import math


class Detector(object):
    def __init__(self, predictor='None',
                 x_pos=0,
                 y_pos=0,
                 z_pos=0,
                 dimension=(140, 145),                 
                 threshold=None,
                 FalseAlarmRate=0.00001,
                 SD_id=1,
                 name='SD',
                 channel_id=1
                 ):

        self.x_pos = x_pos
        self.y_pos = y_pos
        self.z_pos = z_pos
        self.dimension = dimension #(width,length)
        self.threshold = threshold
        self.SD_id = SD_id
        self.name = name
        self.channel_id = channel_id
        self.pred = predictor
        self.alarm_time = 0
        self.dis = 0
        self.FAR = FalseAlarmRate

    def set_pos(self, x_pos, y_pos, z_pos):
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.z_pos = z_pos

    def set_x(self, x_pos):
        self.x_pos = x_pos

    def set_y(self, y_pos):
        self.y_pos = y_pos

    def set_z(self, z_pos):
        self.z_pos = z_pos

    def get_pos(self):
        return (self.x_pos, self.y_pos, self.z_pos)

    def get_dimension(self):
        return self.dimension

    def set_threshold(self, threshold):
        self.threshold = threshold

    def get_threshold(self):
        return self.threshold

    def set_channel_id(self, channel_id):
        self.channel_id = channel_id  # '1' CHA,'2' CHB

    def set_SD_id(self, SD_id):
        self.SD_id = SD_id

    def alarm(self, src_pos):
        dis = self.__cal_distance(
            pos1=(self.x_pos, self.y_pos, self.z_pos), pos2=src_pos)
        self.dis = dis
        self.alarm_time = self.pred.predict(dis/10)

    def __cal_distance(self, pos1, pos2):

        dis = (pos1[0]-pos2[0])**2+(pos1[1]-pos2[1])**2
        return math.sqrt(dis)


class Groups(object):
    pass
