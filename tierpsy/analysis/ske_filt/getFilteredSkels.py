# -*- coding: utf-8 -*-
"""
Created on Fri Dec 11 23:39:22 2015

@author: ajaver
"""

import pandas as pd
import tables
import numpy as np
import matplotlib.pylab as plt
import time
import glob
import warnings
import os


from MWTracker.helper.timeCounterStr import timeCounterStr
from MWTracker.helper.misc import print_flush

from sklearn.covariance import EllipticEnvelope, MinCovDet
from scipy.stats import chi2
from MWTracker.helper.misc import TABLE_FILTERS

#supress unnecessary warnings
import warnings
warnings.filterwarnings('ignore', '.*det > previous_det*',)
np.seterr(invalid='ignore')




getBaseName = lambda skeletons_file: skeletons_file.rpartition(
    os.sep)[-1].replace('_skeletons.hdf5', '')

worm_partitions = {'neck': (8, 16),
                   'midbody': (16, 33),
                   'hips': (33, 41),
                   # refinements of ['head']
                   'head_tip': (0, 4),
                   'head_base': (4, 8),    # ""
                   # refinements of ['tail']
                   'tail_base': (40, 45),
                   'tail_tip': (45, 49)}


name_width_fun = lambda part: 'width_' + part


def getValidIndexes(
        skel_file,
        min_num_skel=100,
        bad_seg_thresh=0.8,
        min_displacement=5):
    # min_num_skel - ignore trajectories that do not have at least this number of skeletons
    # min_dist - minimum distance explored by the blob to be consider a real
    # worm
    with pd.HDFStore(skel_file, 'r') as table_fid:
        trajectories_data = table_fid['/trajectories_data']

    trajectories_data = trajectories_data[
        trajectories_data['worm_index_joined'] > 0]
    valid_ind_str = 'is_good_skel' if 'is_good_skel' in trajectories_data else 'has_skeleton'

    if len(trajectories_data['worm_index_joined'].unique()) == 1:
        good_skel_row = trajectories_data['skeleton_id'][
            trajectories_data[valid_ind_str].values.astype(np.bool)].values
        return (np.array([1]), good_skel_row)

    else:

        # get the fraction of worms that were skeletonized per trajectory
        how2agg = {
            valid_ind_str: [
                'mean', 'sum'], 'coord_x': [
                'max', 'min', 'count'], 'coord_y': [
                'max', 'min']}
        tracks_data = trajectories_data.groupby(
            'worm_index_joined').agg(how2agg)

        delX = tracks_data['coord_x']['max'] - tracks_data['coord_x']['min']
        delY = tracks_data['coord_y']['max'] - tracks_data['coord_y']['min']

        # /tracks_data['coord_x']['count']
        max_avg_dist = np.sqrt(delX * delX + delY * delY)

        skeleton_fracc = tracks_data[valid_ind_str]['mean']
        skeleton_tot = tracks_data[valid_ind_str]['sum']

        good_worm = (
            skeleton_fracc >= bad_seg_thresh) & (
            skeleton_tot >= min_num_skel)
        good_worm = good_worm & (max_avg_dist > min_displacement)

        good_traj_index = good_worm[good_worm].index

        good_row = (trajectories_data.worm_index_joined.isin(good_traj_index)) \
            & (trajectories_data[valid_ind_str].values.astype(np.bool))

        good_skel_row = trajectories_data.loc[good_row, 'skeleton_id'].values
        assert np.all(good_skel_row == trajectories_data[good_row].index)

        return (good_traj_index, good_skel_row)

def saveModifiedTrajData(skeletons_file, trajectories_data):
    trajectories_recarray = trajectories_data.to_records(index=False)
    with tables.File(skeletons_file, "r+") as ske_file_id:
        newT = ske_file_id.create_table(
            '/',
            'trajectories_data_d',
            obj=trajectories_recarray,
            filters=TABLE_FILTERS)
        ske_file_id.remove_node('/', 'trajectories_data')
        newT.rename('trajectories_data')


