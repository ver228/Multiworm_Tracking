# -*- coding: utf-8 -*-
# cython: profile=True
"""
Created on Wed May 20 14:56:35 2015

@author: ajaver
"""


import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport round as c_round;
from libc.math cimport sqrt, floor, ceil


cdef inline bint compare_extrema(bint is_min, float x1, float x2):
    return x1>x2 if is_min else x1<x2

cdef inline bint compare_extrema_eq(bint is_min, float x1, float x2):
    return x1>=x2 if is_min else x1<=x2

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
def extremaPeaksCircDist(int extrema_type, np.ndarray[np.float64_t, ndim=1] x, float dist, np.ndarray[np.float64_t, ndim=1] chainCodeLengths = np.zeros(0)):
    #extrema type positive for maxima, negative or zero for minima

    if chainCodeLengths.size == 0:
        chainCodeLengths = np.arange(1, x.size+1, dtype = np.float64);
        
    if chainCodeLengths.size != x.size:
        print('Wrong chain code lengths size')
        return
    
    #//% Is the vector larger than the search window?
    cdef double winSize = 2 * dist + 1;
    cdef int ind
    if (chainCodeLengths[chainCodeLengths.size-1] < winSize):
        if extrema_type > 0:
            ind = np.argmax(x);
        else:
            ind = np.argmin(x);
        return (x[ind], ind);
    
    return extremaPeaksCircDist_(<bint>(extrema_type <= 0), x, dist, chainCodeLengths)
    # (peaks, indices)

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
cdef extremaPeaksCircDist_(bint is_min, np.ndarray[np.float64_t, ndim=1] x, float dist,
    np.ndarray[np.float64_t, ndim=1] chainCodeLengths):
    
    #//% Search for peaks.
    cdef :
        int im = -1; #//% the last maxima index
        int ie = -1; #//% the end index for the last maxima's search window
        int ip = 0; #//% the current, potential, max peak index
        double p = x[ip]; #//% the current, potential, max peak value
        int i = 1; #//% the vector index
        int j = 0; #//% the recorded, maximal peaks index
        int k;      
        bint isExtrema;
        int numberOfPoints = x.size;
        int lastIndexChain = numberOfPoints - 1;
        np.ndarray[np.float_t, ndim=1]  peaks = np.zeros(numberOfPoints, dtype = np.float);
        np.ndarray[np.int_t, ndim=1] indices = np.zeros(numberOfPoints, dtype = np.int)
    
    while (i < numberOfPoints):
        #//% Found a potential peak.
        if compare_extrema_eq(is_min, p, x[i]):
            ip = i;
            p = x[i];
        
        #//% Test the potential peak.
        if ((chainCodeLengths[i] - chainCodeLengths[ip]) >= dist) or (i == lastIndexChain):
            #//% Check the untested values next to the previous maxima.
            if (im >= 0) and ((chainCodeLengths[ip] - chainCodeLengths[im]) <= (2 * dist)):
                #//% Check the untested values next to the previous maxima. 
                isExtrema = True;
                k = ie;
                while isExtrema and (k >= 0) and ((chainCodeLengths[ip] - chainCodeLengths[k]) < dist):
                    #//% Is the previous peak larger?
                    if compare_extrema_eq(is_min, x[ip], x[k]):
                        isExtrema = False;
                    #//% Advance.
                    k -= 1;
                
                #//% Record the peak.
                if isExtrema:
                    indices[j] = ip;
                    peaks[j] = p;
                    j = j + 1;
                
                #//% Record the maxima.
                im = ip;
                ie = i;
                ip = i;
                p = x[ip];
            #//% Record the peak.
            else:
                indices[j] = ip;
                peaks[j] = p;
                j = j + 1;
                im = ip;
                ie = i;
                ip = i;
                p = x[ip];
        
        #//% Advance.
        i += 1;

    cdef indexSize = j;
    cdef int indexStart = 0;
    cdef int indexEnd = indexSize-1;
    
    #//% If we have two or more peaks, we have to check the start and end for mistakes.
    if(indexSize > 2):
        #//% If the peaks at the start and end are too close, keep the largest or
        #//% the earliest one.
        if ((chainCodeLengths[indices[indexStart]] + chainCodeLengths[lastIndexChain] - chainCodeLengths[indices[indexEnd]]) < dist):
            if compare_extrema_eq(is_min, peaks[indexStart], peaks[indexEnd]):
                indexStart += 1;
            else:
                indexEnd -= 1;
                
        #//% Otherwise, check any peaks that are too close to the start and end.
        else:
            #//% If we have a peak at the start, check the wrapping portion just
            #//% before the end.
            k = numberOfPoints-1;
            
            while ((chainCodeLengths[indices[indexStart]] + chainCodeLengths[lastIndexChain] - chainCodeLengths[k]) < dist):
                #//% Remove the peak.
                if compare_extrema_eq(is_min, peaks[0], x[k]):
                    indexStart += 1;
                    break;
                #//% Advance.
                k -= 1;
            
            #//% If we have a peak at the end, check the wrapping portion just
            #//% before the start.
            k = 0;
            while ((chainCodeLengths[lastIndexChain] - chainCodeLengths[indices[indexEnd]] + chainCodeLengths[k]) < dist):
                #//% Remove the peak.
                if compare_extrema(is_min, peaks[indexEnd], x[k]):
                    indexEnd -= 1;
                    break;
                #//% Advance.
                k += 1
            
    
    #//output
    peaks = peaks[indexStart:indexEnd+1].copy();
    indices = indices[indexStart:indexEnd+1].copy();
    return (peaks, indices)



