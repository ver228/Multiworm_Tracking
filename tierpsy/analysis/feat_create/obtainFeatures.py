# -*- coding: utf-8 -*-
"""
Created on Thu Jun  4 11:30:53 2015

@author: ajaver
"""
import copy
import os
import warnings
from functools import partial

import numpy as np
import pandas as pd
import tables

warnings.filterwarnings('ignore', '.*empty slice*',)
warnings.filterwarnings('ignore', ".*Falling back to 'gelss' driver.",)
warnings.filterwarnings('ignore', category=np.VisibleDeprecationWarning)
warnings.simplefilter(action="ignore", category=RuntimeWarning)

# (http://www.pytables.org/usersguide/parameter_files.html)
tables.parameters.MAX_COLUMNS = 1024

from MWTracker.helper.timeCounterStr import timeCounterStr
from MWTracker.helper.misc import print_flush
from MWTracker.analysis.ske_filt.getFilteredSkels import getValidIndexes
from MWTracker.analysis.feat_create.obtainFeaturesHelper import WormStatsClass, WormFromTable
from MWTracker.analysis.contour_orient.correctVentralDorsal import isBadVentralOrient
from MWTracker.helper.misc import WLAB, TABLE_FILTERS

import open_worm_analysis_toolbox as mv

def getFPS(skeletons_file, expected_fps, min_allowed_fps=1):
        # try to infer the fps from the timestamp
    try:
        with tables.File(skeletons_file, 'r') as fid:
            timestamp_time = fid.get_node('/timestamp/time')[:]

            if np.all(np.isnan(timestamp_time)):
                raise ValueError
            fps = 1 / np.nanmedian(np.diff(timestamp_time))

            if np.isnan(fps) or fps < 1:
                raise ValueError
            is_default_timestamp = 0

    except (tables.exceptions.NoSuchNodeError, IOError, ValueError):
        fps = expected_fps
        is_default_timestamp = 1

    return fps, is_default_timestamp

#%%%%%% these function are related with the singleworm case it might be necesary to change them in the future


def getMicronsPerPixel(skeletons_file):
    try:
        with tables.File(skeletons_file, 'r') as fid:
            microns_per_pixel_scale = fid.get_node(
                '/stage_movement')._v_attrs['microns_per_pixel_scale']
    except (KeyError, tables.exceptions.NoSuchNodeError):
        return 1

    if microns_per_pixel_scale.size == 2:
        assert np.abs(
            microns_per_pixel_scale[0]) == np.abs(
            microns_per_pixel_scale[1])
        microns_per_pixel_scale = np.abs(microns_per_pixel_scale[0])
        return microns_per_pixel_scale
    else:
        return 1


def correctSingleWorm(worm, skeletons_file):
    ''' Correct worm positions using the stage vector calculated by alignStageMotionSegwormFun.m'''
    with tables.File(skeletons_file, 'r') as fid:
        stage_vec_ori = fid.get_node('/stage_movement/stage_vec')[:]
        timestamp_ind = fid.get_node('/timestamp/raw')[:].astype(np.int)
        rotation_matrix = fid.get_node(
            '/stage_movement')._v_attrs['rotation_matrix']
        microns_per_pixel_scale = fid.get_node(
            '/stage_movement')._v_attrs['microns_per_pixel_scale']

    # let's rotate the stage movement
    dd = np.sign(microns_per_pixel_scale)
    rotation_matrix_inv = np.dot(
        rotation_matrix * [(1, -1), (-1, 1)], [(dd[0], 0), (0, dd[1])])

    # adjust the stage_vec to match the timestamps in the skeletons
    timestamp_ind = timestamp_ind
    good = (
        timestamp_ind >= worm.first_frame) & (
        timestamp_ind <= worm.last_frame)

    ind_ff = timestamp_ind[good] - worm.first_frame
    stage_vec_ori = stage_vec_ori[good]

    stage_vec = np.full((worm.timestamp.size, 2), np.nan)
    stage_vec[ind_ff, :] = stage_vec_ori

    

    # the negative symbole is to add the stage vector directly, instead of
    # substracting it.
    stage_vec_inv = -np.dot(rotation_matrix_inv, stage_vec.T).T

    for field in ['skeleton', 'ventral_contour', 'dorsal_contour']:
        if hasattr(worm, field):
            tmp_dat = getattr(worm, field)
            # rotate the skeletons
            # for ii in range(tot_skel):
        #tmp_dat[ii] = np.dot(rotation_matrix, tmp_dat[ii].T).T
            tmp_dat = tmp_dat + stage_vec_inv[:, np.newaxis, :]
            setattr(worm, field, tmp_dat)
    return worm
