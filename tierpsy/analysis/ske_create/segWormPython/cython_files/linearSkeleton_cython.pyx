# -*- coding: utf-8 -*-
# cython: profile=False
# cython: boundscheck=True
# cython: wraparound=True
# cython: nonecheck=True
"""
Created on Sun May 24 19:42:56 2015
@author: ajaver
"""

import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport round as c_round;
from libc.math cimport sqrt, fabs, floor, ceil, fmin, fmax


cdef inline double absDiff(double a, double b): 
    return a-b if a>b else b-a

#for some weird reason libc.math does not have an integer max and min functions (the python ones are slow)
cdef int int_max(int a, int b):
    return a if a>b else b;
cdef int int_min(int a, int b):
    return a if a<b else b;
    
def chainCodeLength2Index(double length, np.ndarray[np.float64_t, ndim=1] chain_code_len):
    '''%CHAINCODELENGTH2INDEX Translate a length into an index. The index
    %   represents the numerically-closest element to the desired length in
    %   an ascending array of chain code lengths.
    %
    %   INDICES = CHAINCODELENGTH2INDEX(LENGTHS, chain_code_len)
    %
    %   Inputs:
    %       lengths          - the lengths to translate into indices
    %       chain_code_len - an ascending array of chain code lengths
    %                          Note: the chain code lengths must increase at
    %                          every successive index
    %
    %   Output:
    %       indices - the indices for the elements closest to the desired
    %                 lengths
    %
    % See also COMPUTEchain_code_len, CIRCCOMPUTEchain_code_len
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.
    '''
    cdef int last_index_chain = chain_code_len.size-1;
    cdef int index;
    cdef double dist_j, dist_next_j;
    cdef int j;
    
    #//% Is the length too small?
    if(length < chain_code_len[0]):
        #//% Find the closest index.
        if (length / chain_code_len[0] < 0.5):
            index = last_index_chain;
        else:
            index = 0;
    #//% Is the length too big?
    else:
        if (length > chain_code_len[last_index_chain]):
            #//% Find the closest index.
            if ((length - chain_code_len[last_index_chain]) / chain_code_len[0] < 0.5):
                index = last_index_chain;
            else:
                index = 0;
        #//% Find the closest index.
        else:
            #//% Try jumping to just before the requested length.
            #//% Note: most chain-code lengths advance by at most sqrt(2) at each
            #//% index. But I don't trust IEEE division so I use 1.5 instead.
            j = <int>c_round(length / 1.5);
            #//% Did we jump past the requested length?
            if (j > last_index_chain or length < chain_code_len[j]):
                j = 0;
            
            #//% find the closest index.
            dist_j = absDiff(length, chain_code_len[j]); #//important use fabs, abs will cast the value to integer
            while (j < last_index_chain):
                #//% Is this index closer than the next one?
                #//% Note: overlapping points have equal distances. Therefore, if
                #//% the distances are equal, we advance.
                dist_next_j = absDiff(length, chain_code_len[j + 1]);
                if (dist_j < dist_next_j):
                    break;
                
                #//% Advance.
                dist_j = dist_next_j;
                j = j + 1;
            #//% Record the closest index.
            index = j;
    return index;


cdef inline int plusCircIndex(int ind, int last_index):
    return ind + 1 if (ind < last_index) else ind - last_index;
    
cdef inline int minusCircIndex(int ind, int last_index):
    return ind - 1 if (ind > 0) else ind + last_index;

