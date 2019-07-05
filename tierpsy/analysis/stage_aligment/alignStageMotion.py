# -*- coding: utf-8 -*-
"""
Created on Thu Feb 11 22:01:59 2016

@author: ajaver
"""

import numpy as np
import tables
import pandas as pd
import warnings

from tierpsy.helper.params import read_fps, read_microns_per_pixel
from tierpsy.helper.misc import print_flush, get_base_name
from tierpsy.analysis.stage_aligment.findStageMovement import getFrameDiffVar, findStageMovement, shift2video_ref


def isGoodStageAligment(skeletons_file):
    with tables.File(skeletons_file, 'r') as fid:
        try:
            good_aligment = fid.get_node('/stage_movement')._v_attrs['has_finished']
        except (KeyError, IndexError, tables.exceptions.NoSuchNodeError):
            good_aligment = 0
        return good_aligment in [1, 2]

def _h_get_stage_inv(skeletons_file, timestamp):
    if timestamp.size == 0:
        return np.zeros((0, 2)), np.zeros(0)

    first_frame = timestamp[0]
    last_frame = timestamp[-1]

    with tables.File(skeletons_file, 'r') as fid:
        stage_vec_ori = fid.get_node('/stage_movement/stage_vec')[:]
        timestamp_ind = fid.get_node('/timestamp/raw')[:].astype(np.int)
        rotation_matrix = fid.get_node('/stage_movement')._v_attrs['rotation_matrix']
        microns_per_pixel_scale = fid.get_node('/stage_movement')._v_attrs['microns_per_pixel_scale']
        #2D to control for the scale vector directions
            
    # let's rotate the stage movement
    dd = np.sign(microns_per_pixel_scale)
    rotation_matrix_inv = np.dot(
        rotation_matrix * [(1, -1), (-1, 1)], [(dd[0], 0), (0, dd[1])])

    # adjust the stage_vec to match the timestamps in the skeletons
    good = (timestamp_ind >= first_frame) & (timestamp_ind <= last_frame)

    ind_ff = timestamp_ind[good] - first_frame
    if timestamp_ind.shape[0] > stage_vec_ori.shape[0]:
        #there are extra elements in the timestamp_ind, let's pad it with the same value in the stage vector
        extra_n = timestamp_ind.shape[0] - stage_vec_ori.shape[0]
        stage_vec_ori = np.pad(stage_vec_ori, ((0, extra_n),(0,0)), 'edge')

    stage_vec_ori = stage_vec_ori[good]

    stage_vec = np.full((timestamp.size, 2), np.nan)
    stage_vec[ind_ff, :] = stage_vec_ori
    # the negative symbole is to add the stage vector directly, instead of
    # substracting it.
    stage_vec_inv = -np.dot(rotation_matrix_inv, stage_vec.T).T


    return stage_vec_inv, ind_ff

def _h_add_stage_position_pix(mask_file, skeletons_file):
    # if the stage was aligned correctly add the information into the mask file    
    microns_per_pixel = read_microns_per_pixel(mask_file)
    with tables.File(mask_file, 'r+') as fid:
        timestamp_c = fid.get_node('/timestamp/raw')[:]
        timestamp = np.arange(np.min(timestamp_c), np.max(timestamp_c)+1)
        stage_vec_inv, ind_ff = _h_get_stage_inv(skeletons_file, timestamp)
        stage_vec_pix = stage_vec_inv[ind_ff]/microns_per_pixel
        if '/stage_position_pix' in fid: 
            fid.remove_node('/', 'stage_position_pix')
        fid.create_array('/', 'stage_position_pix', obj=stage_vec_pix)

