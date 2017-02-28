# -*- coding: utf-8 -*-
"""
Created on Tue Aug  9 00:24:17 2016

@author: ajaver
"""
import os
from functools import partial

import tables


def _isValidFlag(field, flag_value):
    return (field._v_attrs['has_finished'] >= flag_value)

def _isValidProvenance(field, point_name):
    return (point_name in field)

def _checkFlagsFun(fname, field_name, test_value, test_func=_isValidFlag, extra_files=[]):
    accepted_errors = (tables.exceptions.HDF5ExtError, 
        tables.exceptions.NoSuchNodeError, KeyError,IOError)
    try:
        with tables.open_file(fname, mode='r') as fid:
            field = fid.get_node(field_name)
            has_finished = test_func(field, test_value)

            #check that all the extra files do exist
            has_finished = has_finished and all(os.path.exists(x) for x in extra_files)
            
            return has_finished

    except accepted_errors:
            return False



class CheckFinished(object):
    def __init__(self, output_files):
        
        #check that the correct provenance point is stored in the corresponding file
        self._provenance_funcs = {}
        for point in output_files:
            provenance_file = output_files[point][0]
            extra_files = output_files[point][1:]
            
            self._provenance_funcs[point] = partial(_checkFlagsFun, 
                provenance_file,  
                '/provenance_tracking', 
                point, 
                _isValidProvenance,
                extra_files)


        #I plan to check succesful processing using only provenance. I keep this for backwards compatibility.
        outf = lambda x : output_files[x][0]

        #has_finished flags were deprecated in favor of provenance tracking flags
        self._deprec_check_funcs = {
            'COMPRESS': [partial(_checkFlagsFun, outf('COMPRESS'), '/mask', 1)],
            'COMPRESS_ADD_DATA': [partial(_checkFlagsFun, outf('COMPRESS'), '/mask', 2)],
            'TRAJ_CREATE': [partial(_checkFlagsFun, outf('TRAJ_CREATE'), '/plate_worms', 1)],
            'TRAJ_JOIN': [partial(_checkFlagsFun, outf('TRAJ_JOIN'), '/plate_worms', 2)],
            'SKE_CREATE': [partial(_checkFlagsFun, outf('SKE_CREATE'), '/skeleton', 1)],
            'SKE_FILT': [partial(_checkFlagsFun, outf('SKE_FILT'), '/skeleton', 2)],
            'SKE_ORIENT': [partial(_checkFlagsFun, outf('SKE_ORIENT'), '/skeleton', 3)],
            'INT_PROFILE': [partial(_checkFlagsFun, outf('INT_PROFILE'), '/straighten_worm_intensity_median', 1)],
            'INT_SKE_ORIENT': [partial(_checkFlagsFun, outf('INT_SKE_ORIENT'), '/skeleton', 4)],
            'FEAT_CREATE': [partial(_checkFlagsFun, outf('FEAT_CREATE'), '/features_means', 1)],
            'FEAT_MANUAL_CREATE': [partial(_checkFlagsFun, outf('FEAT_MANUAL_CREATE'), '/features_means', 1)],
        }

        #deprecated due to the removal of trajectories.hdf5 from the pipeline
        traj_file = outf('TRAJ_CREATE').replace('_skeletons.hdf5', '_trajectories.hdf5')
        for point in ['TRAJ_CREATE', 'TRAJ_JOIN']:
            func = partial(_checkFlagsFun, 
                            traj_file, 
                            '/provenance_tracking', 
                            point, 
                            _isValidProvenance,
                            extra_files)
            self._deprec_check_funcs[point].append(func)
        


    
    def getUnfinishedPoints(self, checkpoints2process):
        unfinished_points = checkpoints2process[:]
        for point in checkpoints2process:
            if self.get(point):
                unfinished_points.pop(0)
            else:
                break
        return unfinished_points
    
    def get(self, point):
        has_finished = self._provenance_funcs[point]()

        #we test flags for backwards compatibility
        if not has_finished and point in self._deprec_check_funcs:
            for func in self._deprec_check_funcs[point]:
                has_finished = func()
                if has_finished:
                    break
        

        return has_finished