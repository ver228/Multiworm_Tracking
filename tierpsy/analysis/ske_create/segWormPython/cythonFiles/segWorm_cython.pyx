# -*- coding: utf-8 -*-
# cython: profile=True
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: infer_types=False

"""
Created on Wed May 20 14:56:35 2015

@author: ajaver
"""
import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport round as c_round;
from libc.math cimport sqrt, atan2, M_PI, abs

cdef inline double absDiff(double a, double b): 
    return a-b if a>b else b-a

cdef double calculate_displacement(double dPx, double dPy):
    #//% No change or we walked in a straight line.
    if (dPx ==0 or dPy ==0):
        return dPx + dPy;
    #//% We walked one point diagonally.
    elif dPx ==1 and dPy ==1:
        return 1.4142135623730951; #sqrt(2)
    #//% We walked fractionally or more than one point.
    else:
        return sqrt(dPx*dPx + dPy*dPy);
 
def circComputeChainCodeLengths(np.ndarray[np.float_t, ndim=2] points):
    '''
    %CIRCCOMPUTECHAINCODELENGTHS Compute the chain-code length, at each point,
    %   for a circularly-connected, continuous line of points.
    %
    %   LENGTHS = CIRCCOMPUTECHAINCODELENGTHS(POINTS)
    %
    %   Input:
    %       points - the circularly-connected, continuous line of points on
    %                which to measure the chain-code length
    %
    %   Output:
    %       lengths - the chain-code length at each point
    %
    % See also CHAINCODELENGTH2INDEX, COMPUTECHAINCODELENGTHS
    %
    %
    % © Medical Research Council 2012
    % You will not remove any copyright or other notices from the Software;
    % you must reproduce all copyright notices and other proprietary
    % notices on any copies of the Software.
    '''
    cdef int number_of_points = points.shape[0];
    #//% Pre-compute values.
    cdef double sqrt2 = sqrt(2);
    cdef int lastIndex = number_of_points-1;
    
    #//% Measure the difference between subsequent points.
    cdef double dPx, dPy;
    cdef np.ndarray[np.float_t, ndim=1] lengths = np.ones(number_of_points, dtype = np.float); 
    cdef int i
    
    dPx = absDiff(points[0,0], points[lastIndex,0]);
    dPy = absDiff(points[0,1], points[lastIndex,1]);
    lengths[0] = calculate_displacement(dPx, dPy)
    
    #//% Measure the chain code length.
    for i in range(1, number_of_points):
        #//% Measure the difference between subsequent points.
        dPx = absDiff(points[i,0], points[i-1,0]);
        dPy = absDiff(points[i,1], points[i-1,1]);
        lengths[i] = lengths[i-1] + calculate_displacement(dPx, dPy)
    return lengths

cdef inline double getSign(double x):
    return (0 < x) - (x < 0)

cdef computeFractionalPixel(np.ndarray[np.float_t, ndim=2] points, \
int curr_ind, int next_ind, \
double delta_edge, double * point_fractional):
    '''// *% Compute fractional pixels for the first edge.
    //% Note: the first edge is equal to or just over the requested edge
    //% length. Therefore, the fractional pixels for the requested length
    //% lie on the line separating point 1 (index = p1I) from the next
    //% closest point to the vertex (index = p1I + 1). Now, we need to
    //% add the difference between the requested and real distance (delta_edge)
    //% to point p1I, going in a line towards p1I + 1. Therefore, we need
    //% to solve the differences between the requested and real x & y
    //% (dx1 & dy1). Remember the requested x & y lie on the slope
    //% between point p1I and p1I + 1. Therefore, dy1 = m * dx1 where m
    //% is the slope. We want to solve delta_edge1 = sqrt(dx1^2 + dy1^2).
    //% Plugging in m, we get delta_edge1 = sqrt(dx1^2 + (m*dx1)^2). Then
    //% re-arrange the equality to solve:
    //%
    //% dx1 = delta_edge1/sqrt(1 + m^2) and dy1 = delta_edge/sqrt(1 + (1/m)^2)
    //%
    //% But, Matlab uses (r,c) = (y,x), so x & y are reversed.'''

    cdef double SQRT2 = 1.414213562373095;
    cdef int j
    cdef double delta_p[2] 
    cdef double r, dy1, dx1
    
    cdef double y_curr = points[curr_ind, 0]
    cdef double x_curr = points[curr_ind, 1]
    
    delta_p[0] = points[next_ind, 0] - y_curr;
    delta_p[1] = points[next_ind, 1] - x_curr;
    
    if ((delta_p[0] == 0) or (delta_p[1] == 0)):
        point_fractional[0] = y_curr + delta_edge*getSign(delta_p[0]);
        point_fractional[1] = x_curr + delta_edge*getSign(delta_p[1]);
    
    elif ((abs(delta_p[0]) == 1) and (abs(delta_p[1]) == 1)):
        point_fractional[0] = y_curr + (delta_p[0] * delta_edge / SQRT2);
        point_fractional[1] = x_curr + (delta_p[1] * delta_edge / SQRT2);
        
    else:
        r = (delta_p[1] / delta_p[0]);
        dy1 = delta_edge / sqrt(1 +  r*r);
        
        r = (delta_p[0] / delta_p[1]);
        dx1 = delta_edge / sqrt(1 +  r*r);
        
        point_fractional[0] = y_curr + dy1 * getSign(delta_p[0]); 
        point_fractional[1] = x_curr + dx1 * getSign(delta_p[1]);


