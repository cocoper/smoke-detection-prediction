# -*- coding:utf-8  -*-

class Detector(object):
    def __init__(self, regr,
                detctor_pos=(0, 0, 0), 
                threshold = None, 
                SD_id = 1,
                group_id = 1
                ):

        self.pos = detctor_pos
        self.threshold = threshold
        self.ID = SD_id
        self.group_id = group_id
        self.regr = regr

    def set_pos(self,pos):
        self.pos = pos

    def get_pos(self):
        return self.pos

    def set_threshold(self, threshold):
        self.threshold = threshold
        
    def get_threshold(self):
        return self.threshold

    def alarm(self,source_postition):
        pass
        
class Groups(object):
    pass
