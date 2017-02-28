# -*- coding: utf-8 -*-
"""
Created on Wed May 13 19:35:04 2015

@author: ajaver
"""

import os
import sys

import numpy as np
import pandas as pd
import tables

from tierpsy.analysis.ske_orient.WormClass import WormClass
from tierpsy.helper.misc import print_flush
from tierpsy.helper.timeCounterStr import timeCounterStr


def getAnglesDelta(dx, dy):
    '''
    Calculate angles and fix for any jump between -2pi to 2pi
    '''
    angles = np.arctan2(dx, dy)
    dAngles = np.diff(angles)

    # %+1 to cancel shift of diff
    positiveJumps = np.where(dAngles > np.pi)[0] + 1
    negativeJumps = np.where(dAngles < -np.pi)[0] + 1

    #% subtract 2pi from remainging data after positive jumps
    for jump in positiveJumps:
        angles[jump:] = angles[jump:] - 2 * np.pi

    #% add 2pi to remaining data after negative jumps
    for jump in negativeJumps:
        angles[jump:] = angles[jump:] + 2 * np.pi

    #% rotate skeleton angles so that mean orientation is zero
    meanAngle = np.mean(angles)
    angles = angles - meanAngle

    return angles, meanAngle


def calculateHeadTailAng(skeletons, segment4angle, good):
    '''
    For each skeleton two angles are caculated: one vector between the index 0 and segment4angle ('head'), and the other from the index -1 and -segment4angle-1 ('tail').
    '''
    angles_head = np.empty(skeletons.shape[0])
    angles_head.fill(np.nan)
    angles_tail = angles_head.copy()

    dx = skeletons[good, segment4angle, 0] - skeletons[good, 0, 0]
    dy = skeletons[good, segment4angle, 1] - skeletons[good, 0, 1]

    angles_head[good], _ = getAnglesDelta(dx, dy)

    dx = skeletons[good, -segment4angle - 1, 0] - skeletons[good, -1, 0]
    dy = skeletons[good, -segment4angle - 1, 1] - skeletons[good, -1, 1]

    angles_tail[good], _ = getAnglesDelta(dx, dy)
    return angles_head, angles_tail


def getBlocksIDs(invalid, max_gap_allowed):
    '''The skeleton array is divided in blocks of contingous skeletons with
    a gap between unskeletonized frames less than max_gap_allowed'''

    good_ind = np.where(~invalid)[0]
    delTs = np.diff(good_ind)

    block_ind = np.zeros_like(good_ind)
    block_ind[0] = 1
    for ii, delT in enumerate(delTs):
        if delT < max_gap_allowed:
            block_ind[ii + 1] = block_ind[ii]
        else:
            block_ind[ii + 1] = block_ind[ii] + 1
    block_ids = np.zeros(invalid.size, dtype=np.int)

    tot_blocks = block_ind[-1]
    block_ids[good_ind] = block_ind

    return block_ids, tot_blocks


def isWormHTSwitched(skeletons, segment4angle=5, max_gap_allowed=10,
                     window_std=25, min_block_size=250):
    '''
    Determine if the skeleton is correctly oriented going from head to tail. The skeleton array is divided in blocks of contingous skeletons with a gap between unskeletonized frames less than max_gap_allowed.
    For each skeleton two angles are caculated: one vector between the index 0 and segment4angle ('head'), and the other from the index -1 and -segment4angle-1 ('tail'). The amount of head/tail movement is determined by the time rolling (moving) standard deviation (std). If most of the skeletons in the rolling std in a given block are larger for the tail than for the head, the block is flagged as switched. Only blocks larger than min_block_size are used to determine orientation. If a block has less elements than min_block_size it is flagged according to the value of its nearest "big" block.

    '''
    invalid = np.isnan(skeletons[:, 0, 0])

    # get contigous skeletons blocks
    block_ids, tot_blocks = getBlocksIDs(invalid, max_gap_allowed)

    # calculate head and tail angles.
    angles_head, angles_tail = calculateHeadTailAng(
        skeletons, segment4angle, block_ids != 0)

    # calculate the rolling std
    ts = pd.DataFrame({'head_angle': angles_head, 'tail_angle': angles_tail})

    roll_std = ts.rolling(
        window=window_std,
        min_periods=window_std -
        max_gap_allowed).std()

    # determinte if the head in a skeleton has a larger rolling std than the
    # tail
    roll_std["is_head"] = (roll_std['head_angle'] > roll_std['tail_angle'])
    roll_std["block_id"] = block_ids

    # this function will return nan if the number of elements in the group is
    # less than min_block_size
    mean_relevant = lambda x: x.mean() if x.count() > min_block_size else np.nan

    # get the probability of a block being a head
    head_prob = roll_std.groupby('block_id').agg({'is_head': mean_relevant})

    head_prob.loc[0] = np.nan
    # fill nan, forward with the last valid observation, and then first
    # backward with the next valid observation
    head_prob = head_prob.fillna(method='ffill').fillna(method='bfill')

    # create flags to determined if the skeleton is switched
    is_switch_block = np.squeeze(head_prob.values) < 0.5
    is_switch_skel = is_switch_block[block_ids]
    return is_switch_skel, roll_std


