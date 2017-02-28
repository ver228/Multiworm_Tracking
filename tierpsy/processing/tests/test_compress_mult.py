# -*- coding: utf-8 -*-
"""
Created on Thu Aug 11 10:00:43 2016

@author: ajaver
"""

import os
from MWTracker.helper.runMultiCMD import runMultiCMD
from helperFunc import getDefaultSequence, walkAndFindValidFiles
from CheckFilesForProcessing import CheckFilesForProcessing
from ProcessWormsLocal import ProcessWormsLocalParser

if __name__ == '__main__':
    
    #mask_dir_root = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/'
    #results_dir_root = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/Results/'
    
    video_dir_root = '/Users/ajaver/Documents/GitHub/Multiworm_Tracking/Tests/Data/test_2/RawVideos/'
    mask_dir_root = '/Users/ajaver/Documents/GitHub/Multiworm_Tracking/Tests/Data/test_2/RawVideos/Masks/'
    
    tmp_dir_root = os.path.expanduser('~/Tmp/')
    
    checkpoints2process = getDefaultSequence('Track', is_single_worm=True, use_skel_filter=True)
    
    # search extensions that must be invalid to keep the analysis coherent
    valid_files = walkAndFindValidFiles(mask_dir_root, pattern_include='*.hdf5', pattern_exclude='')
    
    files_checker = CheckFilesForProcessing(mask_dir_root, mask_dir_root, 
                 mask_dir_root, tmp_dir_root=tmp_dir_root, 
                 json_file='', analysis_checkpoints = checkpoints2process, 
                 is_single_worm = True, no_skel_filter=False,
                  is_copy_video = True)
    
    cmd_list = files_checker.filterFiles(valid_files)
    #ProcessWormsLocalParser(cmd_list[0][1:])
    runMultiCMD(
            cmd_list,
            local_obj = ProcessWormsLocalParser,
            max_num_process = 6,
            refresh_time = 10)