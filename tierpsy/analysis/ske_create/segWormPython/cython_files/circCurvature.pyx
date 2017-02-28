# -*- coding: utf-8 -*-
"""
Created on Wed May 27 00:43:07 2015

@author: ajaver
"""

"""
multiply.pyx

simple cython test of accessing a numpy array's data

the C function: c_multiply multiplies all the values in a 2-d array by a scalar, in place.

"""

import cython

# import both numpy and the Cython declarations for numpy
import numpy as np
cimport numpy as np

# declare the interface to the C code
cdef extern void c_circCurvature(double *points, int numberOfPoints, double edgeLength, double *chainCodeLengths, double *angles)
cdef extern void c_circCurvature_simple(double *points, int numberOfPoints, double edgeLength, double *angles)

@cython.boundscheck(False)
@cython.wraparound(False)
def circCurvature(np.ndarray[np.float_t, ndim=2, mode="c"] points not None, \
double edgeLength, np.ndarray[np.float_t, ndim=1, mode="c"] chainCodeLengths = np.zeros(1)):
    """
    multiply (arr, value)

    Takes a numpy arry as input, and multiplies each elemetn by value, in place

    param: array -- a 2-d numpy array of np.float64
    param: value -- a number that will be multiplied by each element in the array

    """
    cdef int numberOfPoints = points.shape[0]
    cdef np.ndarray[np.float_t, ndim=1, mode="c"] angles = np.zeros(numberOfPoints)
    
    
    if chainCodeLengths.size == numberOfPoints:
        c_circCurvature(&points[0,0], numberOfPoints, edgeLength, &chainCodeLengths[0], &angles[0])    
    else:
        c_circCurvature_simple(&points[0,0], numberOfPoints, edgeLength, &angles[0])    
    
    return angles

