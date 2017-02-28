# -*- coding: utf-8 -*-
"""
Created on Sun May 24 19:25:04 2015

@author: ajaver
"""
import numpy as np
from .cythonFiles.linearSkeleton_cython import chainCodeLength2Index, circOpposingNearestPoints, \
    getHeadTailRegion, getInterBendSeeds, skeletonize, cleanSkeleton


#% Find points_ind between startI and endI, inclusive.
def betweenPoints(points_ind, startI, endI):
    if startI < endI:
        return (points_ind >= startI) & (points_ind <= endI)
    else:
        return (points_ind >= startI) | (points_ind <= endI)  # wrap around

#% Find points_ind whose index distance from oposite_ind exceeds maxDistI.


def maxDistPoints(points_ind, oposite_ind, maxDistI, contour):
    #% How close are the points?
    points = np.zeros(points_ind.size, dtype=np.bool)
    for i in range(points.size):
        if points_ind[i] > oposite_ind[i]:
            #% The points exceed the threshold.
            if maxDistI <= min(
                    points_ind[i] -
                    oposite_ind[i],
                    oposite_ind[i] +
                    contour.shape[0] -
                    points_ind[i]):
                points[i] = True
        #% The points exceed the threshold.
        elif maxDistI <= min(oposite_ind[i] - points_ind[i], points_ind[i] + contour.shape[0] - oposite_ind[i]):
            points[i] = True
    return points


def getHeadTailSeed(contour, head_ind, tail_ind):
    last_index = contour.shape[0] - 1
    #% Compute the head indices.
    head_side1 = head_ind + 1
    head_side2 = (head_ind - 1) if (head_ind > 0) else (head_ind + last_index)

    #% Compute the tail indices.
    tail_side1 = tail_ind - 1
    tail_side2 = (
        tail_ind +
        1) if (
        tail_ind < last_index) else (
            tail_ind -
        last_index)
    return head_side1, head_side2, tail_side1, tail_side2


def getMidBodySeed(
        contour,
        chain_code_len,
        head_ind,
        tail_ind,
        search_edge_size):
    #% Compute the midbody indices for side 1.
    midbody1_s1 = (chain_code_len[head_ind] + chain_code_len[tail_ind]) / 2
    midbody1_s1 = chainCodeLength2Index(midbody1_s1, chain_code_len)
    midbody1_s2 = circOpposingNearestPoints(
        np.array(
            [midbody1_s1]),
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)[0]

    #% Compute the midbody indices for side 2.
    midbody2_s2 = (chain_code_len[head_ind] +
                   chain_code_len[tail_ind] + chain_code_len[-1]) / 2
    if midbody2_s2 > chain_code_len[-1]:
        midbody2_s2 -= - chain_code_len[-1]

    midbody2_s2 = chainCodeLength2Index(midbody2_s2, chain_code_len)
    midbody2_s1 = circOpposingNearestPoints(
        np.array(
            [midbody2_s2]),
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)[0]

    #% The closest points are the true midbody indices.
    r1 = np.sum((contour[midbody1_s1, :] - contour[midbody1_s2, :])**2)
    r2 = np.sum((contour[midbody2_s1, :] - contour[midbody2_s2, :])**2)
    if (r1 <= r2):
        midbody_side1 = midbody1_s1
        midbody_side2 = midbody1_s2
    else:
        midbody_side1 = midbody2_s1
        midbody_side2 = midbody2_s2

    #% Compute the minimum distance between the midbody indices.
    if midbody_side1 > midbody_side2:
        delta_mid_point = min(
            midbody_side1 -
            midbody_side2,
            midbody_side2 +
            contour.shape[0] -
            midbody_side1)
    else:
        delta_mid_point = min(
            midbody_side2 -
            midbody_side1,
            midbody_side1 +
            contour.shape[0] -
            midbody_side2)

    return midbody_side1, midbody_side2, delta_mid_point


