#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 29 21:22:22 2016

@author: ajaver
"""

import tables
import numpy as np

from tierpsy.helper.timeCounterStr import timeCounterStr
from tierpsy.helper.misc import print_flush
from tierpsy.analysis.traj_create.getBlobTrajectories import generateImages

def getWormROI(img, CMx, CMy, roi_size=128):
    '''
    Extract a square Region Of Interest (ROI)
    img - 2D numpy array containing the data to be extracted
    CMx, CMy - coordinates of the center of the ROI
    roi_size - side size in pixels of the ROI

    -> Used by trajectories2Skeletons
    '''

    if np.isnan(CMx) or np.isnan(CMy):
        return np.zeros(0, dtype=np.uint8), np.array([np.nan] * 2)

    roi_center = int(roi_size) // 2
    roi_range = np.round(np.array([-roi_center, roi_center]))

    # obtain bounding box from the trajectories
    range_x = (CMx + roi_range).astype(np.int)
    range_y = (CMy + roi_range).astype(np.int)

    if range_x[0] < 0:
        range_x[0] = 0
    if range_y[0] < 0:
        range_y[0] = 0
    #%%
    if range_x[1] > img.shape[1]:
        range_x[1] = img.shape[1]
    if range_y[1] > img.shape[0]:
        range_y[1] = img.shape[0]

    worm_img = img[range_y[0]:range_y[1], range_x[0]:range_x[1]]

    roi_corner = np.array([range_x[0], range_y[0]])

    return worm_img, roi_corner

def getAllImgROI(img, frame_data, roi_size=-1):
    #more generic function that tolerates different ROI size
    worms_in_frame = {}
    for irow, row in frame_data.iterrows():
        worm_roi_size = roi_size if roi_size > 0 else row['roi_size']
        
        worms_in_frame[irow] = getWormROI(img, row['coord_x'], row['coord_y'], worm_roi_size)
    return worms_in_frame

    
def pad_if_necessary(worm_roi, roi_corner, roi_size):
    
    #if the dimenssion are correct return
    if worm_roi.shape == (roi_size, roi_size):
        return worm_roi, roi_corner
    
    #corner dimensions are inverted to be the same as in the skeletons
    roi_corner = roi_corner[::-1]
    def get_corner_and_range(curr_dim):
        curr_corner = roi_corner[curr_dim]
        curr_shape = worm_roi.shape[curr_dim]
        #get the shifted corner and start of the roi
        if curr_corner == 0:
            new_corner = curr_shape - roi_size
            new_range = (np.abs(new_corner), roi_size)
        else:
            new_corner = curr_corner
            new_range = (0, curr_shape)
            
        return new_corner, new_range
        
        
    new_corner, new_ranges = zip(*[get_corner_and_range(x) for x in range(2)])
    #corner dimensions are inverted to be the same as in the skeletons
    new_corner = new_corner[::-1]
                
    new_worm_roi = np.zeros((roi_size, roi_size), dtype = worm_roi.dtype)
    new_worm_roi[new_ranges[0][0]:new_ranges[0][1], 
                 new_ranges[1][0]:new_ranges[1][1]] = worm_roi
    return new_worm_roi, new_corner

def getROIFixSize(worms_in_frame, roi_size):
    tot_worms = len(worms_in_frame)
    worm_imgs = np.zeros((tot_worms, roi_size, roi_size))
    roi_corners = np.zeros((tot_worms,2), np.int)
    indexes = np.array(sorted(worms_in_frame.keys()))
    
    for ii, irow in enumerate(indexes):
        worm_img, roi_corner = worms_in_frame[irow]
        worm_img, roi_corner = pad_if_necessary(worm_img, roi_corner, roi_size)
        
        worm_imgs[ii] = worm_img
        roi_corners[ii, :] = roi_corner
    return indexes, worm_imgs, roi_corners 

def generateMoviesROI(masked_file, 
                    trajectories_data,
                    roi_size = -1, 
                    progress_prefix = '',
                    bgnd_param={},
                    progress_refresh_rate_s=20):

    if len(trajectories_data) == 0:
        print_flush(progress_prefix + ' No valid data. Exiting.')
        
    else:
        frames = trajectories_data['frame_number'].unique()
        img_generator = generateImages(masked_file, frames=frames, bgnd_param=bgnd_param)
        
        traj_group_by_frame = trajectories_data.groupby('frame_number')
        progress_time = timeCounterStr(progress_prefix)
        with tables.File(masked_file, 'r') as fid:
            try:
                expected_fps = fid.get_node('/', 'mask')._v_attrs['expected_fps']
            except:
                expected_fps = 25
            progress_refresh_rate = expected_fps*progress_refresh_rate_s


        for ii, (current_frame, img) in enumerate(img_generator):
            frame_data = traj_group_by_frame.get_group(current_frame)
            
            #dictionary where keys are the table row and the values the worms ROIs
            yield getAllImgROI(img, frame_data, roi_size)
            
            if current_frame % progress_refresh_rate == 0:
                print_flush(progress_time.getStr(current_frame))
            
        print_flush(progress_time.getStr(current_frame))

def getROIfromInd(masked_file, trajectories_data, frame_number, worm_index):
    good = (trajectories_data['frame_number']==frame_number) & (trajectories_data['worm_index_joined']==worm_index)
    row = trajectories_data[good]
    assert len(row) == 1
    row = row.iloc[0]
    
    with tables.File(masked_file, 'r') as fid:
        img_data = fid.get_node('/mask')
        img = img_data[frame_number]

    worm_roi, roi_corner = getWormROI(img, row['coord_x'], row['coord_y'], row['roi_size'])

    row, worm_roi, roi_corner 
    return row, worm_roi, roi_corner 