#%%%%%%%
def _n_percentile(n, q): 
        if isinstance(n, (float, int)) or n.size>0:
            return np.percentile(n, q)
        else:
            return np.nan

FUNC_FOR_DIV = {'means':np.median, 'medians':np.median, 
    'P10th':partial(_n_percentile, q=10), 'P90th':partial(_n_percentile, q=90)}
    
            
def getFeatStats(worm, wStats):
    if not isinstance(wStats, WormStatsClass):
        wStats = WormStatsClass()
    # IMPORTANT assert the axis is openworm format before calculating features
    worm_openworm = copy.copy(worm)
    worm_openworm.changeAxis()
    assert worm_openworm.skeleton.shape[1] == 2
    worm_features = mv.WormFeatures(worm_openworm)
    
    def _get_worm_stat(fun):
        # calculate the mean value of each feature
        worm_stat = wStats.getWormStats(worm_features, np.mean)
        for field in wStats.extra_fields:
            worm_stat[field] = getattr(worm, field)
        return worm_stat
        
    worm_stats = {stat: _get_worm_stat(FUNC_FOR_DIV[stat]) for stat in FUNC_FOR_DIV}
    return worm_features, worm_stats

def getOpenWormData(worm, wStats=[]):
    if not isinstance(wStats, WormStatsClass):
        wStats = WormStatsClass()

    # let's make a copy of the skeletons before chaning axis
    worm_coords = {'skeletons':worm.skeleton.copy(),
                    'dorsal_contours':worm.dorsal_contour.copy(),
                    'ventral_contours':worm.ventral_contour.copy()
                    }

    # IMPORTANT change axis to an openworm format before calculating features
    assert worm.skeleton.shape[2] == 2
    #get the worm features at its stats
    worm_features, worm_stats = getFeatStats(worm, wStats)
    

    # convert the timeseries features into a recarray
    tot_frames = worm.timestamp.size
    timeseries_data = np.full(tot_frames, np.nan, wStats.feat_timeseries_dtype)

    timeseries_data['timestamp'] = worm.timestamp
    timeseries_data['worm_index'] = worm.worm_index
    timeseries_data['motion_modes'] = worm_features._features[
        'locomotion.motion_mode'].value

    for feat in wStats.feat_timeseries:
        feat_obj = wStats.features_info.loc[feat, 'feat_name_obj']
        timeseries_data[feat] = worm_features._features[feat_obj].value

    # convert the events features into a dictionary
    events_data = {}
    for feat in wStats.feat_events:
        feat_obj = wStats.features_info.loc[feat, 'feat_name_obj']
        events_data[feat] = worm_features._features[feat_obj].value

    

    return timeseries_data, events_data, worm_stats, worm_coords

