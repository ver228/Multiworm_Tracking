#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 30 20:56:17 2016

@author: ajaver
"""
import numpy as np
import tables
import pandas as pd
import os

from scipy.ndimage.filters import median_filter
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d

from MWTracker.analysis.ske_init.filterTrajectModel import filterModelWorms
from MWTracker.helper.misc import TABLE_FILTERS
from MWTracker.analysis.compress.extractMetaData import read_and_save_timestamp

def getSmoothedTraj(trajectories_file,
                    min_track_size=100,
                    displacement_smooth_win=101,
                    threshold_smooth_win=501,
                    roi_size = -1):
    '''
    Organize the data produced in the trajectories analysis to filter the main trajctories data.
    It will sort the table by index, determine a sensible roi_size, interpolate missing points,
    and smooth the data.
    '''

    def _read_plate_worms(trajectories_file):
        # read that frame an select trajectories that were considered valid by
        # join_trajectories
        #fields that must be included in plate_worms
        plate_worms_fields=  ['worm_index_joined',
                    'frame_number',
                    'coord_x',
                    'coord_y',
                    'threshold',
                    'bounding_box_xmax',
                    'bounding_box_xmin',
                    'bounding_box_ymax',
                    'bounding_box_ymin',
                    'area']
                    
        with pd.HDFStore(trajectories_file, 'r') as table_fid:
            df = table_fid['/plate_worms'][plate_worms_fields]
            df = df[df['worm_index_joined'] > 0]
        
    
        with tables.File(trajectories_file, 'r') as fid:
            timestamp_raw = fid.get_node('/timestamp/raw')[:]
            timestamp_time = fid.get_node('/timestamp/time')[:]
    
        #exit if the timestamp does not make sense
        if len(timestamp_raw) < df['frame_number'].max():
            raise Exception(
                'bad %i, %i. \nFile: %s' %
                (len(timestamp_raw),
                 df['frame_number'].max(),
                    trajectories_file))
        return df, timestamp_raw, timestamp_time
    
    def _get_roi_size(df):
        # calculate the ROI size as the maximum bounding box size for a given trajectory
        bb_x = df['bounding_box_xmax'] - df['bounding_box_xmin'] + 1
        bb_y = df['bounding_box_ymax'] - df['bounding_box_ymin'] + 1
        worm_lim = pd.concat([bb_x, bb_y], axis=1).max(axis=1)
        
        df_bb = pd.DataFrame(
            {'worm_index_joined': df['worm_index_joined'], 'roi_range': worm_lim})
        roi_range = df_bb.groupby('worm_index_joined').agg(max) + 10
        roi_range = dict(roi_range['roi_range'])
        
        return roi_range
    
    def _get_total_number_rows(df, min_track_size):
        # caluculate the total number of rows that will be used by the table.
        # we need this number to reserve space in the recarray
        # get the total length of each track, this is more accurate than using
        # count since parts of the track could have got lost for a few frames
        tracks_data = df.groupby('worm_index_joined').aggregate(['max', 'min'])
        track_lenghts = (
            tracks_data['frame_number']['max'] -
            tracks_data['frame_number']['min'] +
            1)
        tot_num_rows = track_lenghts[track_lenghts > min_track_size].sum()
        return tot_num_rows
    
    # a track size less than 2 will break the interp_1 function
    if min_track_size < 2:
        min_track_size = 2

    # the filter window must be odd
    if displacement_smooth_win % 2 == 0:
        displacement_smooth_win += 1

    df, timestamp_raw, timestamp_time = _read_plate_worms(trajectories_file)
    roi_range = _get_roi_size(df)
    tot_num_rows = _get_total_number_rows(df, min_track_size)
    
    
    # initialize output data as a numpy recarray (pytables friendly format)
    trajectories_df = np.recarray(tot_num_rows, dtype=[('frame_number', np.int32),
                                                       ('worm_index_joined', np.int32),
                                                       ('plate_worm_id', np.int32), 
                                                       ('skeleton_id', np.int32),
                                                       ('coord_x', np.float32), 
                                                       ('coord_y', np.float32), 
                                                       ('threshold', np.float32),
                                                       ('has_skeleton', np.uint8), 
                                                       ('roi_size', np.float32), 
                                                       ('area', np.float32),
                                                       ('timestamp_raw', np.float32), 
                                                       ('timestamp_time', np.float32)])

    # store the maximum and minimum frame of each worm
    worms_frame_range = {}

    # smooth trajectories (reduce giggling from the CM to obtain a nicer video)
    # interpolate for possible missing frames in the trajectories
    curr_rows = 0
    for worm_index, worm_data in df.groupby('worm_index_joined'):
        x = worm_data['coord_x'].values
        y = worm_data['coord_y'].values
        t = worm_data['frame_number'].values
        thresh = worm_data['threshold'].values
        area = worm_data['area'].values

        first_frame = np.min(t)
        last_frame = np.max(t)
        worms_frame_range[worm_index] = (first_frame, last_frame)

        tnew = np.arange(first_frame, last_frame + 1, dtype=np.int32)

        if len(tnew) <= min_track_size:
            continue

        # iterpolate missing points in the trajectory and smooth data using the
        # savitzky golay filter
        fx = interp1d(t, x)
        fy = interp1d(t, y)
        xnew = fx(tnew)
        ynew = fy(tnew)

        farea = interp1d(t, area)
        areanew = farea(tnew)

        fthresh = interp1d(t, thresh)
        threshnew = fthresh(tnew)

        if len(tnew) > displacement_smooth_win and displacement_smooth_win > 3:
            xnew = savgol_filter(xnew, displacement_smooth_win, 3)
            ynew = savgol_filter(ynew, displacement_smooth_win, 3)
            areanew = median_filter(areanew, displacement_smooth_win)

        # smooth the threshold (the worm intensity shouldn't change abruptly
        # along the trajectory)
        if len(tnew) > threshold_smooth_win:
            threshnew = median_filter(threshnew, threshold_smooth_win)

        #we use skeleton_id to add the data into the correct position in the trajectories_data
        new_total = curr_rows + xnew.size
        skeleton_id = np.arange(curr_rows, new_total, dtype=np.int32)
        curr_rows = new_total

        # store the indexes in the original plate_worms table
        plate_worm_id = np.empty(xnew.size, dtype=np.int32)
        plate_worm_id.fill(-1)
        plate_worm_id[t - first_frame] = worm_data.index

        trajectories_df['worm_index_joined'][skeleton_id] = worm_index
        trajectories_df['coord_x'][skeleton_id] = xnew
        trajectories_df['coord_y'][skeleton_id] = ynew

        frame_number = np.arange(first_frame, last_frame + 1, dtype=np.int32)
        trajectories_df['frame_number'][skeleton_id] = frame_number
        trajectories_df['timestamp_raw'][skeleton_id] = timestamp_raw[frame_number]
        trajectories_df['timestamp_time'][skeleton_id] = timestamp_time[frame_number]

        trajectories_df['threshold'][skeleton_id] = threshnew
        trajectories_df['plate_worm_id'][skeleton_id] = plate_worm_id
        trajectories_df['skeleton_id'][skeleton_id] = skeleton_id
        trajectories_df['has_skeleton'][skeleton_id] = False
        trajectories_df['roi_size'][skeleton_id] = roi_range[worm_index]

        trajectories_df['area'][skeleton_id] = areanew

    assert curr_rows == tot_num_rows
    trajectories_data = pd.DataFrame(trajectories_df)
    
    if roi_size > 0:
        trajectories_data['roi_size'] = roi_size
    
    return trajectories_data


    
def saveTrajData(trajectories_data, masked_image_file, skeletons_file):
    
    #read some useful variables from the masked_image_file
    with tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")
        if 'pixels2microns_x' in mask_dataset._v_attrs:
            pixels2microns_x = mask_dataset._v_attrs['pixels2microns_x']
            pixels2microns_y = mask_dataset._v_attrs['pixels2microns_y']
        else:
            pixels2microns_x = 1
            pixels2microns_y = 1
        
        if 'is_light_background' in mask_dataset._v_attrs:
            is_light_background = mask_dataset._v_attrs['is_light_background']
        else:
            is_light_background = 1 #default value

        if 'expected_fps' in mask_dataset._v_attrs:
            expected_fps = mask_dataset._v_attrs['expected_fps']
        else:
            expected_fps = 25 #default value

    #save data into the skeletons file
    with tables.File(skeletons_file, "a") as ske_file_id:
        ske_file_id.create_table(
            '/',
            'trajectories_data',
            obj=trajectories_data.to_records(index=False),
            filters=TABLE_FILTERS)
        
        if not '/timestamp' in ske_file_id:
            read_and_save_timestamp(masked_image_file, skeletons_file)
        
        #read and the pixel information
        trajectories_data = ske_file_id.get_node('/trajectories_data')
        trajectories_data._v_attrs['pixels2microns_x'] = pixels2microns_x                            
        trajectories_data._v_attrs['pixels2microns_y'] = pixels2microns_y

        #find if it is a mask from fluorescence and save it in the new group
        trajectories_data._v_attrs['is_light_background'] = is_light_background

        trajectories_data._v_attrs['expected_fps'] = expected_fps


def processTrajectoryData(skeletons_file, masked_image_file, trajectories_file, smoothed_traj_param, filter_model_name = ''):
    '''
    Initialize the skeletons by creating the table `/trajectories_data`. This table is used by the GUI and by all the subsequent functions.
    filter_model_path -  name of the pretrainned keras model to used to filter worms from spurius blobs. 
                         The file must be stored in the `MWTracker/aux` directory. If the variable is empty this step will be ignored.
    '''


    trajectories_data = getSmoothedTraj(trajectories_file, **smoothed_traj_param)
    if filter_model_name:
        trajectories_data = filterModelWorms(masked_image_file, trajectories_data, filter_model_name)
    
    saveTrajData(trajectories_data, masked_image_file, skeletons_file)
        
if __name__ == '__main__':
    import os
    root_dir = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/test_messy/'
        
    #ff = 'N2_N10_F1-3_Set1_Pos7_Ch1_12112016_024337.hdf5'
    #ff = 'unc-9_N10_F1-3_Set1_Pos1_Ch5_17112016_193814.hdf5'
    #ff = 'trp-4_N1_Set3_Pos6_Ch1_19102016_172113.hdf5'
    #ff = 'trp-4_N10_F1-1_Set1_Pos2_Ch4_02112016_201534.hdf5'
    ff = 'N2_N1_Set1_Pos6_Ch1_19102016_131015.hdf5'
    
    
    masked_image_file = os.path.join(root_dir, ff)    
    skeletons_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
    trajectories_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
    
    is_filter_valid_worms = True
    
    processTrajectoryData(skeletons_file, masked_image_file, trajectories_file, 
                          is_filter_valid_worms, smoothed_traj_param = {})
    
