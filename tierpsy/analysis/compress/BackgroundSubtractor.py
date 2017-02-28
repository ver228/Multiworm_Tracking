# -*- coding: utf-8 -*-
import numpy as np
import cv2
import tables
from  tierpsy.analysis.compress.selectVideoReader import selectVideoReader


class ReadFullImage():
    def __init__(self, video_file):
        self.video_file = video_file
        self.current_index = 0
        self.next_frame = 0
        self.full_interval = None
        self.full_img = None

        self._update(0)
        

    def _update(self, frame_n):
        if frame_n >= self.next_frame:
            with tables.File(self.video_file, 'r') as fid:            
                self.full_img = fid.get_node('/full_data')[self.current_index]
                if self.full_interval is None:
                    self.full_interval = int(fid.get_node('/full_data')._v_attrs['save_interval'])
            
            self.current_index += 1
            self.next_frame = self.full_interval*(self.current_index + 1)

    def  __getitem__(self, frame_n):
        self._update(frame_n)
        return self.full_img


class BackgroundSubtractor():
    def __init__(self, video_file, buff_size = 100, frame_gap = 10, is_light_background=True):
        
        self.video_file = video_file
        self.buff_size = buff_size
        self.frame_gap = frame_gap
        self.is_light_background = is_light_background

        self.bgnd_buff = None
        self.bngd = None
        self.bgnd_ind = None
        self.full_img = None
        self.full_img_reader = None
        
        self._init_buffer()
        
    def _get_buf_ind(self, frame_n):
        return (frame_n//self.frame_gap)

    def _is_update_bgnd(self,frame_n):
        return (frame_n >= 0 and (frame_n % self.frame_gap) == 0)

    def _init_buffer_video(self):
        ret = 1
        frame_n = 0


        vid = selectVideoReader(self.video_file)
        self.bgnd_buff = np.zeros((self.buff_size, vid.height, vid.width), vid.dtype)

        max_frames = self.buff_size*self.frame_gap
        while frame_n < max_frames:
            ret, image = vid.read()
            if ret==0:
                break
            
            if image.ndim == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            if self._is_update_bgnd(frame_n):
                self.bgnd_ind = self._get_buf_ind(frame_n)
                self.bgnd_buff[self.bgnd_ind] = image

            #print(frame_n, self.bgnd_ind, self._is_update_bgnd(frame_n), self.frame_gap)
            
            frame_n += 1
        vid.release()

        self.last_frame = frame_n - 1

        if self.bgnd_ind is None:
            #no valid frames read
            self.bgnd_buff = None
        elif self.bgnd_ind<(self.bgnd_ind-1):
            #not many frames red
            self.bgnd_buff = self.bgnd_buff[:(self.bgnd_ind+1)]

    def _init_buffer(self):
        
        self.reduce_func = np.max if self.is_light_background else np.min
        
        self.is_hdf5 = self.video_file.endswith('hdf5')
        
        if self.is_hdf5:

            with tables.File(self.video_file, 'r') as fid:
                masks = fid.get_node('/mask')
                
                n_frames = self.buff_size*self.frame_gap
                self.bgnd_buff = masks[:n_frames:self.frame_gap]
                self.bgnd_ind = self.bgnd_buff.size 
                self.last_frame = self.bgnd_ind*self.frame_gap

                if '/full_data' in fid:
                    self.full_img_reader = ReadFullImage(self.video_file)
                    self.full_img = self.full_img_reader[0]
        else:
            self._init_buffer_video()

        self._calculate_bgnd()

    def _calculate_bgnd(self):
        new_bgnd = self.reduce_func(self.bgnd_buff, axis=0)
        
        if self.full_img is not None:
            dd = (new_bgnd, self.full_img)
            new_bgnd = self.reduce_func(dd, axis=0)

        self.bgnd = new_bgnd.astype(np.int32)

    def _update_background(self, image, frame_n):
        self.last_frame = frame_n
        self.buff_ind = self._get_buf_ind(frame_n)
        self.buff_ind += 1
        if self.buff_ind >= self.bgnd_buff.shape[0]:
            self.buff_ind=0
        self.bgnd_buff[self.buff_ind] = image

        if self.full_img_reader is not None:
            self.full_img = self.full_img_reader[frame_n]

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
            


