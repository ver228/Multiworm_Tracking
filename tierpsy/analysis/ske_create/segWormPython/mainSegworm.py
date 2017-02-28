# -*- coding: utf-8 -*-
"""
Created on Wed May 20 12:46:20 2015

@author: ajaver
"""

import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter

from .linearSkeleton import linearSkeleton
from .getHeadTail import getHeadTail, rollHead2FirstIndex
from .cython_files.segWorm_cython import circComputeChainCodeLengths
from .cleanWorm import circSmooth, extremaPeaksCircDist

# wrappers around C functions
from .cython_files.circCurvature import circCurvature

errMsg = {104 : '''The worm has 3 or more low-frequency sampled convexities
        sharper than 90 degrees (possible head/tail points).''',
          105 : '''The worm contour has less than 2 high-frequency sampled
        convexities sharper than 60 degrees (the head and tail).
        Therefore, the worm is coiled or obscured and cannot be segmented.''',
          106: '''The worm length, from head to tail, is more than
        twice as large on one side than it is on the other.
        Therefore, the worm is coiled or obscured and cannot be segmented.'''
          }


def get_contour_angles(contour, cnt_chain_code_len, cnt_worm_segments, edge_len_hi_freq):
    
    cnt_ang_hi_freq = circCurvature(
        contour, edge_len_hi_freq, cnt_chain_code_len)

    edge_len_low_freq = 2 * edge_len_hi_freq
    cnt_ang_low_freq = circCurvature(
        contour, edge_len_low_freq, cnt_chain_code_len)

    #% Blur the contour's local high-frequency curvature.
    #% Note: on a small scale, noise causes contour imperfections that shift an
    #% angle from its correct location. Therefore, blurring angles by averaging
    #% them with their neighbors can localize them better.
    worm_seg_size = contour.shape[0] / cnt_worm_segments
    blur_size_hi_freq = np.ceil(worm_seg_size / 2)
    cnt_ang_hi_freq = circSmooth(cnt_ang_hi_freq, blur_size_hi_freq)
    
    #% Compute the contour's local high/low-frequency curvature maxima.
    maxima_hi_freq, maxima_hi_freq_ind = extremaPeaksCircDist(
        1, cnt_ang_hi_freq, edge_len_hi_freq, cnt_chain_code_len)

    maxima_low_freq, maxima_low_freq_ind = extremaPeaksCircDist(
        1, cnt_ang_low_freq, edge_len_low_freq, cnt_chain_code_len)

    
    #pack output
    
    hi_freq_output = cnt_ang_hi_freq, maxima_hi_freq, maxima_hi_freq_ind, edge_len_hi_freq
    low_freq_output = cnt_ang_low_freq, maxima_low_freq, maxima_low_freq_ind, edge_len_low_freq
    
    return hi_freq_output, low_freq_output