def circOpposingPoints(np.ndarray[np.int_t, ndim=1] points_ind, \
int start_ind, int end_ind, int vec_last_index, np.ndarray[np.float64_t, ndim=1] chain_code_len):
    '''%CIRCOPPOSINGPOINTS Find the equivalent point indices on the opposing side
    %   of a circular vector.
    %
    %   points_ind = CIRCOPPOSINGPOINTS(points_ind, start_ind, end_ind, VSIZE)
    %
    %   points_ind = CIRCOPPOSINGPOINTS(points_ind, start_ind, end_ind, VSIZE,
    %                                chain_code_len)
    %
    %   Inputs:
    %       points_ind          - the point indices to find on the opposing side
    %       start_ind           - the index in the vector where the split, between
    %                          opposing sides, starts
    %       end_ind             - the index in the vector where the split, between
    %                          opposing sides, ends
    %       vec_last_index          - the vector last index
    %       chain_code_len - the chain-code length at each point;
    %                          if empty, the array indices are used instead
    %
    %   Output:
    %       points_ind_out - the equivalent point indices on the opposing side
    %
    % See also CIRCCOMPUTECHAINCODELENGTHS
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software; 
    % you must reproduce all copyright notices and other proprietary 
    % notices on any copies of the Software.'''

    cdef int start_ind1, start_ind2, end_ind1, end_ind2
    cdef float side1_size, side2_size, scale1to2, scale2to1
    cdef int ii, cur_ind
    cdef float delta_dist, point_dist
    cdef np.ndarray[np.int_t, ndim=1] points_ind_out = points_ind.copy()
    
    
    #% Re-order the start and end to make life simple. 
    cdef int tmp
    if start_ind > end_ind:
        tmp = start_ind;
        start_ind = end_ind;
        end_ind = tmp;

    #% Separate the points onto sides.
    #% Note: ignore start and end points, they stay the same.
    #% Side1 always goes from start to end in positive, index increments.
    #% Side2 always goes from start to end in negative, index increments.
    
    #% Compute the size of side 1.
    start_ind1 = start_ind + 1;
    end_ind1 = end_ind - 1;
    side1_size = chain_code_len[end_ind1] - chain_code_len[start_ind1];
    
    #% Compute the size of side 2.
    start_ind2 = minusCircIndex(start_ind, vec_last_index)
    end_ind2 = plusCircIndex(end_ind, vec_last_index)
    if start_ind2 < end_ind2:
        side2_size = chain_code_len[start_ind2] + \
            chain_code_len[vec_last_index] - chain_code_len[end_ind2];
    else: #% one of the ends wrapped
        side2_size = chain_code_len[start_ind2] - chain_code_len[end_ind2];
    
    #% Compute the scale between sides.
    scale1to2 = side2_size / side1_size;
    scale2to1 = side1_size / side2_size;
    
    
    for ii in range(points_ind.shape[0]):
        cur_ind = points_ind[ii]
        
        
        #% Find the distance of the side 1 points from the start, scale them for
        #% side 2, then find the equivalent point, at the scaled distance
        #% from the start, on side 2.
        if (cur_ind > start_ind) and (cur_ind < end_ind):
            point_dist = chain_code_len[start_ind2] - \
        (chain_code_len[cur_ind] - chain_code_len[start_ind1]) * scale1to2;
    
        #% Find the distance of the side 2 points from the start, scale them for
        #% side 1, then find the equivalent point, at the scaled distance
        #% from the start, on side 1.
        elif (cur_ind < start_ind) or (cur_ind > end_ind):
            delta_dist = chain_code_len[start_ind2] - chain_code_len[cur_ind];
            if points_ind[ii] > start_ind2:
                delta_dist += chain_code_len[vec_last_index];
            point_dist = chain_code_len[start_ind1] + delta_dist * scale2to1;
        
        else:
            continue
    
        #% Correct any wrapped points.
        if point_dist < 0:
            point_dist += chain_code_len[vec_last_index]
        elif point_dist > chain_code_len[vec_last_index]:
            point_dist -= chain_code_len[vec_last_index]
        
        #% Translate the chain-code lengths to indices.
        points_ind_out[ii] = chainCodeLength2Index(point_dist, chain_code_len);

    return points_ind_out

cdef tuple min_distance(np.ndarray[np.float_t, ndim=2] x, int curr_ind, int range_min, int range_max):
    cdef double dx, dy, r, min_r
    cdef int j, near_ind
    
    min_r = 2147483647 #max 32 integer. initialization
    for j in range(range_min, range_max+1):
        dx = x[curr_ind,0] - x[j,0];
        dy = x[curr_ind,1] - x[j,1];
        r = dx*dx + dy*dy
        if r < min_r:
            min_r = r;
            near_ind = j;
    return min_r, near_ind

def circNearestPoints(np.ndarray[np.int_t, ndim=1] points_ind, \
                            np.ndarray[np.int_t, ndim=1] min_ind, \
                            np.ndarray[np.int_t, ndim=1] max_ind, \
                            np.ndarray[np.float64_t, ndim=2] x):
    '''%CIRCNEARESTPOINTS For each point, find the nearest corresponding point
    %   within an interval of circularly-connected search points.
    %
    %   NEARI = CIRCNEARESTPOINTS(POINTS, MINI, MAXI, X)
    %
    %   Inputs:
    %       points - the point index from which the distance is measured
    %       minI   - the minimum indices of the intervals
    %       maxI   - the maximum indices of the intervals
    %       x      - the circularly-connected, point coordinates on which the
    %                search intervals lie
    %
    %   Output:
    %       nearI - the indices of the nearest points
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software; 
    % you must reproduce all copyright notices and other proprietary 
    % notices on any copies of the Software.
    '''
    assert len(points_ind) == len(min_ind) == len(max_ind)
    cdef int total_points = points_ind.shape[0]
    cdef int last_index = total_points-1
    #% Pre-allocate memory.
    cdef np.ndarray[np.int_t, ndim=1] near_ind = np.zeros(total_points, dtype=np.int);
    cdef int i, near_ind1, near_ind2
    cdef float mag1, mag2
    
    #% Search for the nearest points.
    for i in range(total_points): 
        #% The interval is continuous.
        if min_ind[i] <= max_ind[i]:
            mag1, near_ind1 = min_distance(x, points_ind[i], min_ind[i], max_ind[i])
            near_ind[i] = near_ind1
        
        #% The interval wraps.
        else:
            mag1, near_ind1 = min_distance(x, points_ind[i], min_ind[i], last_index)
            mag2, near_ind2 = min_distance(x, points_ind[i], 0, max_ind[i])
            
            #% Which point is nearest?
            near_ind[i] = near_ind1 if mag1 <= mag2 else near_ind2;
            
    return near_ind

