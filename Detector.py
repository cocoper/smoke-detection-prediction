class detector(object):
    def __init__(self, detctor_position=(0, 0, 0), thershold=None, SD_id = 1):
        self.position = detctor_position
        self.thershold = thershold
        self.ID = SD_id 

    def set_position(self,pos):
        self.position = pos

    def set_thershold(self, thershold):
        self.thershold = thershold

    def alarm(self,source_postition):
        pass
        