def contour2Skeleton(contour, ske_worm_segments = 24, head_angle_thresh=60):
    # contour must be a Nx2 numpy array
    assert isinstance(
        contour,
        np.ndarray) and contour.ndim == 2 and contour.shape[1] == 2

    if contour.dtype != np.double:
        contour = contour.astype(np.double)

    #% The worm is roughly divided into 24 segments of musculature (i.e., hinges
    #% that represent degrees of freedom) on each side. Therefore, 48 segments
    #% around a 2-D contour.
    #% Note: "In C. elegans the 95 rhomboid-shaped body wall muscle cells are
    #% arranged as staggered pairs in four longitudinal bundles located in four
    #% quadrants. Three of these bundles (DL, DR, VR) contain 24 cells each,
    #% whereas VL bundle contains 23 cells." - www.wormatlas.org
    cnt_worm_segments = 2 * ske_worm_segments

    # this line does not really seem to be useful
    #contour = cleanWorm(contour, cnt_worm_segments)

    #% The contour is too small.
    if contour.shape[0] < cnt_worm_segments:
        err_msg = 'Contour is too small'
        return 4 * [np.zeros(0)] + [err_msg]

    # make sure the contours are in the counter-clockwise direction
    # head tail indentification will not work otherwise
    # x1y2 - x2y1(http://mathworld.wolfram.com/PolygonArea.html)
    signed_area = np.sum(
        contour[:-1, 0] * contour[1:, 1] - contour[1:, 0] * contour[:-1, 1]) / 2
    if signed_area > 0:
        contour = np.ascontiguousarray(contour[::-1, :])

    # make sure the array is C_continguous. Several functions required this.
    if not contour.flags['C_CONTIGUOUS']:
        contour = np.ascontiguousarray(contour)

    #% Compute the contour's local high/low-frequency curvature.
    #% Note: worm body muscles are arranged and innervated as staggered pairs.
    #% Therefore, 2 segments have one theoretical degree of freedom (i.e. one
    #% approximation of a hinge). In the head, muscles are innervated
    #% individually. Therefore, we sample the worm head's curvature at twice the
    #% frequency of its body.
    #% Note 2: we ignore Nyquist sampling theorem (sampling at twice the
    #% frequency) since the worm's cuticle constrains its mobility and practical
    #% degrees of freedom.

    cnt_chain_code_len = circComputeChainCodeLengths(contour)
    worm_seg_length = (cnt_chain_code_len[
                       0] + cnt_chain_code_len[-1]) / cnt_worm_segments

    #calculate contour angles
    hi_freq_output, low_freq_output = get_contour_angles(contour, 
                                                         cnt_chain_code_len, 
                                                         cnt_worm_segments, 
                                                         worm_seg_length)

    #unpack data
    cnt_ang_hi_freq, maxima_hi_freq, maxima_hi_freq_ind, edge_len_hi_freq = hi_freq_output
    cnt_ang_low_freq, maxima_low_freq, maxima_low_freq_ind, edge_len_low_freq = low_freq_output
    
    #identify head/tail
    head_ind, tail_ind, err_msg = getHeadTail(cnt_ang_low_freq, 
                                              maxima_low_freq_ind, 
                                              cnt_ang_hi_freq, 
                                              maxima_hi_freq_ind, 
                                              cnt_chain_code_len, 
                                              head_angle_thresh)

    if err_msg != 0:
        return 4 * [np.zeros(0)] + [err_msg]

    # change arrays so the head correspond to the first position
    head_ind, tail_ind, contour, cnt_chain_code_len, cnt_ang_low_freq, maxima_low_freq_ind = \
        rollHead2FirstIndex(head_ind, 
                            tail_ind, 
                            contour, 
                            cnt_chain_code_len, 
                            cnt_ang_low_freq, 
                            maxima_low_freq_ind)

    #% Compute the contour's local low-frequency curvature minima.
    minima_low_freq, minima_low_freq_ind = extremaPeaksCircDist(-1, 
                                                                cnt_ang_low_freq, 
                                                                edge_len_low_freq, 
                                                                cnt_chain_code_len)

    #% Compute the worm's skeleton.
    skeleton, cnt_widths = linearSkeleton(head_ind, 
                                          tail_ind, 
                                          minima_low_freq, 
                                          minima_low_freq_ind,
                                          maxima_low_freq, 
                                          maxima_low_freq_ind, 
                                          contour.copy(), 
                                          worm_seg_length, 
                                          cnt_chain_code_len)

    # The head must be in position 0
    assert head_ind == 0

    # Get the contour for each side.
    cnt_side1 = contour[:tail_ind + 1, :].copy()
    cnt_side2 = np.vstack([contour[0, :], contour[:tail_ind - 1:-1, :]])

    assert np.all(cnt_side1[0] == cnt_side2[0])
    assert np.all(cnt_side1[-1] == cnt_side2[-1])
    assert np.all(skeleton[-1] == cnt_side1[-1])
    assert np.all(skeleton[0] == np.round(cnt_side2[0]))

    return (skeleton, cnt_side1, cnt_side2, cnt_widths, '')


def orientWorm(skeleton, prev_skeleton, cnt_side1, cnt_side2, cnt_widths):
    if skeleton.size == 0:
        return skeleton, cnt_side1, cnt_side2, cnt_widths, np.float(0)

    # orient head tail with respect to hte previous worm
    if prev_skeleton.size > 0:
        #dist2prev_head = np.sum((skeleton[0:3,:]-prev_skeleton[0:3,:])**2)
        #dist2prev_tail = np.sum((skeleton[0:3,:]-prev_skeleton[-3:,:])**2)

        # if the skeleton is wrongly oriented switching it must decrease the
        # error by a lot.
        dist2prev_head = np.sum((skeleton - prev_skeleton)**2)
        dist2prev_tail = np.sum((skeleton - prev_skeleton[::-1, :])**2)
        if dist2prev_head > dist2prev_tail:
            # the skeleton is switched
            skeleton = skeleton[::-1, :]
            cnt_widths = cnt_widths[::-1]
            cnt_side1 = cnt_side1[::-1, :]
            cnt_side2 = cnt_side2[::-1, :]

    # make sure the contours are in the counter-clockwise direction
    # x1y2 - x2y1(http://mathworld.wolfram.com/PolygonArea.html)
    contour = np.vstack((cnt_side1, cnt_side2[::-1, :]))
    signed_area = np.sum(
        contour[:-1, 0] * contour[1:, 1] - contour[1:, 0] * contour[:-1, 1]) / 2
    if signed_area < 0:
        cnt_side1, cnt_side2 = cnt_side2, cnt_side1

    return skeleton, cnt_side1, cnt_side2, cnt_widths, np.abs(signed_area)