cdef int wrapOppositeRegion(np.ndarray[np.float64_t, ndim=1] lenghts, \
double cur_len, int start_ind, int end_ind, int last_index, bint isMax, bint isSide1, bint isWrap):
    if isSide1:
        if (cur_len < lenghts[start_ind]):
            return start_ind;
        elif (cur_len > lenghts[end_ind]):
            return end_ind;
    else:
        if isWrap:
            if ((cur_len > lenghts[start_ind]) or (cur_len < lenghts[end_ind])):
                return start_ind if isMax else end_ind;
        else:
            if (cur_len > lenghts[start_ind]) and (cur_len < lenghts[end_ind]):
                return start_ind if isMax else end_ind;
    
    if cur_len < lenghts[0]:
        cur_len += lenghts[last_index];
        
    elif cur_len > lenghts[last_index]:
        cur_len -= lenghts[last_index];
    
    return chainCodeLength2Index(cur_len, lenghts);

def circOpposingNearestPoints(np.ndarray[np.int_t, ndim=1] points_ind, np.ndarray[np.float64_t, ndim=2] x, \
int start_ind, int end_ind, double search_len, np.ndarray[np.float64_t, ndim=1] chain_code_len):
    '''%CIRCOPPOSINGNEARESTPOINTS Find the nearest equivalent point indices on the
    %   opposing side (within a search window) of a circular vector.
    %
    %   points_ind = CIRCOPPOSINGNEARESTPOINTS(points_ind, X, start_ind, end_ind,
    %                                       search_len)
    %
    %   points_ind = CIRCOPPOSINGNERAESTPOINTS(points_ind, X, start_ind, end_ind,
    %                                       search_len, chain_code_len)
    %
    %   Inputs:
    %       points_ind          - the point indices to find on the opposing side
    %       x                - the circularly connected vector on which the
    %                          points lie
    %       start_ind           - the index in the vector where the split, between
    %                          opposing sides, starts
    %       end_ind             - the index in the vector where the split, between
    %                          opposing sides, ends
    %       search_len     - the search length, on either side of a directly
    %                          opposing point, to search for the nearest point
    %       chain_code_len - the chain-code length at each point;
    %                          if empty, the array indices are used instead
    %
    %   Output:
    %       points_ind - the equivalent point indices on the opposing side
    %
    % See also CIRCOPPOSINGPOINTS, CIRCNEARESTPOINTS, CIRCCOMPUTEchain_code_len
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software; 
    % you must reproduce all copyright notices and other proprietary 
    % notices on any copies of the Software.
    '''
    
    
    cdef int x_last_index = x.shape[0]-1
    cdef int last_chain_index = chain_code_len.size-1
    cdef int start1, start2, end1, end2
    cdef int ii, cur_ind
    cdef double min_opposite, max_opposite
    cdef np.ndarray[np.int_t, ndim=1] opposite_ind
    cdef np.ndarray[np.int_t, ndim=1] points_ind_out = points_ind.copy()
    
    #flags (just to make it easier to read)
    cdef bint SIDE1 = 1;
    cdef bint SIDE2 = 0;
    cdef bint ISMAX = 1;
    cdef bint ISMIN = 0;
    
    cdef bint is2Wrap
    
    
    #% Re-order the start and end to make life simple. 
    cdef int tmp
    if start_ind > end_ind:
        tmp = start_ind;
        start_ind = end_ind;
        end_ind = tmp;

    #% The points are degenerate.
    if ((end_ind - start_ind) < 2) or ((start_ind + x_last_index - end_ind) < 2):
        return  np.zeros([], dtype=x.dtype);

    #% Separate the points onto sides.
    #% Note: ignore start and end points, they stay the same.
    #% Side1 always goes from start to end in positive, index increments.
    
    #% Compute the start indices.
    #% Note: we checked for degeneracy; therefore, only one index can wrap.
    is2Wrap = 0;
    start1 = start_ind + 1;
    start2 = start_ind - 1;
    if start2 < 0:
        start2 = start2 + x_last_index;
        is2Wrap = 1;
    
    #% Compute the end indices.
    end1 = end_ind - 1;
    end2 = end_ind + 1;
    if end2 >= x_last_index:
        end2 = end2 - x_last_index;
        is2Wrap = 1;

    #% Compute the opposing points.
    opposite_ind = circOpposingPoints(points_ind_out, start_ind, end_ind, x_last_index, chain_code_len);
    
    #% Side2 always goes from start to end in negative, index increments.
    side12 = (opposite_ind != start_ind) & (opposite_ind != end_ind);
    opposite_ind = opposite_ind[side12];
    cdef np.ndarray[np.int_t, ndim=1] minOpoints_ind = np.zeros_like(opposite_ind)
    cdef np.ndarray[np.int_t, ndim=1] maxOpoints_ind = np.zeros_like(opposite_ind)
    
    
    #% Compute the minimum search points on side 2 (for the search intervals
    #% opposite side 1).
    for ii in range(opposite_ind.size):
        cur_ind = opposite_ind[ii]
        min_opposite = chain_code_len[cur_ind] - search_len;
        max_opposite = chain_code_len[cur_ind] + search_len;
        
        #side1
        if (cur_ind > start_ind) and (cur_ind < end_ind):
            minOpoints_ind[ii] = wrapOppositeRegion(chain_code_len, min_opposite, start1, end1, last_chain_index, ISMIN, SIDE1, is2Wrap)
            maxOpoints_ind[ii] = wrapOppositeRegion(chain_code_len, max_opposite, start1, end1, last_chain_index, ISMAX, SIDE1, is2Wrap)
        elif (cur_ind < start_ind) or (cur_ind > end_ind):
            minOpoints_ind[ii] = wrapOppositeRegion(chain_code_len, min_opposite, start2, end2, last_chain_index, ISMIN, SIDE2, is2Wrap)
            maxOpoints_ind[ii] = wrapOppositeRegion(chain_code_len, max_opposite, start2, end2, last_chain_index, ISMAX, SIDE2, is2Wrap)
    
    #% Search for the nearest points.
    points_ind_out[side12] = circNearestPoints(points_ind[side12], minOpoints_ind, maxOpoints_ind, x);
    return points_ind_out