def _h_nodes2Array(skeletons_file, nodes4fit, valid_index=-1):
    '''
    Read the groups in skeletons file and save them as a matrix.
    Used by _h_readFeat2Check
    '''
    with tables.File(skeletons_file, 'r') as fid:
        assert all(node in fid for node in nodes4fit)

        if isinstance(valid_index, (float, int)) and valid_index < 0:
            valid_index = np.arange(fid.get_node(nodes4fit[0]).shape[0])

        n_samples = len(valid_index)
        n_features = len(nodes4fit)

        X = np.zeros((n_samples, n_features))

        if valid_index.size > 0:
            for ii, node in enumerate(nodes4fit):
                X[:, ii] = fid.get_node(node)[valid_index]

        return X


def _h_readFeat2Check(skeletons_file, valid_index=-1):
    nodes4fit = ['/skeleton_length', '/contour_area', '/width_midbody']

    worm_morph = _h_nodes2Array(skeletons_file, nodes4fit, valid_index)

    with tables.File(skeletons_file, 'r') as fid:
        if isinstance(valid_index, (float, int)) and valid_index < 0:
            valid_index = np.arange(fid.get_node(nodes4fit[0]).shape[0])

        cnt_widths = fid.get_node('/contour_width')[valid_index, :]

        sample_N = cnt_widths.shape[1]
        ht_limits = int(round(sample_N / 7))

        head_widths = cnt_widths[:, 1:ht_limits]
        tail_widths = cnt_widths[:, -ht_limits:-1]

        # The log(x+1e-1) transform skew the distribution to the right, so the lower values have a higher change to
        # be outliers.I do this because a with close to zero is typically an
        # oulier.
        head_widthsL = np.log(head_widths + 1)
        tail_widthsL = np.log(tail_widths + 1)

    return worm_morph, head_widths, tail_widths, head_widthsL, tail_widthsL


def _h_getMahalanobisRobust(dat, critical_alpha=0.01, good_rows=np.zeros(0)):
    '''Calculate the Mahalanobis distance from the sample vector.'''
    if good_rows.size == 0:
        good_rows = np.any(~np.isnan(dat), axis=1)

    try:
        dat2fit = dat[good_rows]
        assert not np.any(np.isnan(dat2fit))

        robust_cov = MinCovDet().fit(dat2fit)
        mahalanobis_dist = np.sqrt(robust_cov.mahalanobis(dat))
    except ValueError:
        # this step will fail if the covariance matrix is not singular. This happens if the data is not
        # a unimodal symetric distribution. For example there is too many small noisy particles. Therefore
        # I will take a safe option and return zeros in the mahalanobis
        # distance if this is the case.
        mahalanobis_dist = np.zeros(dat.shape[0])

    # critial distance of the maholanobis distance using the chi-square distirbution
    # https://en.wikiversity.org/wiki/Mahalanobis%27_distance
    # http://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html
    maha_lim = chi2.ppf(1 - critical_alpha, dat.shape[1])
    outliers = mahalanobis_dist > maha_lim

    return mahalanobis_dist, outliers, maha_lim


def _h_getPerpContourInd(
        skeleton,
        skel_ind,
        contour_side1,
        contour_side2,
        contour_width):
    # get the closest point in the contour from a line perpedicular to the skeleton.
    #%%

    # get the slop of a line perpendicular to the keleton
    dR = skeleton[skel_ind + 1] - skeleton[skel_ind - 1]
    #m = dR[1]/dR[0]; M = -1/m
    a = -dR[0]
    b = +dR[1]

    c = b * skeleton[skel_ind, 1] - a * skeleton[skel_ind, 0]

    max_width_squared = np.max(contour_width)**2
    # modified from https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line
    #a = M, b = -1

    # make sure we are not selecting a point that get traversed by a coiled
    # worm
    dist2cnt1 = np.sum((contour_side1 - skeleton[skel_ind])**2, axis=1)
    d1 = np.abs(a * contour_side1[:, 0] - b * contour_side1[:, 1] + c)
    d1[dist2cnt1 > max_width_squared] = np.nan

    dist2cnt2 = np.sum((contour_side2 - skeleton[skel_ind])**2, axis=1)
    d2 = np.abs(a * contour_side2[:, 0] - b * contour_side2[:, 1] + c)
    d2[dist2cnt2 > max_width_squared] = np.nan
    
    try:
        cnt1_ind = np.nanargmin(d1)
        cnt2_ind = np.nanargmin(d2)
    except ValueError:
        cnt1_ind = np.nan
        cnt2_ind = np.nan
    
    return cnt1_ind, cnt2_ind


