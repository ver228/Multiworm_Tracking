import numpy as np
import os
from sys import exit
import glob

class readDatFile:
    """ Reads a stack of dat images """
    def __init__(self, dirName):
        self.fid = dirName
        if not os.path.exists(self.fid):
            print('Error: Directory (%s) does not exist.' % self.fid)
            exit()

        self.files = glob.glob(os.path.join(self.fid, '*.dat'))
        
        #TODO: figure out how to really do this. This file order works half of the time
        #get the order of the frames from the file name. 
        file_num_str = [os.path.split(x)[1].partition('spool')[0] for x in self.files]
        #first we assume that the filename contains the frame number 00001, 00002, 00003
        self.dat_order = sorted([int(x) for x in file_num_str])
        #check in the indexes in the file order are really continuous. The ordered index should go 1, 2, 3, 4
        is_continous =  all(np.diff(self.dat_order)==1)
        if not is_continous:
            #the file name can contain the image number as an inverted string, e.g. 6100000 -> 0000016
            self.dat_order = sorted([int(x[::-1]) for x in file_num_str])

            #check again in the indexes in the file order are really continuous. This will throw and error if it is not the case
            assert all(np.diff(self.dat_order)==1)
        
        #It seems that the last 40 bytes of each file are the header (it contains zeros and the size of the image 2080*2156)
        bin_dat = np.fromfile(self.files[0], np.uint8)
        header = bin_dat[-40:].astype(np.uint16)
        header =  np.left_shift(header[1::2], 8) + header[0::2]
        im_size = header[14:16]
        self.height = im_size[1]
        self.width = im_size[0]
        self.num_frames = len(self.dat_order)
        #initialize pointer for frames
        self.curr_frame = -1
    
    def read(self): 
        self.curr_frame += 1
        if self.curr_frame < self.num_frames:
            fname = self.files[self.dat_order[self.curr_frame]]
            bin_dat = np.fromfile(fname, np.uint8)
            #every 3 bytes will correspond two pixel levels.
            D1 = bin_dat[:-40:3] 
            D2 = bin_dat[1:-40:3] 
            D3 = bin_dat[2:-40:3] 
            
            #the image format is mono 12 packed (see web)
            #the first and third bytes represent the higher bits of the pixel intensity
            #while the second byte is divided into the lower bits.
            D1s = np.left_shift(D1.astype(np.uint16), 4) + np.bitwise_and(D2,15)
            D3s = np.left_shift(D3.astype(np.uint16), 4) + np.right_shift(D2,4)
            
            #the pixels seemed to be organized in this order
            image_decoded = np.zeros((self.height, self.width), np.uint16)
            image_decoded[::-1, -2::-2] = D3s.reshape((self.height, -1))
            image_decoded[::-1, ::-2] = D1s.reshape((self.height, -1))

            return (1, image_decoded)
        else:
            return (0, [], [], [])
    def release(self):
        pass
