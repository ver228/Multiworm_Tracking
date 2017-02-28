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
cdef extern double c_curvspace(double *points, int p_size, int p_dim, int N, double *output)

@cython.boundscheck(False)
@cython.wraparound(False)
def curvspace(np.ndarray[double, ndim=2, mode="c"] points not None, int N):
    """
    multiply (arr, value)

    Takes a numpy arry as input, and multiplies each elemetn by value, in place

    param: array -- a 2-d numpy array of np.float64
    param: value -- a number that will be multiplied by each element in the array

    """
    cdef int p_size, p_dim
    cdef curv_len
    
    cdef np.ndarray[double, ndim=2, mode="c"] output = np.zeros((N,2))
    p_size, p_dim = points.shape[0], points.shape[1]
    
    curv_len = c_curvspace (&points[0,0], p_size, p_dim, N, &output[0,0])    
    return output, curv_len 

