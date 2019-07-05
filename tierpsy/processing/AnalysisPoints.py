# -*- coding: utf-8 -*-
"""
Created on Mon Aug  8 17:24:27 2016

@author: ajaver
"""

import os
from importlib import import_module


from tierpsy.helper.misc import IMG_EXT

from tierpsy.helper.params import TrackerParams
from tierpsy.processing.CheckFinished import CheckFinished

from tierpsy.analysis.vid_subsample.createSampleVideo import getSubSampleVidName
from tierpsy.analysis.wcon_export.exportWCON import getWCOName

#lock for multiprocessing
analysis_points_lock = None
def init_analysis_point_lock(l):
   global analysis_points_lock
   analysis_points_lock = l

class CheckPoints(object):
    def __init__(self, file_names, param):
        self.args = {}
        self.file_names = file_names
        self.param = param

    def __getitem__(self, point):
        if not point in self.args:
            self._read_args(point)

        return self.args[point]

    def _read_args(self, point):
        #load arguments
        mod = import_module('tierpsy.analysis.' + point.lower())
        self.args[point] = mod.args_(self.file_names, self.param)

        #add the file that it's going to be used for the provenance_file
        if not 'provenance_file' in self.args[point]:
            self.args[point]['provenance_file'] = self.args[point]['output_files'][0]
            assert self.args[point]['provenance_file'].endswith('.hdf5')

        #assert all the required fields exist
        expected_arguments = set(['func', 'argkws', 'input_files', 'output_files', 'requirements'])
        missing_fields = expected_arguments - set(self.args[point].keys())
        if len(missing_fields):
            raise KeyError('Field {} is not present in {} arguments. Check the corresponding __init__.py file.'.format(missing_fields, point))


    def __iter__(self):
        self.remaining_points = list(self.args.keys())
        return self

    def __next__(self):
        if len(self.remaining_points)==0:
            raise StopIteration
        return self.remaining_points.pop(0)    

class AnalysisPoints(object):
    def __init__(self, video_file, masks_dir, 
        results_dir, json_file = ''):
        
        self.getFileNames(video_file, masks_dir, results_dir)
        
        self.video_file = video_file
        self.masks_dir = masks_dir
        self.results_dir = results_dir
        
        self.param = TrackerParams(json_file)
        self.checkpoints = CheckPoints(self.file_names, self.param)
        self.checker = CheckFinished(checkpoints_args = self.checkpoints)
        
    def getFileNames(self, video_file, masks_dir, results_dir):
        if any(video_file.endswith(x) for x in IMG_EXT):
            #This is a directory with a list of images. 
            #Use the directory name as the basename instead.
            base_name = os.path.basename(os.path.dirname(video_file))
        else:
            base_name = video_file.rpartition('.')[0].rpartition(os.sep)[-1]
        
        results_dir = os.path.abspath(results_dir)
        
        output = {'base_name' : base_name, 'original_video' : video_file}
        
        output['masked_image'] = os.path.join(masks_dir, base_name + '.hdf5')
    
        ext2add = [
            'trajectories',
            'skeletons',
            'features',
            'featuresN',
            'feat_manual',
            'intensities']

        for ext in ext2add:
            output[ext] = os.path.join(results_dir, base_name + '_' + ext + '.hdf5')
        
        output['subsample'] = getSubSampleVidName(output['masked_image'])
        output['wcon'] = getWCOName(output['features'])

        self.file_names =  output
        self.file2dir_dict = {fname:dname for dname, fname in map(os.path.split, self.file_names.values())}
    
    def getField(self, key, points2get = None):
        if points2get is None:
            points2get = self.checkpoints

        #return None if the field is not in point
        return {x : self.checkpoints[x][key] for x in points2get}
        
    def getArgs(self, point):
        return {x:self.checkpoints[point][x] for x in ['func', 'argkws', 'provenance_file']}
    
    
    def hasRequirements(self, point):
        
        requirements_results = {}

        #check the requirements of a given point
        for requirement in self.checkpoints[point]['requirements']:
            #import time
            #tic = time.time()
            #print(point, requirement)
            if isinstance(requirement, str):
                #if the requirement is a string, check the requirement with the checker 
                requirements_results[requirement] = self.checker.get(requirement)
                
            else:
                try:
                    req_name, func = requirement
                    if not analysis_points_lock is None and req_name in ['can_read_video']:
                        with analysis_points_lock:

                            requirements_results[req_name] = func()
                    else:
                        requirements_results[req_name] = func()
                

                except (OSError): 
                    #if there is a problem with the file return back requirement
                    requirements_results[requirement[0]] = False
            #print(time.time()-tic)
        self.unmet_requirements = [x for x in requirements_results if not requirements_results[x]]
        
        return self.unmet_requirements
    
    def getUnfinishedPoints(self, checkpoints2process):
        return self.checker.getUnfinishedPoints(checkpoints2process)
    
