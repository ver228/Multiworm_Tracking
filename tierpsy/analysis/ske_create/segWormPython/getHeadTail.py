# -*- coding: utf-8 -*-
"""
Created on Sun May 24 10:54:16 2015

@author: ajaver
"""
import numpy as np


def absDistanceCirc(one_index, several_index, cnt_chain_code_len):
    dist = np.abs(
        cnt_chain_code_len[one_index] -
        cnt_chain_code_len[several_index])
    dist = np.min((dist, cnt_chain_code_len[-1] - dist), axis=0)  # wrapping
    return dist


def headTailIndex(angles, peak1_ind, peak2_ind):
    #% Note: the tail should have a sharper angle.
    if angles[peak1_ind] <= angles[peak2_ind]:
        head_ind = peak1_ind
        tail_ind = peak2_ind
    else:
        head_ind = peak2_ind
        tail_ind = peak1_ind
    return head_ind, tail_ind


def isHeadTailTouching(head_ind, tail_ind, cnt_chain_code_len):
    ''' Are the sides within 0.5 of each others size?
     Note: if a worm's length from head to tail is at least twice larger
     on one side (relative to the other), than the worm must be touching
     itself. Find the length of each side.'''
    if head_ind > tail_ind:
        size1 = cnt_chain_code_len[head_ind] - cnt_chain_code_len[tail_ind]
        size2 = cnt_chain_code_len[-1] - \
            cnt_chain_code_len[head_ind] + cnt_chain_code_len[tail_ind]
    else:
        size1 = cnt_chain_code_len[tail_ind] - cnt_chain_code_len[head_ind]
        size2 = cnt_chain_code_len[-1] - \
            cnt_chain_code_len[tail_ind] + cnt_chain_code_len[head_ind]

    return min(size1, size2) / max(size1, size2) <= .5


def getHeadTail(
        cnt_ang_low_freq,
        maxima_low_freq_ind,
        cnt_ang_hi_freq,
        maxima_hi_freq_ind,
        cnt_chain_code_len,
        angle_thresh_hi_freq=60):
    
    angle_thresh_low_freq = angle_thresh_hi_freq*1.5
    # We will consider only possible head/tail points
    # values larger than 90 for the low freqency sampling
    # and 60 for the high frequency sampling
    good = cnt_ang_hi_freq[maxima_hi_freq_ind] > angle_thresh_hi_freq
    maxima_hi_freq_ind = maxima_hi_freq_ind[good]

    good = cnt_ang_low_freq[maxima_low_freq_ind] > angle_thresh_low_freq
    maxima_low_freq_ind = maxima_low_freq_ind[good]

    #% Are there too many possible head/tail points?
    if maxima_low_freq_ind.size > 2:

        return -1, -1, 104  # more three or more candidates for head and tail

    #% Are the head and tail on the outer contour?
    if maxima_hi_freq_ind.size < 2:
        return -1, -1, 105

    if maxima_low_freq_ind.size == 2:
        # Easy case, there is only two head/tail candidates
        head_ind, tail_ind = headTailIndex(
            cnt_ang_low_freq, maxima_low_freq_ind[0], maxima_low_freq_ind[1])

        #% Localize the HEAD by finding its nearest, sharpest (but blurred),
        #% high-frequency convexity.
        distance = absDistanceCirc(
            head_ind,
            maxima_hi_freq_ind,
            cnt_chain_code_len)
        head_ind = maxima_hi_freq_ind[np.argmin(distance)]

        #% Localize the TAIL by finding its nearest, sharpest (but blurred),
        #% high-frequency convexity.
        distance = absDistanceCirc(
            tail_ind,
            maxima_hi_freq_ind,
            cnt_chain_code_len)
        tail_ind = maxima_hi_freq_ind[np.argmin(distance)]

    elif maxima_hi_freq_ind.size == 2:
        #% The high-frequency sampling identifies the head and tail.
        head_ind, tail_ind = headTailIndex(
            cnt_ang_hi_freq, maxima_hi_freq_ind[0], maxima_hi_freq_ind[1])

    else:
        #% The high-frequency sampling identifies several, potential heads/tails.

        #% Initialize our head and tail choise.
        head_ind = maxima_hi_freq_ind[0]
        tail_ind = maxima_hi_freq_ind[1]

        #% How far apart are the head and tail?
        dist_head_tail = absDistanceCirc(
            head_ind, tail_ind, cnt_chain_code_len)

        #% Search for the 2 sharp convexities that are furthest apart.
        for i in range(maxima_hi_freq_ind.size - 1):
            for j in range(i + 1, maxima_hi_freq_ind.size):
                #% How far apart are these 2 convexities?
                dist_ij = absDistanceCirc(
                    maxima_hi_freq_ind[i],
                    maxima_hi_freq_ind[j],
                    cnt_chain_code_len)
                #% These 2 convexities are better head and tail choices.
                if dist_ij > dist_head_tail:
                    head_ind = maxima_hi_freq_ind[i]
                    tail_ind = maxima_hi_freq_ind[j]

        head_ind, tail_ind = headTailIndex(cnt_ang_hi_freq, head_ind, tail_ind)

    # one of the sides is too short so it might be touching itself (coiling)
    if isHeadTailTouching(head_ind, tail_ind, cnt_chain_code_len):
        return head_ind, tail_ind, 106
    else:
        return head_ind, tail_ind, 0


def rollHead2FirstIndex(
        head_ind,
        tail_ind,
        contour,
        cnt_chain_code_len,
        cnt_ang_low_freq,
        maxima_low_freq_ind):
    assert head_ind >= 0 and tail_ind >= 0
    #% Orient the contour and angles at the maximum curvature (the head or tail).
    if head_ind > 0:
        contour = np.roll(contour, -head_ind, axis=0)
        cnt_chain_code_len = np.append(cnt_chain_code_len[head_ind:] - cnt_chain_code_len[head_ind - 1], cnt_chain_code_len[
                                       0:head_ind] + (cnt_chain_code_len[-1] - cnt_chain_code_len[head_ind - 1]))
        cnt_ang_low_freq = np.roll(cnt_ang_low_freq, -head_ind)

        maxima_low_freq_ind = maxima_low_freq_ind - head_ind
        maxima_low_freq_ind[maxima_low_freq_ind <
                            0] += cnt_ang_low_freq.size  # wrap

        tail_ind = tail_ind - head_ind
        if tail_ind < 0:
            tail_ind = tail_ind + contour.shape[0]
        head_ind = 0

    return (head_ind, tail_ind, contour, cnt_chain_code_len,
            cnt_ang_low_freq, maxima_low_freq_ind)