def resample_curve(curve, resampling_N=49, widths=np.zeros(0)):
    '''Resample curve to have resampling_N equidistant segments'''

    # calculate the cumulative length for each segment in the curve
    dx = np.diff(curve[:, 0])
    dy = np.diff(curve[:, 1])
    dr = np.sqrt(dx * dx + dy * dy)

    lengths = np.cumsum(dr)
    lengths = np.hstack((0, lengths))  # add the first point
    tot_length = lengths[-1]

    # Verify array lengths
    if len(lengths) < 2 or len(curve) < 2:
        return None, None, None

    fx = interp1d(lengths, curve[:, 0])
    fy = interp1d(lengths, curve[:, 1])

    subLengths = np.linspace(0 + np.finfo(float).eps, tot_length, resampling_N)

    # I add the epsilon because otherwise the interpolation will produce nan
    # for zero
    try:
        resampled_curve = np.zeros((resampling_N, 2))
        resampled_curve[:, 0] = fx(subLengths)
        resampled_curve[:, 1] = fy(subLengths)
        if widths.size > 0:
            fw = interp1d(lengths, widths)
            widths = fw(subLengths)
    except ValueError:
        resampled_curve = np.full((resampling_N, 2), np.nan)
        widths = np.full(resampling_N, np.nan)

    return resampled_curve, tot_length, widths


def smooth_curve(curve, window=5, pol_degree=3):
    '''smooth curves using the savgol_filter'''

    if curve.shape[0] < window:
        # nothing to do here return an empty array
        return np.full_like(curve, np.nan)

    # consider the case of one (widths) or two dimensions (skeletons, contours)
    if curve.ndim == 1:
        smoothed_curve = savgol_filter(curve, window, pol_degree)
    else:
        smoothed_curve = np.zeros_like(curve)
        for nn in range(curve.ndim):
            smoothed_curve[:, nn] = savgol_filter(
                curve[:, nn], window, pol_degree)

    return smoothed_curve


def resampleAll(skeleton, cnt_side1, cnt_side2, cnt_widths, resampling_N):
    '''I am only resample for the moment'''
    # resample data
    skeleton, ske_len, cnt_widths = resample_curve(
        skeleton, resampling_N, cnt_widths)
    cnt_side1, _, _ = resample_curve(cnt_side1, resampling_N)
    cnt_side2, _, _ = resample_curve(cnt_side2, resampling_N)

    #skeleton = smooth_curve(skeleton)
    #cnt_widths = smooth_curve(cnt_widths)
    #cnt_side1 = smooth_curve(cnt_side1)
    #cnt_side2 = smooth_curve(cnt_side2)

    return skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths


def getSkeleton(worm_cnt, prev_skeleton=np.zeros(0), resampling_N=49, 
                num_segments = 24, head_angle_thresh=60):
    '''
    resampling_N -> The final number of points the skeleton, and each contour will have.
    num_segments -> number of segments used to calculate the skeleton curvature 
        (or half the number of segments used for the contour curvature). 
        Reduced for rounder objects and decreased for sharper organisms.
        
    head_angle_thresh -> the threshold to consider a peak on the curvature as the head or tail.
    '''
    n_output_param = 6  # number of expected output parameters

    if worm_cnt.size == 0:
        return (n_output_param) * [np.zeros(0)]
        
    assert isinstance(
        worm_cnt,
        np.ndarray) and worm_cnt.ndim == 2 and worm_cnt.shape[1] == 2

    # make sure the worm contour is float
    worm_cnt = worm_cnt.astype(np.float32)
    skeleton, cnt_side1, cnt_side2, cnt_widths, err_msg = \
    contour2Skeleton(worm_cnt, num_segments, head_angle_thresh)

    if skeleton.size == 0:
        return (n_output_param) * [np.zeros(0)]

    # resample curves
    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths = \
        resampleAll(skeleton, cnt_side1, cnt_side2, cnt_widths, resampling_N)

    # orient skeleton with respect to the previous skeleton
    skeleton, cnt_side1, cnt_side2, cnt_widths, cnt_area = \
        orientWorm(skeleton, prev_skeleton, cnt_side1, cnt_side2, cnt_widths)

    output_data = (
        skeleton,
        ske_len,
        cnt_side1,
        cnt_side2,
        cnt_widths,
        cnt_area)
    assert len(output_data) == n_output_param
    return output_data
