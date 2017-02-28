# -*- coding: utf-8 -*-
"""
Created on Tue Aug  9 00:26:10 2016

@author: ajaver
"""
import os

from helperFunc import getDefaultSequence, walkAndFindValidFiles
from CheckFilesForProcessing import CheckFilesForProcessing

if __name__ == '__main__':
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_17112015_205616.hdf5'
    #results_dir = '/Users/ajaver/Desktop/Videos/Avelino_17112015/Results1/'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Pratheeban/MaskedVideos/L1_early/15_07_07_C1_overnt_Ch1_07072015_160917.hdf5'
    #results_dir = '/Users/ajaver/Desktop/Videos/Pratheeban/Results/L1_early/'
    
    mask_dir_root = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/'
    results_dir_root = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/Results/'
    tmp_dir_root = os.path.expanduser('~/Tmp/')
    
    checkpoints2process = getDefaultSequence('Track', is_single_worm=True, use_skel_filter=True)
    
    # search extensions that must be invalid to keep the analysis coherent
    valid_files = walkAndFindValidFiles(mask_dir_root, pattern_include='*.hdf5', pattern_exclude='')
    
    files_checker = CheckFilesForProcessing(mask_dir_root, mask_dir_root, 
                 results_dir_root, tmp_dir_root=tmp_dir_root, 
                 json_file='', analysis_checkpoints = checkpoints2process, 
                 is_single_worm = True, no_skel_filter=False,
                  is_copy_video = True)
    
    cmd_list = files_checker.filterFiles(valid_files)

