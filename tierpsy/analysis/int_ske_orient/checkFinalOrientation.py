# -*- coding: utf-8 -*-
"""
Created on Tue Mar 15 15:37:12 2016

@author: ajaver
"""

import glob
import os

import numpy as np
import pandas as pd
import tables

from scipy.signal import savgol_filter
from tierpsy.analysis.ske_orient.checkHeadOrientation import isWormHTSwitched
from tierpsy.helper.misc import print_flush


def getHeadProbMov(
        skeletons_file,
        trajectories_worm,
        max_gap_allowed=10,
        window_std=25,
        segment4angle=5,
        min_block_size=250):

    skel_group = (
        trajectories_worm['skeleton_id'].min(),
        trajectories_worm['skeleton_id'].max())

    with tables.File(skeletons_file, 'r') as fid:
        good_skeletons = trajectories_worm['int_map_id'].values != -1
        skeletons_id = trajectories_worm['skeleton_id'].values[good_skeletons]

        dd = fid.get_node('/skeleton').shape
        skeletons = np.full((len(good_skeletons), dd[1], dd[2]), np.nan)

        if len(skeletons_id) > 0:
            skeletons[good_skeletons, :, :] = fid.get_node(
                '/skeleton')[skeletons_id, :, :]
        else:
            return np.nan, skel_group
    
    #savgol_filter does not accept even windows
    if window_std % 2 == 0:
        window_std += 1
    
    #get the indexes of valid skeletons
    skel_ind_valid = ~np.isnan(skeletons[:, 0, 0])
    
    #smooth on time to reduce the variance but only on the points that are going to be used to calculate the angles
    for nn in [0, segment4angle, -segment4angle -1 , -1]:
        for ii in range(2):
            dat = pd.Series(skeletons[:, nn, ii]).fillna(method='ffill').fillna(method='bfill')
            dat = savgol_filter(dat, window_std, 3)
            skeletons[:, nn, ii] = dat
    
    
    #total range in coordinates of the head movement
    top = np.max(skeletons[:, 0], axis=0)
    bot = np.min(skeletons[:, 0], axis=0)
    head_path_range = np.sqrt(np.sum((top-bot)**2))
    
    #average head tail distance
    ht_dist = np.sqrt(((skeletons[:, 0] - skeletons[:, -1])**2).sum(axis=1))
    ht_dist_avg = np.nanmean(ht_dist)/2
    
    #%%
    if head_path_range < ht_dist_avg:
        #here I find that it works better to use a very large window since the movement is less
        window_std = window_std*50
        
        #make sure the the window is at most half of the total size of the valid skeletons window
        dd, = np.where(skel_ind_valid)
        bot, top = dd[0], dd[-1]
        
        N = max(1, (top-bot + 1)//2)
        window_std = min(window_std, N)
    
    
    is_switch_skel, roll_std = isWormHTSwitched(skeletons, 
                                                segment4angle=segment4angle, 
                                                max_gap_allowed=max_gap_allowed, 
                                                window_std = window_std, 
                                                min_block_size=min_block_size)
    #%%
    #calculate the head tail probability at each point and get the average
    p_mov = roll_std['head_angle']/(roll_std['head_angle'] +roll_std['tail_angle'])
    
    
    #remove values that are too small, if the std is zero i cannot really calculate this values
    dd = roll_std['head_angle'] + roll_std['tail_angle']
    ind_valid = skel_ind_valid & (dd > 1e-3)
    p_mov = p_mov.values[ind_valid]
    
    if p_mov.size == 0:
        import pdb
        pdb.set_trace()
    #average using only the indexes of valid skeletons
    p_mov_avg = np.nanmean(p_mov)
    
    return p_mov_avg, skel_group


def searchIntPeaks(
    median_int,
    peak_search_limits=[
        0.054,
        0.192,
        0.269,
        0.346]):
    '''
    Look for local maxima in the intensity profile, it will first look for a minima within
    0 and search lim 0, then for a maxima between the minima and the search lim 1,
    then for a minima and finally for a maxima...
    '''
    length_resampling = median_int.shape[0]

    peaks_ind = []
    hh = 0
    tt = length_resampling
    for ii, ds in enumerate(peak_search_limits):
        peak_lim = round(ds * length_resampling)
        func_search = np.argmin if ii % 2 == 0 else np.argmax

        hh = func_search(median_int[hh:peak_lim]) + hh

        dd = length_resampling - peak_lim
        tt = func_search(median_int[dd:tt]) + dd

        peaks_ind.append((hh, tt))

    return peaks_ind


def getHeadProvInt(
        intensities_file,
        trajectories_worm,
        min_block_size,
        peak_search_limits):
    '''
    Calculate the probability of an intensity profile being in the correct orientation according to the intensity profile
    '''
    with tables.File(intensities_file, 'r') as fid:
        int_map_id = trajectories_worm.loc[
            trajectories_worm['int_map_id'] != -1, 'int_map_id']
        if int_map_id.size == 0 or int_map_id.size < min_block_size:
            # the number of maps is too small let's return nan's nothing to do
            # here
            return np.nan, np.nan, []

        worm_int = fid.get_node(
            '/straighten_worm_intensity_median')[int_map_id].astype(np.float)

    worm_int -= np.median(worm_int, axis=1)[:, np.newaxis]
    # get the median intensity profile
    median_int = np.median(worm_int, axis=0)

    # search for the peaks in the intensity profile (the head typically have a
    # minimum, follow by a maximum, then a minimum and then a maxima)
    peaks_ind = searchIntPeaks(median_int,
                               peak_search_limits=peak_search_limits)

    # calculate the distance between the second minima and the second maxima
    headbot2neck = median_int[peaks_ind[3][0]] - median_int[peaks_ind[2][0]]
    headbot2neck = 0 if headbot2neck < 0 else headbot2neck

    tailbot2waist = median_int[peaks_ind[3][1]] - median_int[peaks_ind[2][1]]
    tailbot2waist = 0 if tailbot2waist < 0 else tailbot2waist

    p_int_bot = headbot2neck / (headbot2neck + tailbot2waist)

    # calculate the distance between the second minima and the first maxima
    headtop2bot = median_int[peaks_ind[1][0]] - median_int[peaks_ind[2][0]]
    headtop2bot = 0 if headtop2bot < 0 else headtop2bot

    tailtop2bot = median_int[peaks_ind[1][1]] - median_int[peaks_ind[2][1]]
    tailtop2bot = 0 if tailtop2bot < 0 else tailtop2bot
    p_int_top = headtop2bot / (headtop2bot + tailtop2bot)

    int_group = (np.min(int_map_id), np.max(int_map_id))

    #    #%%
    #    plt.figure()
    #    plt.title(base_name)
    #    plt.plot(median_int, label ='0.3')
    #
    #    strC = 'rgck'
    #    for ii, dd in enumerate(peaks_ind):
    #        for xx in dd:
    #            plt.plot(xx, median_int[xx], 'o' + strC[ii])

    return p_int_top, p_int_bot, int_group


def checkFinalOrientation(
        skeletons_file,
        intensities_file,
        trajectories_worm,
        min_block_size,
        head_tail_param):
    peak_search_limits = [0.054, 0.192, 0.269, 0.346]

    p_mov, skel_group = getHeadProbMov(
        skeletons_file, 
        trajectories_worm, 
        **head_tail_param)

    p_int_top, p_int_bot, int_group = getHeadProvInt(
        intensities_file, trajectories_worm, min_block_size, peak_search_limits=peak_search_limits)

    # The weights I am using will give the p_tot > 0.5 as long as the
    # std of the head is twice than the tail, if it is less the intensity
    # will take a higher role. The difference between the second minimum (traquea)
    # and the second maximum (neck) given by p_int_bot, seems to be a better predictor,
    # since typically the second maxima does not exists in the tail. However,
    # the difference between the first maximum (head tip) and the second mimimum (traquea)
    # given by p_int_top, can be important therefore both weights are similar.
    p_tot = 0.75 * p_mov + 0.15 * p_int_bot + 0.1 * p_int_top

    # if it is nan, both int changes where negatives, equal the probability to
    # the p_mov
    if p_tot != p_tot:
        p_tot = p_mov

    return p_tot, [skel_group], [int_group]

#%%
if __name__ == '__main__':
    from tierpsy.analysis.int_ske_orient.correctHeadTailIntensity import switchBlocks

    check_dir = '/Users/ajaver/Desktop/Videos/single_worm/agar_1/MaskedVideos/'

    head_tail_param = {
        'max_gap_allowed': 10,
        'window_std': 25,
        'segment4angle': 5,
        'min_block_size': 250}
    #peak_search_limits = [0.054, 0.192, 0.269, 0.346]

    all_median = []
    for ff in glob.glob(os.path.join(check_dir, '*')):
        ff = ff.replace('MaskedVideos', 'Results')
        base_name = os.path.split(ff)[1].rpartition('.')[0]
        
        trajectories_file = ff[:-5] + '_trajectories.hdf5'
        skeletons_file = ff[:-5] + '_skeletons.hdf5'
        intensities_file = ff[:-5] + '_intensities.hdf5'

        # check the file finished in the correct step
        # with tables.File(skeletons_file, 'r') as fid:
        #    assert fid.get_node('/skeleton')._v_attrs['has_finished'] >= 4

        with pd.HDFStore(skeletons_file, 'r') as fid:
            trajectories_data = fid['/trajectories_data']

        grouped_trajectories = trajectories_data.groupby('worm_index_joined')
        tot_worms = len(grouped_trajectories)
        # variables to report progress
        base_name = skeletons_file.rpartition(
            '.')[0].rpartition(os.sep)[-1].rpartition('_')[0]

        print_flush(
            base_name +
            " Checking if the final Head-Tail orientation is correct")
        for index_n, (worm_index, trajectories_worm) in enumerate(
                grouped_trajectories):

            p_tot, skel_group, int_group = checkFinalOrientation(
                skeletons_file, intensities_file, trajectories_worm, head_tail_param)
            
            if p_tot < 0.5:
                switchBlocks(
                    skel_group,
                    skeletons_file,
                    int_group,
                    intensities_file)
