# -*- coding: utf-8 -*-
"""
Created on Wed May 18 18:22:12 2016

@author: ajaver
"""
import os

import cv2
import h5py
import numpy as np

from tierpsy.analysis.feat_create.obtainFeatures import read_fps
from tierpsy.helper.misc import print_flush
from tierpsy.helper.timeCounterStr import timeCounterStr


def getSubSampleVidName(masked_image_file):
    #used by AnalysisPoints.py and CheckFinished.py
    return masked_image_file.replace('.hdf5', '_subsample.avi')


def _getCorrectedTimeVec(fid, tot_frames):
    '''time vector used to account for missing frames'''
    if '/timestamp/raw' in fid:
        timestamp_ind = fid['/timestamp/raw'][:]
    else:
        #if there is not valid timestamp field considered that there are not missing frames
        return np.arange(tot_frames)
    
    #remove any nan, I notice that sometimes the last number is a nan
    timestamp_ind = timestamp_ind[~np.isnan(timestamp_ind)]
    if timestamp_ind.size < tot_frames-1: #invalid timestamp
        #if there is not valid frames skip
        return np.arange(tot_frames)


    tot_timestamps = int(timestamp_ind[-1])
    
    #%%
    #make sure to compensate for missing frames, so the video will have similar length.
    tt_vec = np.full(tot_timestamps+1, np.nan)
    current_frame = 0
    for ii in range(tot_timestamps+1):
        tt_vec[ii] = current_frame
        current_timestamp = timestamp_ind[current_frame]
        if current_timestamp <= ii:
            current_frame += 1

    return tt_vec

def createSampleVideo(masked_image_file, sample_video_name ='', time_factor = 8, 
                     size_factor = 5, expected_fps=30, codec='MPEG'):
    #%%
    if not sample_video_name:
        sample_video_name = getSubSampleVidName(masked_image_file)
    
    # initialize timers
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progressTime = timeCounterStr('{} Generating subsampled video.'.format(base_name))
    
    with h5py.File(masked_image_file, 'r') as fid:
        masks = fid['/mask']
        tot_frames, im_h, im_w = masks.shape
        im_h, im_w = im_h//size_factor, im_w//size_factor
        
        fps, is_default_timestamp = getFPS(masked_image_file, expected_fps)

        tt_vec = _getCorrectedTimeVec(fid, tot_frames)
        #%%
        #codec values that work 'H264' #'MPEG' #XVID
        vid_writer = cv2.VideoWriter(sample_video_name, \
                            cv2.VideoWriter_fourcc(*codec), fps/2, (im_w,im_h), isColor=False)
        assert vid_writer.isOpened()
        
        for frame_number in range(0, tot_frames, time_factor*2):
            current_frame = tt_vec[frame_number]
            img = masks[current_frame]
            im_new = cv2.resize(img, (im_w,im_h))
            vid_writer.write(im_new)


            if frame_number % (500*time_factor) == 0:
                # calculate the progress and put it in a string
                print_flush(progressTime.getStr(frame_number))

        vid_writer.release()
        print_flush(progressTime.getStr(frame_number) + ' DONE.')
    
#%%
if __name__ == '__main__':

    #mask_file_name = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/Agar_Test/MaskedVideos/Agar_Screening_101116/N2_N10_F1-3_Set1_Pos3_Ch6_12112016_002739.hdf5'
    #masked_image_file = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/Agar_Test/MaskedVideos/Agar_Screening_101116/unc-9_N3_F1-3_Set1_Pos3_Ch4_12112016_002739.hdf5'
    masked_image_file = r'C:\Users\wormrig\Documents\GitHub\Multiworm_Tracking\Tests\data\test_1\MaskedVideos\Capture_Ch1_18062015_140908.hdf5'
    createSampleVideo(masked_image_file)


    