cdef double circAddition(double A,double B, double max_size):
    C = A+B;
    if C > max_size:
        C -= max_size;
    return C

cdef double circSubtraction(double A, double B, double min_size, double max_size):
    C = A-B;
    if C < min_size:
        C += max_size;
    return C

def getHeadTailRegion(int head_ind, int tail_ind, np.ndarray[np.float64_t, ndim=1] chain_code_len, double worm_seg_length):
    cdef double head_tail_seg = worm_seg_length * 4;
    cdef int head_start, head_end, tail_start, tail_end
    cdef double tmp
    
    cdef double last_chain_len = chain_code_len[chain_code_len.size-1]
    cdef double first_chain_len = chain_code_len[0]
    
    #% Find small head boundaries.
    tmp = circSubtraction(chain_code_len[head_ind], head_tail_seg, first_chain_len, last_chain_len);
    head_start = chainCodeLength2Index(tmp, chain_code_len);
    
    tmp = circAddition(chain_code_len[head_ind], head_tail_seg, last_chain_len);
    head_end = chainCodeLength2Index(tmp, chain_code_len);
    
    #% Find small tail boundaries.
    tmp = circSubtraction(chain_code_len[tail_ind], head_tail_seg, first_chain_len, last_chain_len);
    tail_start = chainCodeLength2Index(tmp, chain_code_len);
    
    tmp = circAddition(chain_code_len[tail_ind], head_tail_seg, last_chain_len);
    tail_end = chainCodeLength2Index(tmp, chain_code_len);
    
    return head_start, head_end, tail_start, tail_end

def getInterBendSeeds(np.ndarray[np.int_t, ndim=1] bend_side1, np.ndarray[np.int_t, ndim=1] bend_side2, \
np.ndarray[np.float64_t, ndim=2] contour, np.ndarray[np.float64_t, ndim=1] chain_code_len): 
    cdef int total_interbends = bend_side1.size-1
    #% Compute the inter-bend indices.
    cdef np.ndarray[np.int_t, ndim=1] interbend_side1 = np.zeros((total_interbends), dtype = np.int)
    cdef np.ndarray[np.int_t, ndim=1] interbend_side2 = np.zeros((total_interbends), dtype = np.int)
    cdef int i
    for i in range(total_interbends):
        interbend_side1[i] = chainCodeLength2Index((chain_code_len[bend_side1[i]] + \
        chain_code_len[bend_side1[i+1]]) / 2., chain_code_len);
    interbend_side2 = circNearestPoints(interbend_side1, bend_side2[1:], bend_side2[:total_interbends], contour);
    return interbend_side1, interbend_side2
    
