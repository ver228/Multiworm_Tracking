# -*- coding: utf-8 -*-
import numpy as np
import cv2
from  MWTracker.analysis.compress.selectVideoReader import selectVideoReader

class BackgroundSubtractor():
    def __init__(self, video_file, buff_size = 100, frame_gap = 10, is_light_background=True):
        
        self.video_file = video_file
        self.buff_size = buff_size
        self.frame_gap = frame_gap
        self.is_light_background = is_light_background

        self.bgnd_buff = None
        self.bngd = None
        self.bgnd_ind = None
        self._initialize_buffer()
        
    def _get_buf_ind(self, frame_n):
        return (frame_n//self.frame_gap)

    def _is_update_bgnd(self,frame_n):
        return (frame_n >= 0 and (frame_n % self.frame_gap) == 0)

    def _initialize_buffer(self):
        ret = 1
        frame_n = 0
        vid = selectVideoReader(self.video_file)
        bgnd_buff = np.zeros((self.buff_size, vid.height, vid.width), vid.dtype)

        max_frames = self.buff_size*self.frame_gap
        while frame_n < max_frames:
            ret, image = vid.read()
            if ret==0:
                break
            
            if image.ndim == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            if self._is_update_bgnd(frame_n):
                self.bgnd_ind = self._get_buf_ind(frame_n)
                bgnd_buff[self.bgnd_ind] = image

            #print(frame_n, self.bgnd_ind, self._is_update_bgnd(frame_n), self.frame_gap)
            
            frame_n += 1

            
        vid.release()

        if self.bgnd_ind is None:
            #no valid frames read
            bgnd_buff = None
        elif self.bgnd_ind<(self.bgnd_ind-1):
            #not many frames red
            bgnd_buff = bgnd_buff[:(self.bgnd_ind+1)]
        
        self.last_frame = frame_n - 1 
        self.bgnd_buff = bgnd_buff
        self._calculate_bgnd()

    def _calculate_bgnd(self):
        if self.is_light_background:
            new_bgnd = np.max(self.bgnd_buff, axis=0)
        else:
            new_bgnd = np.min(self.bgnd_buff, axis=0)
        self.bgnd = new_bgnd.astype(np.int32)

    def _update_background(self, image, frame_n):
        self.last_frame = frame_n
        self.buff_ind = self._get_buf_ind(frame_n)
        self.buff_ind += 1
        if self.buff_ind >= self.bgnd_buff.shape[0]:
            self.buff_ind=0
        self.bgnd_buff[self.buff_ind] = image

        self._calculate_bgnd()

    def update_background(self, image, frame_n):
        if frame_n > self.last_frame and self._is_update_bgnd(frame_n):
            self._update_background(image, frame_n)

    def subtract_bgnd(self, image):
        #here i am cliping and returning in the 8 bit format required
        return (np.clip(self.bgnd - image, 1, 255).astype(np.uint8))

    def apply(self, image, last_frame=-1):
        if last_frame > 0:
            #we have to decide if we are dealing with a single image or a buffer or images
            if image.ndim == 2:
                self.update_background(image, last_frame)
            else:
                first_frame = last_frame-image.shape[0]+1
                for ii, frame_n in enumerate(range(first_frame, last_frame+1)):
                    self.update_background(image[ii], frame_n)
        
        return self.subtract_bgnd(image)
            


