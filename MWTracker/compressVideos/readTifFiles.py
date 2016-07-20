# -*- coding: utf-8 -*-
"""
Created on Tue 18 July 2016

@author: ljschumacher
"""
import cv2
import numpy as np
import os
from sys import exit
import glob

class readTifFiles:
    """ Reads a single tif image, to be expanded for reading videos/stacks"""
    def __init__(self, directoryName):
        self.fid = directoryName
        if not os.path.exists(self.fid):
            print('Error: Directory (%s) does not exist.' % self.fid)
            exit()
        # make a list of the files belonging to this tif series
        self.files = glob.glob(os.path.join(self.fid, '*.tif'))
        # extract string list of filenumbers from list of files
        file_num_str = [os.path.split(x)[1].split('_X')[1].split('.tif')[0] for x in self.files]
        file_num_int = [int(x) for x in file_num_str]
        # numerically sort list of file numbers and get sorted indices
        self.dat_order = sorted(range(len(file_num_int)), key=lambda k: file_num_int[k])
        #check that frame numbers are continuous. The ordered index should go 1, 2, 3, ...
        assert all(np.diff(sorted(file_num_int))==1) #  This will throw and error if it is not the case

        # read the first image to determine width and height
        image = cv2.imread(self.files[0],-1)
        self.height = image.shape[0]
        self.width = image.shape[1]
        self.num_frames = len(self.dat_order)
        #initialize pointer for frames
        self.curr_frame = -1

    def read(self):
        self.curr_frame += 1
        if self.curr_frame < self.num_frames:
            filename = self.files[self.dat_order[self.curr_frame]]
            image = cv2.imread(filename,-1)
            return (1, image)
        else:
            return(0, [])
    
    def release(self):
        pass