cdef double getDistance(double x1, double x2, double y1, double y2):
    cdef double d1, d2
    d1 = x1-x2;
    d2 = y1-y2;
    return sqrt(d1*d1 + d2*d2)
    
cdef tuple getWrappedIndex(int start_side, int end_side, double inc_side, int cnt_size):
    if (start_side <= end_side):
        #//% We are going forward.
        if (inc_side > 0):
            return ((end_side - start_side + 1) / inc_side, -1, -1)
        #//% We are wrapping backward.
        else:
            return ((start_side + cnt_size - end_side + 1) / (-1*inc_side), cnt_size-1, 0)
    #//% The first starting index is after the ending one.
    else:
        #//% We are going backward.
        if (inc_side < 0):
            return ((start_side - end_side + 1) / (-1*inc_side), -1, -1)
        #//% We are wrapping forward.
        else:
            return ((cnt_size - start_side + 1 + end_side) / inc_side, 0, cnt_size-1)
    
def skeletonize(int start_side1, int end_side1, int inc_side1, \
int start_side2, int end_side2, int inc_side2, \
np.ndarray[np.float_t, ndim=2] cnt_side1, np.ndarray[np.float_t, ndim=2] cnt_side2):
    '''%SKELETONIZE Skeletonize takes the 2 pairs of start and end points on a
    %contour(s), then traces the skeleton between them using the specified
    %increments.
    %
    %   [SKELETON] = SKELETONIZE(start_side1, end_side1, inc_side1, start_side2, end_side2, inc_side2, cnt_side1, cnt_side2)
    %
    %   Inputs:
    %       start_side1       - The starting index for the first contour segment.
    %       end_side1       - The ending index for the first contour segment.
    %       inc_side1       - The increment to walk along the first contour segment.
    %                  Note: a negative increment means walk backwards.
    %                  Contours are circular, hitting an edge wraps around.
    %       start_side2       - The starting index for the second contour segment.
    %       end_side2       - The ending index for the second contour segment.
    %       inc_side2       - The increment to walk along the second contour segment.
    %                  Note: a negative increment means walk backwards.
    %                  Contours are circular, hitting an edge wraps around.
    %       cnt_side1       - The contour for the first segment.
    %       cnt_side2       - The contour for the second segment.
    %
    %   Output:
    %       skeleton - the skeleton traced between the 2 sets of contour points.
    %       cnt_widths  - the widths between the 2 sets of contour points.
    %                  Note: there are no widths when cutting across.
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.'''

    cdef int cnt1_size = cnt_side1.shape[0]
    cdef int cnt2_size = cnt_side1.shape[1]
    
    cdef int wrap_end1, wrap_start1, wrap_end2, wrap_start2;
    cdef double size1, size2;
    
    #//% The first starting index is before the ending one.
    size1, wrap_start1, wrap_end1 = getWrappedIndex(start_side1, end_side1, inc_side1, cnt1_size)
    
    #//% The second starting index is before the ending one.
    size2, wrap_start2, wrap_end2 = getWrappedIndex(start_side2, end_side2, inc_side2, cnt2_size)
    
    #//% Trace the midline between the contour segments.
    #//% Note: the next few pages of code represent multiple, nearly identical
    #//% algorithms. The reason they are inlined as separate instances is to
    #//% mildly speed up one of the tightest loops in our program.
    
    #// % pre-allocate memory
    cdef int number_points = 2*int(floor(size1 + size2)); #preallocate memory
    cdef np.ndarray[np.float_t, ndim=2] skeleton = np.zeros((number_points,2))
    cdef np.ndarray[np.float_t, ndim=1] cnt_widths = np.zeros((number_points))
    
    cdef int j1 = start_side1;
    cdef int j2 = start_side2;
    cdef int next_j1, next_j2;
    cdef double d1, d2, d12, dnj12_0, dnj12_1, prev_width;
    
    
    if (j1 == wrap_end1): #//% wrap
        j1 = wrap_start1;
    
    if (j2 == wrap_end2): #//% wrap
        j2 = wrap_start2;
    
    #//% Initialize the skeleton and contour widths.
    skeleton[0,0] = c_round((cnt_side1[j1,0] + cnt_side2[j2,0])/ 2);
    skeleton[0,1] = c_round((cnt_side1[j1,1] + cnt_side2[j2,1])/ 2);
    cnt_widths[0] = getDistance(cnt_side1[j1,0], cnt_side2[j2,0], cnt_side1[j1,1], cnt_side2[j2,1]);
    
    cdef int ske_ind = 1;
    #//% Skeletonize the contour segments and measure the width.
    while ((j1 != end_side1) and (j2 != end_side2)):
        #//% Compute the widths.
        next_j1 = j1 + inc_side1;
        if (next_j1 == wrap_end1): #//% wrap
            next_j1 = wrap_start1;
        
        next_j2 = j2 + inc_side2;
        if (next_j2 == wrap_end2): #//% wrap
            next_j2 = wrap_start2;
        
        d1 = getDistance(cnt_side1[next_j1,0], cnt_side2[j2,0], cnt_side1[next_j1,1], cnt_side2[j2,1])
        d2 = getDistance(cnt_side1[j1,0], cnt_side2[next_j2,0], cnt_side1[j1,1], cnt_side2[next_j2,1])
        d12 = getDistance(cnt_side1[next_j1,0], cnt_side2[next_j2,0], cnt_side1[next_j1,1], cnt_side2[next_j2,1])
        
        dnj12_0 = (cnt_side1[next_j1,0]-cnt_side1[j1,0])*(cnt_side1[next_j2,0]-cnt_side1[j2,0]);
        dnj12_1 = (cnt_side1[next_j1,1]-cnt_side1[j1,1])*(cnt_side1[next_j2,1]-cnt_side1[j2,1]);
        
        #//% Advance along both contours.
        if ((d12 <= d1 and d12 <= d2) or d1 == d2):
            j1 = next_j1;
            j2 = next_j2;
            cnt_widths[ske_ind] = d12;
        #//% The contours go in similar directions. Follow the smallest width.
        else:
            if ((dnj12_0> -1) and (dnj12_1> -1)):
                #//% Advance along the the first contour.
                if (d1 <= d2):
                    j1 = next_j1;
                    cnt_widths[ske_ind] = d1;
                #//% Advance along the the second contour.
                else:
                    j2 = next_j2;
                    cnt_widths[ske_ind] = d2;
            
            #//% The contours go in opposite directions.
            #//% Follow decreasing widths or walk along both contours.
            #//% In other words, catch up both contours, then walk along both.
            #//% Note: this step negotiates hairpin turns and bulges.
            else:
                #//% Advance along both contours.
                prev_width = cnt_widths[ske_ind - 1];
                if ((d12 <= d1 and d12 <= d2) or d1 == d2 or (d1 > prev_width and d2 > prev_width )):
                    j1 = next_j1;
                    j2 = next_j2;
                    cnt_widths[ske_ind] = d12;
                #//% Advance along the the first contour.
                else:
                    if (d1 < d2):
                        j1 = next_j1;
                        cnt_widths[ske_ind] = d1;
                    #//% Advance along the the second contour.
                    else:
                        j2 = next_j2;
                        cnt_widths[ske_ind] = d2;

        #//% Compute the skeleton.
        skeleton[ske_ind, 0] = c_round((cnt_side1[j1, 0] + cnt_side2[j2, 0]) / 2);
        skeleton[ske_ind, 1] = c_round((cnt_side1[j1, 1] + cnt_side2[j2, 1]) / 2);
        ske_ind +=1;
            
    #//% Add the last point.
    if (j1 != end_side1) or (j2 != end_side2):
        skeleton[ske_ind, 0] = c_round((cnt_side1[end_side1, 0] + cnt_side2[end_side2, 0]) / 2);
        skeleton[ske_ind, 1] = c_round((cnt_side1[end_side1, 1] + cnt_side2[end_side2, 1]) / 2);
        cnt_widths[ske_ind] = getDistance(cnt_side1[end_side1,0], cnt_side2[end_side2,0], cnt_side1[end_side1,1], cnt_side2[end_side2,1])
        ske_ind +=1;
    
    skeleton = skeleton[:ske_ind,:];
    cnt_widths = cnt_widths[:ske_ind]
    
    return (skeleton, cnt_widths)



    