cdef inline double absDiff(double a, double b): 
    return a-b if a>b else b-a
    
#cdef inline int max(int a, int b): return a if a <= b else b

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
def removeSmallSegments(np.ndarray[np.float_t, ndim=2] contour):
    '''% Remove small overlapping segments and anti alias the contour.
    % Note: we don't remove loops. Removing loops may, for example, incorrectly
    % clean up a collapsed contour and/or remove a tail whip thereby leading to
    % false positives and/or false negatives, respectively.
    '''
    cdef np.ndarray[np.uint8_t, ndim=1] keep = np.ones(contour.shape[0], dtype = np.uint8); 
    cdef int lastIndex = contour.shape[0] -1;
    cdef int i, nextI, next2I;
    cdef double dContour_x, dContour_y;
    
    if (contour[0,0] == contour[lastIndex,0]) and (contour[0,1] == contour[lastIndex,1]):
        keep[0] = 0;
    
    #% Remove small overlapping segments and anti alias the contour.
    i = 0;
    while (i <= lastIndex):
        #//% Initialize the next 2 indices.
        if (i < lastIndex - 1):
            nextI = i + 1;
            next2I = i + 2;
        
        #//% The second index wraps.
        elif (i < lastIndex):
                nextI = lastIndex;
                next2I = 0;
                
                #//% Find the next kept point.
                while (not keep[next2I]):
                    next2I+=1;
                
                #//% The are no more kept points.
                if (i == next2I):
                    break;
                    
        #//% Both indices wrap.
        else:
            #//% Find the next kept point.
            nextI = 0;
            while (not keep[nextI]):
                nextI+=1;
            
            #//% The are no more kept points.
            if(i == nextI):
                break;
            
            #//% Find the next kept point.
            next2I = nextI + 1;
            while (not keep[next2I]):
                next2I+=1;
            
            #//% The are no more kept points.
            if (i == next2I):
                break;
        
        dContour_x = absDiff(contour[i,0], contour[next2I,0]);
        dContour_y = absDiff(contour[i,1], contour[next2I,1]);
        
        if (dContour_x == 0) and (dContour_y == 0):
            keep[i] = 0;
            keep[nextI] = 0;
            #% Advance.
            i = i + 2;
            
        #% Smooth any stairs.
        elif (dContour_x <= 1) and (dContour_y <= 1):
            keep[nextI] = 0;
            #% Advance.
            i = i + 2;
            
        #% Advance.
        else:
            i = i + 1;
        
    contour = contour[keep==1,:];
    
    return contour, keep

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
def cleanContour(np.ndarray[np.float_t, ndim=2] contour):
    '''%CLEANCONTOUR Clean an 8-connected, circularly-connected contour by
    %removing any duplicate points and interpolating any missing points.
    %
    %   [ccontour] = cleancontour(contour)
    %
    %   Input:
    %       contour - the 8-connected, circularly-connected contour to clean
    %
    %   Output:
    %       cContour - the cleaned contour (no duplicates & no missing points)
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software; 
    % you must reproduce all copyright notices and other proprietary 
    % notices on any copies of the Software.'''
    #%%
    #% Construct the cleaned contour.
    cdef np.ndarray[np.float_t, ndim=2] cContour = np.zeros_like(contour);
    cdef int last_index_contour = contour.shape[0]-1;
    cdef int i, j = 0;
    cdef double x, y, x1, x2, y1, y2
    
    for i in range(contour.shape[0]-1):
        y1 = contour[i,0]
        y2 = contour[i + 1,0]
        x1 = contour[i,1]
        x2 = contour[i + 1,1]
        #% Initialize the point differences.
        y = absDiff(y1,y2);
        x = absDiff(x1,x2);
        
        #% Ignore duplicates.
        if y == 0 and x == 0 :
            continue;
        
        #% Add the point.
        if (y == 0 or y == 1) and (x == 0 or x == 1):
            cContour[j,:] = contour[i,:];
            j = j + 1;
            
        #% Interpolate the missing points.
        else:
            points = <int>max(y, x);
            cContour[j:(j + points),0] = np.round(np.linspace(y1, y2, points + 1));
            cContour[j:(j + points),1] = np.round(np.linspace(x1, x2, points + 1));
            j = j + points;
    
    #% Add the last point
    if (cContour[0,0] != contour[last_index_contour,0]) or \
            (cContour[1,0] != contour[last_index_contour,1]):
        cContour[j,:] = contour[last_index_contour,:]
        j = j + 1;
    
    cContour = cContour[:j,:]
    #%%
    return cContour

