# -*- coding: utf-8 -*-
"""
Created on Sun Oct  4 14:33:18 2015

@author: ajaver
"""
import tables
import numpy as np


class readVideoHDF5:

    def __init__(self, fileName, full_img_period=np.inf):
        # to be used when added to the plugin
        self.vid_frame_pos = []
        self.vid_time_pos = []

        try:
            self.fid = tables.File(fileName, 'r')
            self.dataset = self.fid.get_node('/mask')
        except:
            raise OSError

        self.tot_frames = self.dataset.shape[0]

        self.width = self.dataset.shape[2]
        self.height = self.dataset.shape[1]
        self.dtype = self.dataset.dtype

        self.tot_pix = self.height * self.width

        # initialize pointer for frames
        self.curr_frame = -1

        # how often we get a full frame
        self.full_img_period = full_img_period

    def read(self):
        self.curr_frame += 1
        if self.curr_frame % self.full_img_period == 0:
            self.full_img = self.dataset[self.curr_frame, :, :]
            self.value2replace = np.median(self.full_img)

        if self.curr_frame < self.tot_frames:
            image = self.dataset[self.curr_frame, :, :]
            mask_bw = image == 0
            image[mask_bw] = self.value2replace
            return (1, image)
        else:
            return (0, [])

    def __len__(self):
        return self.tot_frames

    def release(self):
        # close the buffer
        self.fid.close()