def getBendsSeeds(contour, bend_ind, chain_code_len, head_ind, tail_ind,
                  midbody_tuple, worm_seg_length, search_edge_size):
    # extract midbody limits
    midbody_side1, midbody_side2, delta_mid_point = midbody_tuple

    # compute bends
    head_start, head_end, tail_start, tail_end = \
        getHeadTailRegion(head_ind, tail_ind, chain_code_len, worm_seg_length)

    good = ~(
        betweenPoints(
            bend_ind,
            head_start,
            head_end) & betweenPoints(
            bend_ind,
            tail_start,
            tail_end))
    bend_ind = bend_ind[good]

    #% Compute the bend indices for side 1.
    #% Remove any bend indices too close to the head and/or tail.
    bend1_s1 = bend_ind[(bend_ind >= head_end) & (bend_ind <= tail_start)]
    bend1_s2 = circOpposingNearestPoints(
        bend1_s1,
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)

    #% Remove any bend indices that cross the midline.
    good = ~maxDistPoints(bend1_s1, bend1_s2, delta_mid_point, contour)
    bend1_s1 = bend1_s1[good]
    bend1_s2 = bend1_s2[good]

    #% Minimize the width at the bend.
    bend1_s1 = circOpposingNearestPoints(
        bend1_s2,
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)
    headB1 = betweenPoints(bend1_s1, head_start, head_end)
    tailB1 = betweenPoints(bend1_s1, tail_start, tail_end)
    crossed = maxDistPoints(bend1_s1, bend1_s2, delta_mid_point, contour)
    good = ~(headB1 | tailB1 | crossed)
    bend1_s1 = bend1_s1[good]
    bend1_s2 = bend1_s2[good]

    #% Compute the bend indices for side 2.
    bend2_s2 = bend_ind[(bend_ind >= tail_end) & (bend_ind <= head_start)]
    bend2_s1 = circOpposingNearestPoints(
        bend2_s2,
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)

    #% Remove any bend indices that cross the midline.
    good = ~maxDistPoints(bend2_s2, bend2_s1, delta_mid_point, contour)
    bend2_s2 = bend2_s2[good]
    bend2_s1 = bend2_s1[good]

    #% Minimize the width at the bend.
    bend2_s2 = circOpposingNearestPoints(
        bend2_s1,
        contour,
        head_ind,
        tail_ind,
        search_edge_size,
        chain_code_len)

    headB2 = betweenPoints(bend2_s2, head_start, head_end)
    tailB2 = betweenPoints(bend2_s2, tail_start, tail_end)
    crossed = maxDistPoints(bend2_s2, bend2_s1, delta_mid_point, contour)
    good = ~(headB2 | tailB2 | crossed)
    bend2_s2 = bend2_s2[good]
    bend2_s1 = bend2_s1[good]

    # the skeleton seem to be calculated better if one consider segments from the bending regions
    #% Combine the bend indices from opposing sides and order everything so
    #% that the skeleton segments can never cross.
    bend_side1 = np.sort(np.hstack([midbody_side1, bend1_s1, bend2_s1]))
    midbody_ind = np.where(bend_side1 == midbody_side1)[0][0]

    bend_side2 = np.sort(np.hstack([midbody_side2, bend2_s2, bend1_s2]))[::-1]
    bend_side2 = bend_side2[
        (bend_side2 <= head_ind) | (
            bend_side2 >= tail_ind)]

    return bend_side1, bend_side2, midbody_ind


