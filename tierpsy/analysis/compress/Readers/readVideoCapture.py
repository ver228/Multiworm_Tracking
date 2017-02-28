#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 14 16:56:55 2016

@author: ajaver
"""

import cv2

class readVideoCapture():
    def __init__(self, video_file):
        vid = cv2.VideoCapture(video_file)
        # sometimes video capture seems to give the wrong dimensions read the
        # first image and try again
        # get video frame, stop program when no frame is retrive (end of file)
        ret, image = vid.read()
        vid.release()
            
        if ret:
            self.height = image.shape[0]
            self.width = image.shape[1]
            self.dtype = image.dtype
            self.vid = cv2.VideoCapture(video_file)
            self.video_file = video_file
        else:
            raise OSError(
                'Cannot get an image from %s.\n It is likely that either the file name is wrong, the file is corrupt or OpenCV was not installed with ffmpeg support.' %
                video_file)
        
    def read(self):
        return self.vid.read()
    
    def release(self):
        return self.vid.release()
        