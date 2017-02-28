# -*- coding: utf-8 -*-
"""
Created on Sat Feb 13 19:00:43 2016

@author: ajaver
"""
import collections
import os

import numpy as np
import pandas as pd
import tables
from scipy.ndimage.filters import median_filter, minimum_filter, maximum_filter

from MWTracker.analysis.int_ske_orient.checkFinalOrientation import checkFinalOrientation
from MWTracker.helper.misc import print_flush
from MWTracker.helper.timeCounterStr import timeCounterStr


def medabsdev(x): return np.median(np.abs(np.median(x) - x))


def createBlocks(flags_vector, min_block_size=0):
    # divide data into groups of continous indexes
    blocks = np.zeros(flags_vector.shape, np.int)

    lab_ind = 0
    prev_ind = False
    group_ini = []
    group_fin = []
    for ii, flag_ind in enumerate(flags_vector):

        if not prev_ind and flag_ind:
            group_ini.append(ii)
        if prev_ind and not flag_ind:
            # substract one size this is the condition one after the end of the
            # block
            group_fin.append(ii - 1)
        prev_ind = flag_ind
    # append the last index if the group ended in the last index
    if len(group_ini) - len(group_fin) == 1:
        group_fin.append(ii)
    assert len(group_ini) == len(group_fin)

    # change this into a single list of tuples
    groups = list(zip(group_ini, group_fin))

    # remove any group smaller than the min_block_size
    groups = [gg for gg in groups if gg[1] - gg[0] >= min_block_size]
    return groups


def _fuseOverlapingGroups(corr_groups, gap_size=0):
    '''Helper function of correctBlock.
        -- gap_size, gap between blocks
    '''
    # ensure the groups are sorted
    corr_groups = sorted(corr_groups)

    if len(corr_groups) == 1:
        return corr_groups
    else:
        # fuse groups that overlap
        ini, fin = corr_groups[0]
        corr_groups_f = []  # [(ini,fin)]
        for gg in corr_groups[1:]:
            if fin + gap_size >= gg[0]:
                fin = gg[1]
            else:
                corr_groups_f.append((ini, fin))
                ini, fin = gg

        corr_groups_f.append((ini, fin))

        return corr_groups_f


def correctBlock(groups, new_flag_vec, gap_size=0):
    if len(groups) == 0:
        return groups  # nothing to do here

    corr_groups = []
    maxInd = len(new_flag_vec) - 1
    for gg in groups:
        # loop until it reaches the window borders or find an false index
        ini = gg[0]
        while ini > 0:  # and ini > gg[0]-smooth_W:
            if not new_flag_vec[ini - 1]:
                break
            ini -= 1

        fin = gg[1]
        # print('a',fin)

        while fin < maxInd:  # and fin < gg[1]+smooth_W:
            if not new_flag_vec[fin + 1]:
                break
            fin += 1

        # print('b',fin)

        corr_groups.append((ini, fin))
    assert len(groups) == len(corr_groups)

    return _fuseOverlapingGroups(corr_groups, gap_size=gap_size)