def getLinearSkeleton(
        contour,
        head_ind,
        tail_ind,
        midbody_ind,
        bend_side1,
        bend_side2,
        interbend_side1,
        interbend_side2):

    head_side1, head_side2, tail_side1, tail_side2 = \
        getHeadTailSeed(contour, head_ind, tail_ind)

    #% Skeletonize the worm from its midbody to its head.
    skeleton_mid_head = np.zeros((contour.shape[0], 2))
    widths_mid_head = np.zeros((contour.shape[0]))
    i = midbody_ind
    j = 0
    while i > 0:
        #% Skeletonize the segment from the bend to the interbend.
        segment, cnt_widths = skeletonize(bend_side1[i], interbend_side1[i - 1], -1,
                                          bend_side2[i], interbend_side2[i - 1], 1, contour, contour)
        next_j = j + segment.shape[0] - 1

        skeleton_mid_head[j:next_j + 1, :] = segment
        widths_mid_head[j:next_j + 1] = cnt_widths
        j = next_j + 1
        i = i - 1

        #% Skeletonize the segment from the next bend back to the interbend.
        [segment, cnt_widths] = skeletonize(bend_side1[i], interbend_side1[i], 1, bend_side2[
                                            i], interbend_side2[i], -1, contour, contour)

        next_j = j + segment.shape[0] - 1
        skeleton_mid_head[j:next_j + 1, :] = segment[::-1, :]
        widths_mid_head[j:next_j + 1] = cnt_widths[::-1]
        j = next_j + 1

    #% Skeletonize the segment from the last bend to the head.
    [segment, cnt_widths] = skeletonize(bend_side1[i], head_side1, -1, bend_side2[i],
                                        head_side2, 1, contour, contour)
    next_j = j + segment.shape[0] - 1
    skeleton_mid_head[j:next_j + 1, :] = segment
    widths_mid_head[j:next_j + 1] = cnt_widths

    #% Clean up.
    skeleton_mid_head = skeleton_mid_head[:next_j, :]
    widths_mid_head = widths_mid_head[:next_j]

    #% Skeletonize the worm from its midbody to its tail.
    skeleton_mid_tail = np.zeros((contour.shape[0], 2))
    widths_mid_tail = np.zeros(contour.shape[0])
    i = midbody_ind
    j = 0
    while i < bend_side1.size - 1:
        #% Skeletonize the segment from the bend to the interbend.
        [segment, cnt_widths] = skeletonize(bend_side1[i], interbend_side1[i], 1, bend_side2[
                                            i], interbend_side2[i], -1, contour, contour)
        next_j = j + segment.shape[0] - 1
        skeleton_mid_tail[j:next_j + 1, :] = segment
        widths_mid_tail[j:next_j + 1] = cnt_widths

        j = next_j + 1
        i = i + 1

        [segment, cnt_widths] = skeletonize(bend_side1[i], interbend_side1[i - 1], -1,
                                            bend_side2[i], interbend_side2[i - 1], 1, contour, contour)
        next_j = j + segment.shape[0] - 1
        skeleton_mid_tail[j:next_j + 1, :] = segment[::-1, :]
        widths_mid_tail[j:next_j + 1] = cnt_widths[::-1]
        j = next_j + 1

    [segment, cnt_widths] = skeletonize(bend_side1[i], tail_side1, 1, bend_side2[
                                        i], tail_side2, -1, contour, contour)

    next_j = j + segment.shape[0] - 1
    skeleton_mid_tail[j:next_j + 1, :] = segment
    widths_mid_tail[j:next_j + 1] = cnt_widths

    #% Clean up.
    skeleton_mid_tail = skeleton_mid_tail[:next_j, :]
    widths_mid_tail = widths_mid_tail[:next_j]

    #% Reconstruct the skeleton.
    skeleton = np.vstack([contour[head_ind, :], skeleton_mid_head[
                         ::-1, :], skeleton_mid_tail, contour[tail_ind, :]])
    cnt_widths = np.hstack([0, widths_mid_head[::-1], widths_mid_tail, 0])

    return skeleton, cnt_widths