def getGoodTrajIndexes(skeletons_file,
        use_skel_filter = True,
        use_manual_join = False,
        is_single_worm = False,
        feat_filt_param = {'min_num_skel':100}):
    
    assert (use_skel_filter or use_manual_join) or feat_filt_param
    if use_manual_join:
        assert hasManualJoin(skeletons_file)

    with pd.HDFStore(skeletons_file, 'r') as table_fid:
        colnames = table_fid.get_node('/trajectories_data').colnames

    if use_manual_join:
        worm_index_str = 'worm_index_manual' if 'worm_index_manual' in colnames else 'worm_index_N'
    else:
        worm_index_str = 'worm_index_joined'

    
    
    if not (use_manual_join or use_skel_filter):
        # filter the raw skeletons using the parameters in feat_filt_param
        dd = {
            x: feat_filt_param[x] for x in [
                'min_num_skel',
                'bad_seg_thresh',
                'min_displacement']}
        good_traj_index, _ = getValidIndexes(
            skeletons_file, **dd)
    else:
        
        with pd.HDFStore(skeletons_file, 'r') as table_fid:
            trajectories_data = table_fid['/trajectories_data']

        if use_manual_join:
            # select tables that were manually labeled as worms
            good = trajectories_data['worm_label'] == WLAB['WORM']
            trajectories_data = trajectories_data[good]

        if use_skel_filter and 'is_good_skel' in trajectories_data:
            # select data that was labeld in FEAT_FILTER
            good = trajectories_data['is_good_skel'] == 1
            trajectories_data = trajectories_data[good]

        
        assert worm_index_str in trajectories_data
        
        #keep only the trajectories that have at least min_num_skel valid skeletons
        N = trajectories_data.groupby(worm_index_str).agg(
            {'has_skeleton': np.nansum})
        N = N[N > feat_filt_param['min_num_skel']].dropna()
        good_traj_index = N.index
    return good_traj_index, worm_index_str

def isValidSingleWorm(skeletons_file, good_traj_index):
    '''Check if it is sigle worm and if the stage movement has been aligned successfully.'''
    try:
        with tables.File(skeletons_file, 'r') as fid:
            if fid.get_node('/stage_movement')._v_attrs['has_finished'] != 1:
                # single worm case with a bad flag termination in the stage
                # movement
                return False
            else:
                assert len(good_traj_index) <= 1
                return True
    except (tables.exceptions.NoSuchNodeError, IOError, KeyError):
        return False


def hasManualJoin(skeletons_file):
    with tables.File(skeletons_file, 'r') as fid:
        return any(x in fid.get_node('/trajectories_data').colnames for x in ['worm_index_manual', 'worm_index_N'])


