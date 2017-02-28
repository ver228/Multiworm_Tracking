# -*- coding: utf-8 -*-
"""
Created on Tue 17 May 2016

@author: ljschumacher
"""
import cv2
import os


class readTifStack:
    """ Reads a tif image stack"""

    def __init__(self, fileName):
        self.fid = fileName
        if not os.path.exists(self.fid):
            print('Error: Directory (%s) does not exist.' % self.fid)
            exit()
        image = cv2.imread(self.fid)
        self.height = image.shape[0]
        self.width = image.shape[1]

    def read(self):
        image = cv2.imread(self.fid, 0)
        return (1, image)

    def release(self):
        pass