def alignStageMotion(masked_file, skeletons_file):

    base_name = get_base_name(masked_file)
    print_flush(base_name + ' Aligning Stage Motion...')
    #%%
    fps = read_fps(skeletons_file)
    
    #%%
    # Open the information file and read the tracking delay time.
    # (help from segworm findStageMovement)
    # 2. The info file contains the tracking delay. This delay represents the
    # minimum time between stage movements and, conversely, the maximum time it
    # takes for a stage movement to complete. If the delay is too small, the
    # stage movements become chaotic. We load the value for the delay.
    with tables.File(masked_file, 'r') as fid:
        xml_info = fid.get_node('/xml_info').read().decode()
        g_mask = fid.get_node('/mask')

        tot_frames = g_mask.shape[0]
        # Read the scale conversions, we would need this when we want to convert the pixels into microns
        pixelPerMicronX = 1/g_mask._v_attrs['pixels2microns_x']
        pixelPerMicronY = 1/g_mask._v_attrs['pixels2microns_y']

    with pd.HDFStore(masked_file, 'r') as fid:
        stage_log = fid['/stage_log']
    

    
    #%this is not the cleaneast but matlab does not have a xml parser from
    #%text string
    delay_str = xml_info.partition('<delay>')[-1].partition('</delay>')[0]
    delay_time = float(delay_str) / 1000;
    delay_frames = np.ceil(delay_time * fps);
    
    normScale = np.sqrt((pixelPerMicronX ** 2 + pixelPerMicronX ** 2) / 2);
    pixelPerMicronScale =  normScale * np.array((np.sign(pixelPerMicronX), np.sign(pixelPerMicronY)));
    
    #% Compute the rotation matrix.
    #%rotation = 1;
    angle = np.arctan(pixelPerMicronY / pixelPerMicronX);
    if angle > 0:
        angle = np.pi / 4 - angle;
    else:
        angle = np.pi / 4 + angle;
    
    cosAngle = np.cos(angle);
    sinAngle = np.sin(angle);
    rotation_matrix = np.array(((cosAngle, -sinAngle), (sinAngle, cosAngle)));
    #%%
    #% Ev's code uses the full vectors without dropping frames
    #% 1. video2Diff differentiates a video frame by frame and outputs the
    #% differential variance. We load these frame differences.
    frame_diffs_d = getFrameDiffVar(masked_file);

    print_flush(base_name + ' Aligning Stage Motion...')
    #%% Read the media times and locations from the log file.
    #% (help from segworm findStageMovement)
    #% 3. The log file contains the initial stage location at media time 0 as
    #% well as the subsequent media times and locations per stage movement. Our
    #% algorithm attempts to match the frame differences in the video (see step
    #% 1) to the media times in this log file. Therefore, we load these media
    #% times and stage locations.
    #%from the .log.csv file
    mediaTimes = stage_log['stage_time'].values;
    locations = stage_log[['stage_x', 'stage_y']].values;
    

    #ini stage movement fields
    with tables.File(skeletons_file, 'r+') as fid:
        # delete data from previous analysis if any
        if '/stage_movement' in fid:
            fid.remove_node('/stage_movement', recursive = True)
        g_stage_movement = fid.create_group('/', 'stage_movement')
        g_stage_movement._v_attrs['has_finished'] = 0
        
        #read and prepare timestamp
        try:
            video_timestamp_ind = fid.get_node('/timestamp/raw')[:]
            if np.any(np.isnan(video_timestamp_ind)): 
                raise ValueError()
            else:
                video_timestamp_ind = video_timestamp_ind.astype(np.int)
        except(tables.exceptions.NoSuchNodeError, ValueError):
            warnings.warn('It is corrupt or do not exist. I will assume no dropped frames and deduce it from the number of frames.')
            video_timestamp_ind = np.arange(tot_frames, dtype=np.int)
    
    #%% The shift makes everything a bit more complicated. I have to remove the first frame, before resizing the array considering the dropping frames.
    if video_timestamp_ind.size > frame_diffs_d.size + 1:
        #%i can tolerate one frame (two with respect to the frame_diff)
        #%extra at the end of the timestamp
        video_timestamp_ind = video_timestamp_ind[:frame_diffs_d.size + 1];
    
    dd = video_timestamp_ind - np.min(video_timestamp_ind) - 1; #shift data
    dd = dd[dd>=0];
    #%%
    if frame_diffs_d.size != dd.size:
        raise ValueError('Number of timestamps do not match the number of frames in the movie.')
        
    frame_diffs = np.full(int(np.max(video_timestamp_ind)), np.nan);
    frame_diffs[dd] = frame_diffs_d;


    #%% save stage data into the skeletons.hdf5
    with tables.File(skeletons_file, 'r+') as fid:
        # I am saving this data before for debugging purposes
        g_stage_movement = fid.get_node('/stage_movement')
        fid.create_carray(g_stage_movement, 'frame_diffs', obj=frame_diffs_d)
        g_stage_movement._v_attrs['fps'] = fps
        g_stage_movement._v_attrs['delay_frames'] = delay_frames
        g_stage_movement._v_attrs['microns_per_pixel_scale'] = pixelPerMicronScale
        g_stage_movement._v_attrs['rotation_matrix'] = rotation_matrix
    

    #%% try to run the aligment and return empty data if it fails 
    is_stage_move, movesI, stage_locations = \
    findStageMovement(frame_diffs, mediaTimes, locations, delay_frames, fps);
    stage_vec_d, is_stage_move_d = shift2video_ref(is_stage_move, movesI, stage_locations, video_timestamp_ind)
    
    #%% save stage data into the skeletons.hdf5
    with tables.File(skeletons_file, 'r+') as fid:
        g_stage_movement = fid.get_node('/stage_movement')
        fid.create_carray(g_stage_movement, 'stage_vec', obj=stage_vec_d)
        fid.create_carray(g_stage_movement, 'is_stage_move', obj=is_stage_move_d)
        g_stage_movement._v_attrs['has_finished'] = 1
    

    _h_add_stage_position_pix(masked_file, skeletons_file)
    print_flush(base_name + ' Aligning Stage Motion. Finished.')
    

if __name__ == '__main__':
    #masked_file = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/miss_aligments/trp-2 (ok298) off food_2010_04_30__13_03_40___1___8.hdf5'
    #masked_file = '/Users/ajaver/Tmp/MaskedVideos/worm 1/L4_19C_1_R_2015_06_24__16_40_14__.hdf5'
    #masked_file = '/Users/ajaver/Tmp/MaskedVideos/worm 2/L4_H_18_2016_10_30__15_56_12__.hdf5'
    masked_file = '/Volumes/behavgenom_archive$/single_worm/unfinished/WT/PS312/food_mec-10,mec-4-L3/XX/30m_wait/clockwise/197 PS312 3 on mec-10,mec-4-L3 L_2011_07_06__15_33___3___1.hdf5'
    skeletons_file = masked_file.replace(
        'MaskedVideos',
        'Results').replace(
        '.hdf5',
        '_skeletons.hdf5')
    #alignStageMotion(masked_file, skeletons_file)
    