def getWormFeaturesFilt(
        skeletons_file,
        features_file,
        use_skel_filter,
        use_manual_join,
        is_single_worm,
        expected_fps,
        feat_filt_param,
        split_traj_time):

    def _iniFileGroups():
        # initialize groups for the timeseries and event features
        header_timeseries = {
            feat: tables.Float32Col(
                pos=ii) for ii, (feat, _) in enumerate(
                wStats.feat_timeseries_dtype)}
                
        table_timeseries = features_fid.create_table(
            '/', 'features_timeseries', header_timeseries, filters=TABLE_FILTERS)

        # save some data used in the calculation as attributes
        table_timeseries._v_attrs['micronsPerPixel'] = micronsPerPixel
        table_timeseries._v_attrs[
            'is_default_timestamp'] = is_default_timestamp
        table_timeseries._v_attrs['fps'] = fps
        table_timeseries._v_attrs['worm_index_str'] = worm_index_str

        # node to save features events
        group_events = features_fid.create_group('/', 'features_events')

        # save the skeletons
        with tables.File(skeletons_file, 'r') as ske_file_id:
            skel_shape = ske_file_id.get_node('/skeleton').shape

        

        worm_coords_array = {}
        w_node = features_fid.create_group('/', 'coordinates')
        for  array_name in ['skeletons', 'dorsal_contours', 'ventral_contours']:
            worm_coords_array[array_name] = features_fid.create_earray(
                w_node,
                array_name,
                shape=(
                    0,
                    skel_shape[1],
                    skel_shape[2]),
                atom=tables.Float32Atom(
                    shape=()),
                filters=TABLE_FILTERS)
        
        # initialize rec array with the averaged features of each worm
        stats_features_df = {stat:np.full(tot_worms, np.nan, dtype=wStats.feat_avg_dtype) for stat in FUNC_FOR_DIV}
    
        return header_timeseries, table_timeseries, group_events, worm_coords_array, stats_features_df
    
    progress_timer = timeCounterStr('')
    def _displayProgress(n):
            # display progress
        dd = " Extracting features. Worm %i of %i done." % (n, tot_worms)
        print_flush(
            base_name +
            dd +
            ' Total time:' +
            progress_timer.getTimeStr())

    #get the valid number of worms
    good_traj_index, worm_index_str = getGoodTrajIndexes(skeletons_file,
        use_skel_filter,
        use_manual_join,
        is_single_worm, 
        feat_filt_param)
    
    #check if the stage was not aligned correctly. Return empty features file otherwise.
    if is_single_worm and not isValidSingleWorm(skeletons_file, good_traj_index):
        good_traj_index = np.array([])

    fps, is_default_timestamp = getFPS(skeletons_file, expected_fps)
    micronsPerPixel = getMicronsPerPixel(skeletons_file)
    split_traj_frames = split_traj_time*fps
    
    # function to calculate the progress time. Useful to display progress
    base_name = skeletons_file.rpartition('.')[0].rpartition(os.sep)[-1].rpartition('_')[0]
    
    with tables.File(features_file, 'w') as features_fid:

        #total number of worms
        tot_worms = len(good_traj_index)
        if tot_worms == 0:
            print_flush(base_name + ' No valid worms found to calculate features. Creating empty file.')
            return

        # initialize by getting the specs data subdivision
        wStats = WormStatsClass()
        all_splitted_feats = {stat:[] for stat in FUNC_FOR_DIV}
    

        #initialize file
        header_timeseries, table_timeseries, group_events, \
        worm_coords_array, stats_features_df = _iniFileGroups()



        _displayProgress(0)
        # start to calculate features for each worm trajectory
        for ind_N, worm_index in enumerate(good_traj_index):
            # initialize worm object, and extract data from skeletons file
            worm = WormFromTable(
                skeletons_file,
                worm_index,
                use_skel_filter=use_skel_filter,
                worm_index_str=worm_index_str,
                micronsPerPixel=micronsPerPixel,
                fps=fps,
                smooth_window=5)
            
            #corrections for the case of single worm
            if is_single_worm:
                #add experiment_info into the features file  
                with tables.File(skeletons_file, 'r') as skel_fid:
                    if '/experiment_info' in skel_fid:
                        dd = skel_fid.get_node('/experiment_info').read()
                        features_fid.create_array(
                            '/', 'experiment_info', obj=dd)
                        assert not isBadVentralOrient(skeletons_file)

                assert worm_index == 1 and ind_N == 0
                worm = correctSingleWorm(worm, skeletons_file)
                if np.all(np.isnan(worm.skeleton[:, 0, 0])):
                    return

            # calculate features
            timeseries_data, events_data, worm_stats, worm_coords= \
                getOpenWormData(worm, wStats)
            
            #get splitted features
            splitted_worms = [x for x in worm.splitWormTraj(split_traj_frames) 
            if x.n_valid_skel > feat_filt_param['min_num_skel']]
            dd = [getFeatStats(x, wStats)[1] for x in splitted_worms]
            splitted_feats = {stat:[x[stat] for x in dd] for stat in FUNC_FOR_DIV}

            #%% add data to save
            # save timeseries data
            table_timeseries.append(timeseries_data)
            table_timeseries.flush()


            # save skeletons
            for key in worm_coords_array:
                worm_coords_array[key].append(worm_coords[key])
                worm_coords_array[key].flush()

            # save event data as a subgroup per worm
            worm_node = features_fid.create_group(
                group_events, 'worm_%i' % worm_index)
            worm_node._v_attrs['worm_index'] = worm_index
            worm_node._v_attrs['frame_range'] = np.array(
                (worm.first_frame, worm.last_frame))

            for feat in events_data:
                tmp_data = events_data[feat]
                # consider the cases where the output is a single number, empty
                # or None
                if isinstance(tmp_data, (float, int)):
                    tmp_data = np.array([tmp_data])
                if tmp_data is None or tmp_data.size == 0:
                    tmp_data = np.array([np.nan])
                features_fid.create_carray(
                    worm_node, feat, obj=tmp_data, filters=TABLE_FILTERS)

            # store the average for each worm feature
            for stat in FUNC_FOR_DIV:
                stats_features_df[stat][ind_N] = worm_stats[stat]
                
                #append the splitted traj features
                all_splitted_feats[stat] += splitted_feats[stat]
            #%%
            # report progress
            _displayProgress(ind_N + 1)
            
        
        # create and save a table containing the averaged worm feature for each
        # worm
        f_node = features_fid.create_group('/', 'features_summary')
        for stat in FUNC_FOR_DIV:
            features_fid.create_table(
                f_node, stat, obj = stats_features_df[stat], filters = TABLE_FILTERS)
            
            feat_stat_split = features_fid.create_table(
                f_node, stat + '_split', obj=np.array(all_splitted_feats[stat]), filters=TABLE_FILTERS)
            feat_stat_split._v_attrs['split_traj_frames'] = split_traj_frames
        
        #FUTURE: I am duplicating this field for backward compatibility, I should remove it later on.
        features_fid.create_table('/', 'features_means', obj = stats_features_df['means'], filters = TABLE_FILTERS)
        feat_stat_split = features_fid.create_table('/', 'features_means_split', obj=np.array(all_splitted_feats['means']), filters=TABLE_FILTERS)
        
        print_flush(
            base_name +
            ' Feature extraction finished: ' +
            progress_timer.getTimeStr())