def checkLocalVariation(worm_int_profile, groups, local_avg_win=10):
    corr_groups = []

    groups = sorted(groups)

    tot_groups = len(groups)
    max_index = len(groups) - 1

    min_loc_avg_win = max(1, local_avg_win // 2)

    for ii in range(tot_groups):

        gg = groups[ii]

        # get the limits from the previous and enxt index
        prev_group = (-1, -1) if ii == 0 else groups[ii - 1]
        next_group = (
            tot_groups,
            tot_groups) if ii == max_index else groups[
            ii + 1]

        med_block = np.median(worm_int_profile[gg[0]:gg[1] + 1], axis=0)

        m_dif_ori_left = 0
        m_dif_inv_left = 0
        m_dif_ori_right = 0
        m_dif_inv_right = 0

        # get previous contigous map limits
        bot = max(gg[0] - local_avg_win, prev_group[1] + 1)
        top = gg[0] - 1

        if top - bot + 1 >= min_loc_avg_win:
            med_block_left = np.median(worm_int_profile[bot:top + 1], axis=0)

            m_dif_ori_left = np.sum(np.abs(med_block - med_block_left))
            m_dif_inv_left = np.sum(np.abs(med_block - med_block_left[::-1]))

        # get next contigous map limits
        bot = gg[1] + 1
        top = min(gg[1] + local_avg_win, next_group[0] - 1)

        if top - bot + 1 >= min_loc_avg_win:
            #med_block = np.median(worm_avg[min(gg[1]-local_avg_win, gg[0]):gg[1]+1], axis=0)
            med_block_right = np.median(worm_int_profile[bot:top + 1], axis=0)

            m_dif_ori_right = np.sum(np.abs(med_block - med_block_right))
            m_dif_inv_right = np.sum(np.abs(med_block - med_block_right[::-1]))

        # combine both, we only need to have a size that show a very big change when the intensity map is switch
        # if m_dif_inv_left+m_dif_inv_right < m_dif_ori_left+m_dif_ori_right:
        if m_dif_inv_left <= m_dif_ori_left and m_dif_inv_right <= m_dif_ori_right:
            corr_groups.append(gg)

    return corr_groups


def removeBadSkelBlocks(
        groups,
        int_skeleton_id,
        trajectories_worm,
        min_frac_in,
        gap_size):
    if len(groups) == 0:
        return groups  # nothing to do here

    assert trajectories_worm['worm_index_joined'].unique().size == 1

    # get the index of the skeletons that delimited the candiate block to be
    # inverted
    skel_group = [(int_skeleton_id[ini], int_skeleton_id[fin])
                  for ini, fin in groups]

    # change index in the original worm skeletons matrix
    first_skel = trajectories_worm.index[0]
    int_skel_group = [(x - first_skel, y - first_skel) for x, y in skel_group]

    # create globs according if consecutive frames have an skeleton map (if
    # the have valid filtered  skeletons)
    good = (trajectories_worm['int_map_id'] != -1).values
    has_skel_group = createBlocks(good, min_block_size=0)

    # get the gaps location before fussing groups, otherwise we will over
    # estimate the size of the groups
    is_gap = np.full(len(trajectories_worm), True, np.bool)
    for kk, gg in enumerate(has_skel_group):
        is_gap[gg[0]:gg[1] + 1] = False

    # fuse skeletons blocks to be more stringent with the selection
    has_skel_group = _fuseOverlapingGroups(has_skel_group, gap_size=gap_size)

    # to test for overlaps let's created a vector with the labeled groups
    has_blocks_flags = np.full(len(trajectories_worm), -1, np.int)
    for kk, gg in enumerate(has_skel_group):
        has_blocks_flags[gg[0]:gg[1] + 1] = kk

    # remove labels from the gaps
    has_blocks_flags[is_gap] = -1

    # total number of skeletons for each group
    blocks_sizes = collections.Counter(has_blocks_flags)

    # total number of skeletons of a given group inside a block to be switched
    blocks_in = []
    for gg in int_skel_group:
        blocks_in += list(has_blocks_flags[gg[0]:gg[1] + 1])
    blocks_in_size = collections.Counter(blocks_in)

    # calculate the fraction of skeletons of each group insde a block
    blocks_in_frac = {x: (blocks_in_size[x] / blocks_sizes[x])
                      for x in blocks_in_size if x != -1}

    # only keep groups that has at least blocks_in_frac skeletons inside the
    # block
    corr_skel_group = [has_skel_group[x]
                       for x in blocks_in_frac if blocks_in_frac[x] >= min_frac_in]

    # shift the index to match the general trajectories_table
    corr_skel_group = [(x + first_skel, y + first_skel)
                       for x, y in corr_skel_group]

    # convert from skeleton row id in the worm profile_intensities
    int_map_ord = {dd: kk for kk, dd in enumerate(int_skeleton_id)}
    corr_groups = [(int_map_ord[x], int_map_ord[y])
                   for x, y in corr_skel_group]
    # correct for contingous groups
    if len(corr_groups) > 1:
        corr_groups = _fuseOverlapingGroups(corr_groups, gap_size=1)

    return corr_groups


def dat_switch(X, r_range):
    fin = r_range[1] + 1
    dat = X[r_range[0]:fin]
    X[r_range[0]:fin] = dat[:, ::-1]


def dat_swap(X, Y, r_range):
    fin = r_range[1] + 1
    dat_x = X[r_range[0]:fin]
    dat_y = Y[r_range[0]:fin]
    X[r_range[0]:fin] = dat_y
    Y[r_range[0]:fin] = dat_x


def dat_switch_swap(X, Y, r_range):
    fin = r_range[1] + 1
    dat_x = X[r_range[0]:fin]
    dat_y = Y[r_range[0]:fin]
    X[r_range[0]:fin] = dat_y[:, ::-1]
    Y[r_range[0]:fin] = dat_x[:, ::-1]


def switchBlocks(skel_group, skeletons_file, int_group, intensities_file):
    with tables.File(skeletons_file, 'r+') as fid:
        contour_side1 = fid.get_node('/contour_side1')
        contour_side2 = fid.get_node('/contour_side2')
        skeleton = fid.get_node('/skeleton')
        contour_width = fid.get_node('/contour_width')

        #cnt1_length = fid.get_node('/contour_side1_length')
        #cnt2_length = fid.get_node('/contour_side2_length')

        # w_head_t = fid.get_node('/width_head_tip')
        # w_head_b = fid.get_node('/width_head_base')
        # w_neck = fid.get_node('/width_neck')
        # w_hips = fid.get_node('/width_hips')
        # w_tail_b = fid.get_node('/width_tail_base')
        # w_tail_t = fid.get_node('/width_tail_tip')

        for gg in skel_group:
            dat_switch_swap(contour_side1, contour_side2, gg)

            dat_switch(skeleton, gg)
            dat_switch(contour_width, gg)

            #dat_swap(cnt1_length, cnt2_length, gg)
            #dat_swap(w_head_t, w_tail_t, gg)
            #dat_swap(w_head_b, w_tail_b, gg)
            #dat_swap(w_hips, w_neck, gg)
        fid.flush()

    with tables.File(intensities_file, 'r+') as fid:
        worm_int_med = fid.get_node('/straighten_worm_intensity_median')
        for gg in int_group:
            dat_switch(worm_int_med, gg)

        if '/straighten_worm_intensity' in fid:
            worm_int = fid.get_node('/straighten_worm_intensity')

            for ini, fin in int_group:
                dat = worm_int[ini:fin + 1, :, :]
                worm_int[ini:fin + 1, :, :] = dat[:, ::-1, ::-1]
        fid.flush()


def getDampFactor(length_resampling):
    # this is small window that reduce the values on the head a tail, where a
    # segmentation error or noise can have a very big effect
    MM = length_resampling // 4
    rr = (np.arange(MM) / (MM - 1)) * 0.9 + 0.1
    damp_factor = np.ones(length_resampling)
    damp_factor[:MM] = rr
    damp_factor[-MM:] = rr[::-1]
    return damp_factor


def correctHeadTailIntWorm(
        trajectories_worm,
        skeletons_file,
        intensities_file,
        smooth_W=5,
        gap_size=0,
        min_block_size=10,
        local_avg_win=25,
        min_frac_in=0.85):

    # get data with valid intensity maps (worm int profile)
    good = trajectories_worm['int_map_id'] != -1
    int_map_id = trajectories_worm.loc[good, 'int_map_id'].values
    int_skeleton_id = trajectories_worm.loc[good, 'skeleton_id'].values
    int_frame_number = trajectories_worm.loc[good, 'frame_number'].values

    # only analyze data that contains at least  min_block_size intensity
    # profiles
    if int_map_id.size == 0 or int_map_id.size < min_block_size:
        return []

    # read the worm intensity profiles
    with tables.File(intensities_file, 'r') as fid:
        worm_int_profile = fid.get_node(
            '/straighten_worm_intensity_median')[int_map_id, :]

    # normalize intensities of each individual profile
    worm_int_profile -= np.median(worm_int_profile, axis=1)[:, np.newaxis]

    # reduce the importance of the head and tail. This parts are typically
    # more noisy
    damp_factor = getDampFactor(worm_int_profile.shape[1])
    worm_int_profile *= damp_factor

    # worm median intensity
    med_int = np.median(worm_int_profile, axis=0).astype(np.float)

    #%%
    # let's check for head tail errors by comparing the
    # total absolute difference between profiles using the original
    # orientation ...
    diff_ori = np.sum(np.abs(med_int - worm_int_profile), axis=1)
    #... and inverting the orientation
    diff_inv = np.sum(np.abs(med_int[::-1] - worm_int_profile), axis=1)

    #%% DEPRECATED, it
    # check if signal noise will allow us to distinguish between the two signals
    # I am assuming that most of the images will have a correct head tail orientation
    # and the robust estimates will give us a good representation of the noise levels
    # if np.median(diff_inv) - medabsdev(diff_inv)/2 < np.median(diff_ori) + medabsdev(diff_ori)/2:
    #    bad_worms.append(worm_index)
    #    continue

    #%%
    # smooth data, it is easier for identification
    diff_ori_med = median_filter(diff_ori, smooth_W)
    diff_inv_med = median_filter(diff_inv, smooth_W)

    # this will increase the distance between the original and the inversion.
    # Therefore it will become more stringent on detection
    diff_orim = minimum_filter(diff_ori_med, smooth_W)
    diff_invM = maximum_filter(diff_inv_med, smooth_W)

    # a segment with a bad head-tail indentification should have a lower
    # difference with the median when the profile is inverted.
    bad_orientationM = diff_orim > diff_invM
    if np.all(bad_orientationM):
        return []

    # let's create blocks of skeletons with a bad orientation
    blocks2correct = createBlocks(bad_orientationM, min_block_size)
    # print(blocks2correct)

    # let's refine blocks limits using the original unsmoothed differences
    bad_orientation = diff_ori > diff_inv
    blocks2correct = correctBlock(blocks2correct, bad_orientation, gap_size=0)

    # let's correct the blocks inversion boundaries by checking that they do not
    # travers a group of contigous skeletons. I am assuming that head tail errors
    # only can occur when we miss an skeleton.
    blocks2correct = removeBadSkelBlocks(
        blocks2correct,
        int_skeleton_id,
        trajectories_worm,
        min_frac_in,
        gap_size=gap_size)

    # Check in the boundaries between blocks if there is really a better local
    # match if the block is inverted
    blocks2correct = checkLocalVariation(
        worm_int_profile, blocks2correct, local_avg_win)
    if not blocks2correct:
        return []

    # redefine the limits in the skeleton_file and intensity_file rows using
    # the final blocks boundaries
    skel_group = [(int_skeleton_id[ini], int_skeleton_id[fin])
                  for ini, fin in blocks2correct]
    int_group = [(int_map_id[ini], int_map_id[fin])
                 for ini, fin in blocks2correct]

    # finally switch all the data to correct for the wrong orientation in each
    # group
    switchBlocks(skel_group, skeletons_file, int_group, intensities_file)

    # store data from the groups that were switched
    switched_blocks = []
    for ini, fin in blocks2correct:
        switched_blocks.append((int_frame_number[ini], int_frame_number[fin]))

    return switched_blocks


def correctHeadTailIntensity(
        skeletons_file,
        intensities_file,
        smooth_W=5,
        gap_size=0,
        min_block_size=10,
        local_avg_win=25,
        min_frac_in=0.85,
        head_tail_param={}):

    # get the trajectories table
    with pd.HDFStore(skeletons_file, 'r') as fid:
        trajectories_data = fid['/trajectories_data']
        # at this point the int_map_id with the intensity maps indexes must
        # exist in the table
        assert 'int_map_id' in trajectories_data

    grouped_trajectories = trajectories_data.groupby('worm_index_joined')

    tot_worms = len(grouped_trajectories)

    # variables to report progress
    base_name = skeletons_file.rpartition(
        '.')[0].rpartition(os.sep)[-1].rpartition('_')[0]
    progress_timer = timeCounterStr('')

    bad_worms = []  # worms with not enough difference between the normal and inverted median intensity profile
    switched_blocks = []  # data from the blocks that were switched

    #ind2check = [765]
    for index_n, (worm_index, trajectories_worm) in enumerate(
            grouped_trajectories):
        # if not worm_index in ind2check: continue

        if index_n % 10 == 0:
            dd = " Correcting Head-Tail using intensity profiles. Worm %i of %i." % (
                index_n + 1, tot_worms)
            dd = base_name + dd + ' Total time:' + progress_timer.getTimeStr()
            print_flush(dd)

        # correct head tail using the intensity profiles
        dd = correctHeadTailIntWorm(
            trajectories_worm,
            skeletons_file,
            intensities_file,
            smooth_W,
            gap_size,
            min_block_size,
            local_avg_win,
            min_frac_in)

        switched_blocks += [(worm_index, t0, tf) for t0, tf in dd]

        # check that the final orientation is correct, otherwise switch the
        # whole trajectory
        p_tot, skel_group, int_group = checkFinalOrientation(
            skeletons_file, intensities_file, trajectories_worm, min_block_size, head_tail_param)
        if p_tot < 0.5:
            switchBlocks(
                skel_group,
                skeletons_file,
                int_group,
                intensities_file)

    # label the process as finished and store the indexes of the switched worms
    with tables.File(skeletons_file, 'r+') as fid:
        if not '/intensity_analysis' in fid:
            fid.create_group('/', 'intensity_analysis')

        if '/intensity_analysis/bad_worms' in fid:
            fid.remove_node('/intensity_analysis/min_block_size/bad_worms')
        if '/intensity_analysis/switched_head_tail' in fid:
            fid.remove_node('/intensity_analysis/switched_head_tail')

        if bad_worms:
            fid.create_array(
                '/intensity_analysis',
                'bad_worms',
                np.array(bad_worms))

        if switched_blocks:
            # to rec array
            switched_blocks = np.array(
                switched_blocks, dtype=[
                    ('worm_index', np.int), ('ini_frame', np.int), ('last_frame', np.int)])
            fid.create_table(
                '/intensity_analysis',
                'switched_head_tail',
                switched_blocks)

        fid.get_node('/skeleton')._v_attrs['has_finished'] = 4

    print_flush(
        base_name +
        ' Head-Tail correction using intensity profiles finished: ' +
        progress_timer.getTimeStr())

    # return bad_worms, switched_blocks

if __name__ == '__main__':
    #%%
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_18112015_075624.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_17112015_205616.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/04-03-11/MaskedVideos/575 JU440 swimming_2011_03_04__13_16_37__8.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/04-03-11/MaskedVideos/575 JU440 on food Rz_2011_03_04__12_55_53__7.hdf5'
    masked_image_file = '/Volumes/behavgenom$/GeckoVideo/Curro/MaskedVideos/exp2/Pos2_Ch2_28012016_182629.hdf5'

    skeletons_file = masked_image_file.replace('MaskedVideos', 'Results')[
        :-5] + '_skeletons.hdf5'
    intensities_file = skeletons_file.replace('_skeletons', '_intensities')

    correctHeadTailIntensity(
        skeletons_file,
        intensities_file,
        smooth_W=5,
        gap_size=0,
        min_block_size=10,
        local_avg_win=25,
        min_frac_in=0.95)