def correctHeadTail(skeletons_file, max_gap_allowed=10, window_std=25,
                    segment4angle=5, min_block_size=250):
    '''
    Correct Head Tail orientation using skeleton movement. Head must move more than the tail (have a higher rolling standar deviation). This might fail if the amount of contingously skeletonized frames is too little (a few seconds). Head must be in the first position of the single frame skeleton array, while the tail must be in the last.

    max_gap_allowed - maximimun number of consecutive skeletons lost before consider it a new block
    window_std - frame windows to calculate the standard deviation
    segment4angle - separation between skeleton segments to calculate the angles
    min_block_size - consider only around 10s intervals to determine if it is head or tail...
    '''
    base_name = skeletons_file.rpartition(
        '.')[0].rpartition(os.sep)[-1].rpartition('_')[0]

    with pd.HDFStore(skeletons_file, 'r') as ske_file_id:
        indexes_data = ske_file_id[
            '/trajectories_data'][['worm_index_joined', 'skeleton_id']]
        # get the first and last frame of each worm_index
        rows_indexes = indexes_data.groupby(
            'worm_index_joined').agg([min, max])['skeleton_id']
        del indexes_data

    # check if the skeletonization finished succesfully
    with tables.File(skeletons_file, "r") as ske_file_id:
        skeleton_table = ske_file_id.get_node('/skeleton')
        if 'has_finished' in dir(skeleton_table._v_attrs):
            assert skeleton_table._v_attrs['has_finished'] >= 2

    progress_timer = timeCounterStr('')
    for ii, dat in enumerate(rows_indexes.iterrows()):
        if ii % 10 == 0:
            dd = " Correcting Head-Tail using worm movement. Worm %i of %i." % (
                ii + 1, len(rows_indexes))
            dd = base_name + dd + ' Total time:' + progress_timer.getTimeStr()
            print_flush(dd)
            sys.stdout.flush()

        worm_index, row_range = dat
        worm_data = WormClass(skeletons_file, worm_index,
                              rows_range=(row_range['min'], row_range['max']))

        if not np.all(np.isnan(worm_data.skeleton_length)):
            is_switched_skel, roll_std = isWormHTSwitched(worm_data.skeleton,
                                                          segment4angle=segment4angle, max_gap_allowed=max_gap_allowed,
                                                          window_std=window_std, min_block_size=min_block_size)

            worm_data.switchHeadTail(is_switched_skel)

        worm_data.writeData()
        #%%
    print_flush(
        'Head-Tail correction using worm movement finished:' +
        progress_timer.getTimeStr())

    with tables.File(skeletons_file, "r+") as ske_file_id:
        # Mark a succesful termination
        ske_file_id.get_node('/skeleton')._v_attrs['has_finished'] = 3

if __name__ == "__main__":
    #root_dir = '/Users/ajaver/Desktop/Gecko_compressed/20150511/'
    #base_name = 'Capture_Ch1_11052015_195105'
    #root_dir = '/Users/ajaver/Desktop/Gecko_compressed/20150512/'
    #base_name = 'Capture_Ch3_12052015_194303'

    skeletons_file = root_dir + '/Trajectories/' + base_name + '_skeletons.hdf5'

    # correctHeadTail(skeletons_file, max_gap_allowed = 10, \
    # window_std = 25, segment4angle = 5, min_block_size = 250)