#%%
if __name__ == '__main__':
    from MWTracker.helper.tracker_param import tracker_param
    skeletons_file = '/Users/ajaver/Tmp/Results/FirstRun_181016/HW_N1_Set2_Pos6_Ch1_18102016_140043_skeletons.hdf5'
    features_file = skeletons_file.replace('_skeletons.hdf5', '_features.hdf5')
    
    
    param = tracker_param()
    is_single_worm = False
    use_manual_join = False
    use_skel_filter = True
    expected_fps = 25
    
    good_traj_index, worm_index_str = getGoodTrajIndexes(skeletons_file,
        use_skel_filter,
        use_manual_join,
        is_single_worm, 
        param.feat_filt_param)
    
    micronsPerPixel = getMicronsPerPixel(skeletons_file)
    fps, is_default_timestamp = getFPS(skeletons_file, expected_fps)
    
    worm_index = good_traj_index[0]
    worm = WormFromTable(
                skeletons_file,
                worm_index,
                use_skel_filter=use_skel_filter,
                worm_index_str=worm_index_str,
                micronsPerPixel=micronsPerPixel,
                fps=fps,
                smooth_window=5)
    
    split_traj_frames = 300*fps
    splitted_worms = [x for x in worm.splitWormTraj(split_traj_frames) 
            if x.n_valid_skel > 100]
    
    wStats = WormStatsClass()
    dd = [getFeatStats(x, wStats)[1] for x in splitted_worms]
    splitted_feats = {stat:[x[stat] for x in dd] for stat in FUNC_FOR_DIV}
#    worm_openworm = copy.copy(worm)
#    worm_openworm.changeAxis()
#    assert worm_openworm.skeleton.shape[1] == 2
#    worm_features = mv.WormFeatures(worm_openworm)
#    
#    wStats = WormStatsClass()
#    worm_stats = wStats.getWormStats(worm_features, np.mean)


    
#%%
#    getWormFeaturesFilt(
#        skeletons_file,
#        features_file,
#        use_skel_filter,
#        use_manual_join,
#        is_single_worm,
#        **param.feats_param)
