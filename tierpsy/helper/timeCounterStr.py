# -*- coding: utf-8 -*-
"""
Created on Tue Jun  9 11:51:28 2015

@author: ajaver
"""

import time
import datetime
import numpy as np

def tictoc():
    tic = time.time()

    def toc():
        print('Elapse time %f' % (time.time() - tic))
    return toc


class timeCounterStr:

    def __init__(self, task_str):
        self.initial_time = time.time()
        self.last_frame = 0
        self.task_str = task_str
        self.fps_time = time.time()

    def getStr(self, frame_number):
        # calculate the progress and put it in a string
        time_str = str(
            datetime.timedelta(
                seconds=round(
                    time.time() -
                    self.initial_time)))
        
        try:
            fps = (frame_number - self.last_frame + 1) / \
                (time.time() - self.fps_time)
        except ZeroDivisionError:
            fps = np.nan
            
        progress_str = '%s Total time = %s, fps = %2.1f; Frame %i '\
            % (self.task_str, time_str, fps, frame_number)
        self.fps_time = time.time()
        self.last_frame = frame_number
        return progress_str

    def getTimeStr(self):
        return str(
            datetime.timedelta(
                seconds=round(
                    time.time() -
                    self.initial_time)))