def cleanSkeleton(np.ndarray[np.float_t, ndim=2] skeleton, np.ndarray[np.float_t, ndim=1] widths, double worm_seg_size):
    ''' * %CLEANSKELETON Clean an 8-connected skeleton by removing any overlap and
     * %interpolating any missing points.
     * %
     * %   [CSKELETON] = CLEANSKELETON(SKELETON)
     * %
     * %   Note: the worm's skeleton is still rough. Therefore, index lengths, as
     * %         opposed to chain-code lengths, are used as the distance metric
     * %         over the worm's skeleton.
     * %
     * %   Input:
     * %       skeleton    - the 8-connected skeleton to clean
     * %       widths      - the worm's contour widths at each skeleton point
     * %       worm_seg_size - the size (in contour points) of a worm segment.
     * %                     Note: the worm is roughly divided into 24 segments
     * %                     of musculature (i.e., hinges that represent degrees
     * %                     of freedom) on each side. Therefore, 48 segments
     * %                     around a 2-D contour.
     * %                     Note 2: "In C. elegans the 95 rhomboid-shaped body
     * %                     wall muscle cells are arranged as staggered pairs in
     * %                     four longitudinal bundles located in four quadrants.
     * %                     Three of these bundles (DL, DR, VR) contain 24 cells
     * %                     each, whereas VL bundle contains 23 cells." -
     * %                     www.wormatlas.org
     * %
     * %   Output:
     * %       cSkeleton - the cleaned skeleton (no overlap & no missing points)
     * %       cWidths   - the cleaned contour widths at each skeleton point
     * %
     * %
     * % © Medical Research Council 2012
     * % You will not remove any copyright or other notices from the Software;
     * % you must reproduce all copyright notices and other proprietary
     * % notices on any copies of the Software.
     *
     * % If a worm touches itself, the cuticle prevents the worm from folding and
     * % touching adjacent pairs of muscle segments; therefore, the distance
     * % between touching segments must be, at least, the length of 2 muscle
     * % segments.'''
    
    cdef int FLAG_MAX = 2147483647 #max 32 integer. initialization
    cdef int maxSkeletonOverlap = <int>(ceil(2 * worm_seg_size));
    cdef int number_points = skeleton.shape[0]
    cdef int last_index = number_points - 1
    
    cdef np.ndarray[np.int_t, ndim=1] pSortC = np.lexsort((skeleton[:,1], skeleton[:,0])) 
    cdef np.ndarray[np.int_t, ndim=1] iSortC = np.argsort(pSortC)
    
    #output
    cdef int buff_size = 2*number_points;
    cdef np.ndarray[np.float_t, ndim=2] cSkeleton = np.zeros((buff_size, 2), dtype = np.float); #//% pre-allocate memory
    cdef np.ndarray[np.float_t, ndim=1] cWidths = np.zeros(buff_size, dtype = np.float);
    
    #indexes
    cdef np.ndarray[np.int_t, ndim=1] keep = np.arange(number_points)
    cdef int minI, maxI;
    cdef int s1I = 0; #// % the first index for the skeleton loop
    cdef int i, s2I, pI;
    cdef double dSkeleton[2];
    
    while (s1I < last_index):
        #//% Find small loops.
        #// % Note: distal, looped sections are most likely touching;
        #// % therefore, we don't remove these.
        if (keep[s1I] != FLAG_MAX):
            minI = s1I; #//% the minimum index for the loop
            maxI = s1I; #//% the maximum index for the loop
            
            #//% Search backwards.
            if (iSortC[s1I] > 0):
                pI = iSortC[s1I] - 1; #//% the index for the sorted points
                s2I = pSortC[pI]; #// % the second index for the skeleton loop
                
                dSkeleton[0] = absDiff(skeleton[s1I, 0], skeleton[s2I, 0]);
                dSkeleton[1] = absDiff(skeleton[s1I, 1], skeleton[s2I, 1]);

                while ((dSkeleton[0]<=1) or (dSkeleton[1]<=1)):
                    if ((s2I > s1I) and (keep[s2I]!=FLAG_MAX) and (dSkeleton[0]<=1) and \
                    (dSkeleton[1]<=1) and absDiff(s1I, s2I) < maxSkeletonOverlap):
                        minI = int_min(minI, s2I);
                        maxI = int_max(maxI, s2I);
                    
                    #// Advance the second index for the skeleton loop.
                    pI = pI - 1;
                    if(pI < 1):
                        break;
                    
                    s2I = pSortC[pI];
                    dSkeleton[0] = absDiff(skeleton[s1I, 0], skeleton[s2I, 0]);
                    dSkeleton[1] = absDiff(skeleton[s1I, 1], skeleton[s2I, 1]);

            #//% Search forwards.
            if (iSortC[s1I]< last_index):
                pI = iSortC[s1I] + 1; #//% the index for the sorted points
                s2I = pSortC[pI]; #//% the second index for the skeleton loop
                dSkeleton[0] = absDiff(skeleton[s1I, 0], skeleton[s2I, 0]);
                dSkeleton[1] = absDiff(skeleton[s1I, 1], skeleton[s2I, 1]);

                while ((dSkeleton[0]<=1) or (dSkeleton[1]<=1)):
                    if ((s2I > s1I) and (keep[s2I]!=FLAG_MAX) \
                    and (dSkeleton[0]<=1) and (dSkeleton[1]<=1) \
                    and absDiff(s1I, s2I) < maxSkeletonOverlap):
                        minI = min(minI, s2I);
                        maxI = max(maxI, s2I);
                    
                    #// Advance the second index for the skeleton loop.
                    pI = pI + 1;
                    if (pI > last_index):
                        break;
                    
                    s2I = pSortC[pI];
                    dSkeleton[0] = absDiff(skeleton[s1I, 0], skeleton[s2I, 0]);
                    dSkeleton[1] = absDiff(skeleton[s1I, 1], skeleton[s2I, 1]);


            #//% Remove small loops.
            if (minI < maxI):
                #//% Remove the overlap.
                if ((skeleton[minI,0] == skeleton[maxI,0]) and  \
                (skeleton[minI,1] == skeleton[maxI,1])):
                    for i in range(minI+1, maxI+1):
                        keep[i] = FLAG_MAX;
                        widths[minI] = fmin(widths[minI], widths[i]);
                #//% Remove the loop.
                else:
                    if(minI < maxI - 1):
                        for i in range(minI+1, maxI):
                            keep[i] = FLAG_MAX;
                            widths[minI] = fmin(widths[minI], widths[i]);
                            widths[maxI] = fmin(widths[maxI], widths[i]);
                        
            #//% Advance the first index for the skeleton loop.
            s1I = maxI if (s1I < maxI) else s1I + 1;
        #//% Advance the first index for the skeleton loop.
        else:
            s1I = s1I + 1;
    
    
    cdef int newTotal = 0;
    for i in range(number_points):
        if (keep[i] != FLAG_MAX):
            skeleton[newTotal, 0] = skeleton[i,0];
            skeleton[newTotal, 1] = skeleton[i,1];
            widths[newTotal] = widths[i];
            newTotal+=1;

    #//% The head and tail have no width.
    widths[0] = 0;
    widths[newTotal-1] = 0;
    number_points = newTotal;
    last_index = number_points-1
    
    del iSortC, pSortC;
    
    #//% Heal the skeleton by interpolating missing points.
            
    cdef int j = 0, m;
    cdef float x,y, x1,x2, y1, y2, delY, delX, delW;
    cdef float points;
    
    #variables used to check for repeated points in interpolations
    cdef float xd, yd, xprev, yprev;
    cdef int n_interp

    for i in range(last_index):
        #//% Initialize the point differences.
        y = absDiff(skeleton[i + 1, 0], skeleton[i, 0]);
        x = absDiff(skeleton[i + 1, 1], skeleton[i, 1]);
        
        #//% Add the point.
        if ((y == 0. or y == 1.) and (x == 0. or x == 1.)):
            cSkeleton[j,0] = skeleton[i,0];
            cSkeleton[j,1] = skeleton[i,1];
            
            cWidths[j] = widths[i];
            j +=1;
        
        #//% Interpolate the missing points.
        else:
            points = fmax(y, x);
            
            if j + points > buff_size:
                #increase in case there is a buffer overflow
                buff_size *= 2
                cSkeleton.resize((buff_size,2))
                cWidths.resize(buff_size)
            
            y1 = skeleton[i,0];
            y2 = skeleton[i + 1,0];
            delY = (y2-y1)/points;
            x1 = skeleton[i,1];
            x2 = skeleton[i + 1,1];
            delX = (x2-x1)/points;
            delW = (widths[i + 1] - widths[i])/points;
            
            #used to avoid repeated points (they can overflow the buffer)
            xprev  = -1;
            yprev  = -1;
            n_interp = 0; #number of points in the interpolation
            for m in range(<int>points):
                xd = round(x1 + m*delX);
                yd = round(y1 + m*delY);
                if (xd != xprev) or (yd !=yprev):
                    cSkeleton[j+n_interp, 0] = yd;
                    cSkeleton[j+n_interp, 1] = xd;
                    cWidths[j+n_interp] = round(widths[i] + m*delW);
                    n_interp += 1;
            j += n_interp+1;

    
    #//% Add the last point.
    cSkeleton[j,0] = skeleton[last_index,0];
    cSkeleton[j,1] = skeleton[last_index,1];
    cWidths[j] = widths[last_index];
    j+=1;
    
    number_points = j;
    
    #//% Anti alias.
    keep = np.arange(number_points)
    cdef int nextI
    i = 0;
    
    while (i < number_points - 2):
        #//% Smooth any stairs.
        nextI = i + 2;
        if ((absDiff(cSkeleton[i,0], cSkeleton[nextI,0])<=1) and (absDiff(cSkeleton[i,1], cSkeleton[nextI,1])<=1)):
            keep[i + 1] = FLAG_MAX;
            #//% Advance.
            i = nextI;
        #//% Advance.
        else:
            i+=1;
    
    newTotal = 0;
    for i in range(number_points):
        if (keep[i] != FLAG_MAX):
            cSkeleton[newTotal,0] = cSkeleton[i,0];
            cSkeleton[newTotal,1] = cSkeleton[i,1];
            cWidths[newTotal] = cWidths[i];
            newTotal+=1;
        
    
    cSkeleton = cSkeleton[:newTotal, :]
    cWidths = cWidths[:newTotal]
    
    return cSkeleton, cWidths
    
    