cdef inline double getEdgeLengthLeft(double last_length, double pv, double p):
    return (pv - p) if (p <= pv) else (last_length + pv - p)

cdef inline double getEdgeLengthRight(double last_length, double pv, double p):
    return (p-pv) if (p >= pv) else (last_length + p - pv)
    
cdef inline int plusCircIndex(int ind, int last_index):
    return ind + 1 if (ind < last_index) else ind - last_index;
    
cdef inline int minusCircIndex(int ind, int last_index):
    return ind - 1 if (ind > 0) else ind + last_index;


def circCurvature_old(np.ndarray[np.float_t, ndim=2] points, double edgeLength, np.ndarray[np.float_t, ndim=1] chainCodeLengths):
    '''
    //   Inputs:
    //       points          - the vector of clockwise, circularly-connected
    //                          points ((x,y) pairs).
    //       edgeLength       - the length of edges from the angle vertex.
    //       chainCodeLengths - the chain-code length at each point;
    //                          if empty, the array indices are used instead
    //   Output:
    //       angles - the angles of curvature per point (0 = none to +-180 =
    //                maximum curvature). The sign represents whether the angle
    //                is convex (+) or concave (-).
    '''    
    
    cdef int number_of_points = points.shape[0];
    cdef int last_index = (number_of_points-1);
    cdef last_length = chainCodeLengths[last_index]
    
    cdef np.ndarray[np.float_t, ndim=1] angles = np.zeros(number_of_points, dtype = np.float)
    
    cdef double edge1, edge2;
    cdef int pv_ind; # central point index
    cdef int p1_ind, p2_ind; #indexes for a point in opposite side
    cdef double pv_length;
    cdef double p, pv
    
    
    
    cdef int nextP1_ind, prevP2_ind;
    cdef double delta_edge1, delta_edge2, nextE1;
    cdef double p1[2], p2[2];
    cdef double a1, a2, angle
    
    #initialize indexes
    pv_ind = 0
    p1_ind = last_index
    p2_ind = pv_ind;
    
    #initialize the first edge
    pv_length = chainCodeLengths[p1_ind] + chainCodeLengths[pv_ind];
    edge1 = pv_length - chainCodeLengths[p1_ind];
    while ((p1_ind > 0) and (edge1 < edgeLength)):
        p1_ind = p1_ind - 1;
        edge1 = pv_length - chainCodeLengths[p1_ind];
        
    while True:
        #// Compute the second edge length.
        pv = chainCodeLengths[pv_ind]
        p = chainCodeLengths[p2_ind]
        edge2 = getEdgeLengthRight(last_length, pv, p)
        #// Find the second edge.
        while (edge2 < edgeLength):
            p2_ind = plusCircIndex(p2_ind, last_index);
            
            p = chainCodeLengths[p2_ind]
            edge2 = getEdgeLengthRight(last_length, pv, p)
        
            
        #// Compute fractional pixels for the second edge (uses the next point).
        delta_edge1 =  edge1 - edgeLength;
        nextP1_ind =  plusCircIndex(p1_ind, last_index);        
        
        computeFractionalPixel(points, p1_ind, nextP1_ind, delta_edge1, p1);
        
        #// Compute fractional pixels for the second edge (uses the previous point).
        delta_edge2 = edge2 - edgeLength;
        prevP2_ind =  minusCircIndex(p2_ind, last_index);
        computeFractionalPixel(points, p2_ind, prevP2_ind, delta_edge2, p2);
        
        #// Use the difference in tangents to measure the angle.
        a2 = atan2(points[pv_ind,0] - p2[0], points[pv_ind,1] - p2[1]);
        a1 = atan2(p1[0] - points[pv_ind,0], p1[1] - points[pv_ind,1]);
        angle = a2-a1;
        
        if (angle > M_PI):
            angle -= 2 * M_PI;
        elif (angle < -1*M_PI):
            angle += 2 * M_PI;
        
        angles[pv_ind] = angle * 180 / M_PI;
        
        #// Advance.
        pv_ind = pv_ind + 1;
        if (pv_ind > last_index):
            break; #exit
        else: 
            #// Compute the first edge length.
            pv = chainCodeLengths[pv_ind]
            p = chainCodeLengths[p1_ind]

            edge1 = getEdgeLengthLeft(last_length, pv, p)
            nextE1 = edge1;
            nextP1_ind = p1_ind;
            while (nextE1 > edgeLength):
                edge1 = nextE1;
                p1_ind = nextP1_ind;
                nextP1_ind = plusCircIndex(p1_ind, last_index)
                
                p = chainCodeLengths[nextP1_ind]
                nextE1 = getEdgeLengthLeft(last_length, pv, p)
        
    return angles