def _h_calcArea(cnt):
    # make sure the contours are in the counter-clockwise direction
    # x1y2 - x2y1(http://mathworld.wolfram.com/PolygonArea.html)
    signed_area = np.sum(cnt[:-1, 0] * cnt[1:, 1] - cnt[1:, 0] * cnt[:-1, 1])
    return np.abs(signed_area / 2)

def filterPossibleCoils(
        skeletons_file,
        max_width_ratio=2.25,
        max_area_ratio=6):
    with pd.HDFStore(skeletons_file, 'r') as table_fid:
        trajectories_data = table_fid['/trajectories_data']

    if not 'is_good_skel' in trajectories_data:
        is_good_skel = trajectories_data['has_skeleton'].values.copy()
    else:
        is_good_skel = trajectories_data['is_good_skel'].values.copy()
    
    tot_skeletons = len(is_good_skel)
    with tables.File(skeletons_file, 'r') as ske_file_id:

        skeletons = ske_file_id.get_node('/skeleton')
        contour_side1s = ske_file_id.get_node('/contour_side1')
        contour_side2s = ske_file_id.get_node('/contour_side2')
        contour_widths = ske_file_id.get_node('/contour_width')

        sample_N = contour_widths.shape[1]

        ht_limits = int(round(sample_N / 6))
        mid_limits = (int(round(3 * sample_N / 6)),
                      int(round(4 * sample_N / 6)) + 1)

        for skel_id in range(tot_skeletons):
            if is_good_skel[skel_id] == 0:
                continue

            contour_width = contour_widths[skel_id]
            contour_side1 = contour_side1s[skel_id]
            contour_side2 = contour_side2s[skel_id]
            skeleton = skeletons[skel_id]


            #%%
            edge_length = 8
            p1 = contour_side1[:-edge_length]
            p2 = contour_side1[edge_length:]

            points = contour_side1[edge_length // 2:-edge_length // 2]
            ang2 = np.arctan2(points[:, 0] - p2[:, 0], points[:, 1] - p2[:, 1])
            ang1 = np.arctan2(p1[:, 0] - points[:, 0], p1[:, 1] - points[:, 1])
            angles = ang2 - ang1

            for i in range(angles.size):
                if angles[i] > np.pi:
                    angles[i] = angles[i] - 2 * np.pi
                elif angles[i] < -np.pi:
                    angles[i] = angles[i] + 2 * np.pi
            angles = angles * 180 / np.pi

            blurWin = np.full(edge_length, 1. / edge_length)
            anglesb = np.convolve(angles, blurWin, 'same')
            #%%
            # the idea is that when the worm coils and there is an skeletons, it is
            # likely to be a cnonsequence of the head/tail protuding, therefore we can
            # use the head/tail withd to get a good ratio of the worm width

            # calculate head and tail width
            head_w = contour_width[ht_limits]
            tail_w = contour_width[-ht_limits]
            midbody_w = np.max(contour_width)

            '''
            Does the worm more than double its width from the head/tail?
            Note: if the worm coils, its width will grow to more than
            double that at the end of the head.
            '''
            if midbody_w / head_w > max_width_ratio or midbody_w / \
                    tail_w > max_width_ratio or max(head_w / tail_w, tail_w / head_w) > max_width_ratio:
                is_good_skel[skel_id] = 0
                continue

            # calculate the head and tail area (it is an approximation the
            # limits are not super well defined, but it is enough for
            # filtering)
            head_skel_lim = skeleton[np.newaxis, ht_limits]
            tail_skel_lim = skeleton[np.newaxis, -ht_limits]

            cnt_side1_ind_h, cnt_side2_ind_h = _h_getPerpContourInd(
                skeleton, ht_limits, contour_side1, contour_side2, contour_width)
            cnt_side1_ind_t, cnt_side2_ind_t = _h_getPerpContourInd(
                skeleton, -ht_limits, contour_side1, contour_side2, contour_width)

            if cnt_side1_ind_h > cnt_side1_ind_t or cnt_side2_ind_h > cnt_side2_ind_t or \
            np.any(np.isnan([cnt_side1_ind_h, cnt_side2_ind_h, cnt_side1_ind_t, cnt_side2_ind_t])):    
                is_good_skel[skel_id] = 0
                continue
            
            # if cnt_side1_ind_h>cnt_side1_ind_t:
            #    cnt_side1_ind_h, cnt_side1_ind_t = cnt_side1_ind_t, cnt_side1_ind_h
            # if cnt_side2_ind_h>cnt_side2_ind_t:
            #    cnt_side2_ind_h, cnt_side2_ind_t = cnt_side2_ind_t, cnt_side2_ind_h

            cnt_head = np.concatenate((contour_side1[:cnt_side1_ind_h + 1], head_skel_lim,
                                           contour_side2[:cnt_side2_ind_h + 1][::-1]))

            cnt_tail = np.concatenate(
                (contour_side2[cnt_side2_ind_t:][::-1],
                    tail_skel_lim,
                    contour_side1[cnt_side1_ind_t:]))

            area_head = _h_calcArea(cnt_head)
            area_tail = _h_calcArea(cnt_tail)

            '''Is the tail too small (or the head too large)?
            Note: the area of the head and tail should be roughly the same size.
            A 2-fold difference is huge!
            '''
            if area_tail == 0 or area_head == 0 or area_head / \
                    area_tail > max_width_ratio or area_tail / area_head > max_width_ratio:
                is_good_skel[skel_id] = 0
                continue

            # calculate the area of the rest of the body
            cnt_rest = np.concatenate(
                (head_skel_lim,
                 contour_side1[
                     cnt_side1_ind_h:cnt_side1_ind_t + 1],
                    tail_skel_lim,
                    contour_side2[
                     cnt_side2_ind_h:cnt_side2_ind_t + 1][
                     ::-1],
                    head_skel_lim))
            area_rest = _h_calcArea(cnt_rest)

            '''
            Are the head and tail too small (or the body too large)?
            Note: earlier, the head and tail were each chosen to be 4/24 = 1/6
            the body length of the worm. The head and tail are roughly shaped
            like rounded triangles with a convex taper. And, the width at their
            ends is nearly the width at the center of the worm. Imagine they were
            2 triangles that, when combined, formed a rectangle similar to the
            midsection of the worm. The area of this rectangle would be greater
            than a 1/6 length portion from the midsection of the worm (the
            maximum area per length in a worm is located at its midsection). The
            combined area of the right and left sides is 4/6 of the worm.
            Therefore, the combined area of the head and tail must be greater
            than (1/6) / (4/6) = 1/4 the combined area of the left and right
            sides.
            '''
            if area_rest / (area_head + area_tail) > max_area_ratio:
                is_good_skel[skel_id] = 0
                continue
    trajectories_data['is_good_skel'] = is_good_skel
    saveModifiedTrajData(skeletons_file, trajectories_data)


def _h_calAreaSignedArray(cnt_side1, cnt_side2):
    '''calculate the contour area using the shoelace method, the sign indicate the contour orientation.'''
    assert cnt_side1.shape == cnt_side2.shape
    if cnt_side1.ndim == 2:
        # if it is only two dimenssion (as if in a single skeleton).
        # Add an extra dimension to be compatible with the rest of the code
        cnt_side1 = cnt_side1[np.newaxis, :, :]
        cnt_side2 = cnt_side2[np.newaxis, :, :]

    contour = np.hstack((cnt_side1, cnt_side2[:, ::-1, :]))
    signed_area = np.sum(
        contour[:,:-1,0] * contour[:,1:,1] -
        contour[:,1:,0] * contour[:,:-1,1],
        axis=1)/ 2
    
    assert signed_area.size == contour.shape[0]
    return signed_area

def _h_calAreaArray(cnt_side1, cnt_side2):
    '''calculate the contour area using the shoelace method'''
    signed_area = _h_calAreaSignedArray(cnt_side1, cnt_side2)
    return np.abs(signed_area)

def _addMissingFields(skeletons_file):
    '''
    Add missing fields that might have not been calculated before in older videos.
    '''
    with tables.File(skeletons_file, 'r+') as fid:
        if not '/contour_area' in fid:
            contour_side1 = fid.get_node('/contour_side1')[:]
            contour_side2 = fid.get_node('/contour_side2')[:]
            cnt_area = _h_calAreaArray(contour_side1, contour_side2)
            fid.create_carray('/', "contour_area", obj=cnt_area, filters=TABLE_FILTERS)

        if not '/width_midbody' in fid:
            midbody_ind = (17, 32)
            contour_width = fid.get_node('/contour_width')[:]
            width_midbody = np.median(contour_width[:, midbody_ind[0]:midbody_ind[1]+1], axis=1)
            fid.create_carray('/', "width_midbody", obj=width_midbody, filters=TABLE_FILTERS)

def filterByPopulationMorphology(skeletons_file, good_skel_row, critical_alpha=0.01):
    base_name = getBaseName(skeletons_file)
    progress_timer = timeCounterStr('')

    print_flush(base_name + ' Filter Skeletons: Starting...')
    with pd.HDFStore(skeletons_file, 'r') as table_fid:
        trajectories_data = table_fid['/trajectories_data']

    if not 'is_good_skel' in trajectories_data:
        trajectories_data['is_good_skel'] = trajectories_data['has_skeleton']

    if good_skel_row.size > 0:
        # nothing to do if there are not valid skeletons left.

        print_flush(
            base_name +
            ' Filter Skeletons: Reading features for outlier identification.')
        
        #add possible missing fields that were con calculated in older versions of the software
        _addMissingFields(skeletons_file)
        
        # calculate classifier for the outliers
        nodes4fit = ['/skeleton_length', '/contour_area', '/width_midbody']
        worm_morph = _h_nodes2Array(skeletons_file, nodes4fit, -1)
        #worm_morph[~trajectories_data['is_good_skel'].values] = np.nan
        feats4fit = [worm_morph]

        #feats4fit = _h_readFeat2Check(skeletons_file)

        print_flush(
            base_name +
            ' Filter Skeletons: Calculating outliers. Total time:' +
            progress_timer.getTimeStr())

        tot_rows2fit = feats4fit[0].shape[0]
        # check all the data to fit has the same size in the first axis
        assert all(tot_rows2fit == featdat.shape[0] for featdat in feats4fit)
        outliers_rob = np.zeros(tot_rows2fit, np.bool)
        outliers_flag = np.zeros(tot_rows2fit, np.int)
        assert len(feats4fit) < 64  # otherwise the outlier flag will not work

        for out_ind, dat in enumerate(feats4fit):
            maha, out_d, lim_d = _h_getMahalanobisRobust(
                dat, critical_alpha, good_skel_row)
            outliers_rob = outliers_rob | out_d

            # flag the outlier flag by turning on the corresponding bit
            outliers_flag += (out_d) * (2**out_ind)

        print_flush(
            base_name +
            ' Filter Skeletons: Labeling valid skeletons. Total time:' +
            progress_timer.getTimeStr())

        # labeled rows of valid individual skeletons as GOOD_SKE
        trajectories_data['is_good_skel'] &= ~outliers_rob
        trajectories_data['skel_outliers_flag'] = outliers_flag

    # Save the new is_good_skel column
    saveModifiedTrajData(skeletons_file, trajectories_data)

    print_flush(
        base_name +
        ' Filter Skeletons: Finished. Total time:' +
        progress_timer.getTimeStr())


def getFilteredSkels(
        skeletons_file,
        min_num_skel=100,
        bad_seg_thresh=0.8,
        min_displacement=5,
        critical_alpha=0.01,
        max_width_ratio=2.25,
        max_area_ratio=6):

    # check if the skeletonization finished succesfully
    with tables.File(skeletons_file, "r") as ske_file_id:
        skeleton_table = ske_file_id.get_node('/skeleton')

    #eliminate skeletons that do not match a decent head, tail and body ratio. Likely to be coils. Taken from Segworm.
    filterPossibleCoils(
        skeletons_file,
        max_width_ratio=max_width_ratio,
        max_area_ratio=max_area_ratio)

    # get valid rows using the trajectory displacement and the
    # skeletonization success. These indexes will be used to calculate statistics of what represent a valid skeleton.
    good_traj_index, good_skel_row = getValidIndexes(
        skeletons_file, min_num_skel=min_num_skel, bad_seg_thresh=bad_seg_thresh, min_displacement=min_displacement)

    #filter skeletons depending the population morphology (area, width and length)
    filterByPopulationMorphology(
        skeletons_file,
        good_skel_row,
        critical_alpha=critical_alpha)

    with tables.File(skeletons_file, "r+") as ske_file_id:
        skeleton_table = ske_file_id.get_node('/skeleton')
        # label as finished
        skeleton_table._v_attrs['has_finished'] = 2