def linearSkeleton(
        head_ind,
        tail_ind,
        minima_low_freq,
        minima_low_freq_ind,
        maxima_low_freq,
        maxima_low_freq_ind,
        contour,
        worm_seg_length,
        chain_code_len):
    '''%LINEARSKELETON Skeletonize a linear (non-looped) worm. The worm is
    %skeletonized by splitting its contour, from head to tail, into short
    %segments. These short segments are bounded by matching pairs of minimal
    %angles (< -20 degrees) and their nearest points on the opposite side of
    %the worm's contour. We then walk along the opposing sides of these short
    %segments and mark the midline as our skeleton. The final step is cleaning
    %up this skeleton to remove overlapping points and interpolate missing ones.
    %
    %   [SKELETON CWIDTHS] = LINEARSKELETON(head_ind, tail_ind, CONTOUR, worm_seg_length)
    %
    %   [SKELETON CWIDTHS] = LINEARSKELETON(head_ind, tail_ind, CONTOUR, worm_seg_length,
    %                                       chain_code_len)
    %
    %   Inputs:
    %       head_ind            - the head's contour index
    %       tail_ind            - the tail's contour index
    %       minima_low_freq             - the local minimal peaks
    %       minima_low_freq_ind             - the local minimal peaks' contour indices
    %       maxima_low_freq             - the local maximal peaks
    %       maxima_low_freq_ind             - the local maximal peaks' contour indices
    %       contour          - the worm's contour
    %       worm_seg_length      - the size (in contour length) of a worm segment.
    %                          Note 1: the worm is roughly divided into 24
    %                          segments of musculature (i.e., hinges that
    %                          represent degrees of freedom) on each side.
    %                          Therefore, 48 segments around a 2-D contour.
    %                          Note 2: "In C. elegans the 95 rhomboid-shaped
    %                          body wall muscle cells are arranged as staggered
    %                          pairs in four longitudinal bundles located in
    %                          four quadrants. Three of these bundles (DL, DR,
    %                          VR) contain 24 cells each, whereas VL bundle
    %                          contains 23 cells." - www.wormatlas.org
    %       chain_code_len - the chain-code length at each point;
    %                          if empty, the array indices are used instead
    %
    %   Output:
    %       skeleton - the worm's skeleton
    %       cnt_widths  - the worm contour's width at each skeleton point
    %
    % See also SEGWORM, CIRCCOMPUTEchain_code_len
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.
    '''
    assert head_ind <= tail_ind

    '''% Compute the edge size to use in searching for opposing contour points.
    % We use 1/4 of a contour side to be safe.
    % Note: worm curvature can significantly distort the length of a contour
    % side and, consequently, the locations of identical spots on opposing
    % sides of the contour. Therefore, in addition to using scaled locations,
    % we also use a large search window to ensure we correctly identify
    % opposing contour locations.
    '''
    search_edge_size = chain_code_len[-1] / 8.

    '''% Compute the segment size to use in excluding the head and tail angles.
    % Due to bends and obscure boundaries at the head and tail, it is difficult
    % to match opposing contour points near these locations.The worm's head and
    % tail occupy, approximately, 4 muscle segments each, on the skeleton and
    % either side of the contour.
    % Note: "The first two muscle cells in the two ventral and two dorsal rows
    % [of the head] are smaller than their lateral counterparts, giving a
    % stagger to the packing of the two rows of cells in a quadrant. The first
    % four muscles in each quadrant are innervated exclusively by motoneurons
    % in the nerve ring. The second block of four muscles is dually innervated,
    % receiving synaptic input from motoneurons in the nerve ring and the
    % anterior ventral cord. The rest of the muscles in the body are
    % exclusively innervated by NMJs in the dorsal and ventral cords." - The
    % Structure of the Nervous System of the Nematode C. elegans, on
    % www.wormatlas.org'''

    #% Compute the head, tail, midbody, and bends for both sides.
    #% Skeletonization occurs piecemeal, stitching together segments starting at
    #% the midbody, from bend to bend, and ending with the head/tail.
    #% Side1 always goes from head to tail in positive, index increments.
    #% Side2 always goes from head to tail in negative, index increments.

    midbody_tuple = getMidBodySeed(
        contour,
        chain_code_len,
        head_ind,
        tail_ind,
        search_edge_size)

    #% Find the large minimal bends away from the head and tail.
    bend_ind = np.append(
        minima_low_freq_ind[
            minima_low_freq < -20],
        maxima_low_freq_ind[
            maxima_low_freq > 20])
    bend_side1, bend_side2, midbody_ind = getBendsSeeds(
        contour, bend_ind, chain_code_len, head_ind, tail_ind, midbody_tuple, worm_seg_length, search_edge_size)

    # get inter-bend seeds
    interbend_side1, interbend_side2 = getInterBendSeeds(
        bend_side1, bend_side2, contour, chain_code_len)

    # get skeleton and contour cnt_widths
    skeleton, cnt_widths = getLinearSkeleton(
        contour, head_ind, tail_ind, midbody_ind, bend_side1, bend_side2, interbend_side1, interbend_side2)
    assert (skeleton.size > 0) and (skeleton.ndim == 2)
    #assert np.all(skeleton[0]==contour[head_ind])
    #assert np.all(skeleton[-1]==contour[tail_ind])

    #% Clean up the rough skeleton.
    #skeleton, cnt_widths = cleanSkeleton(skeleton, cnt_widths, worm_seg_length);
    #assert np.all(skeleton[0]==contour[head_ind])
    #assert np.all(skeleton[-1]==contour[tail_ind])

    return skeleton, cnt_widths
