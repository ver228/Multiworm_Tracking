# -*- coding: utf-8 -*-
"""
Created on Tue Aug  9 00:26:10 2016

@author: ajaver
"""
import os

from AnalysisPoints import AnalysisPoints
from ProcessWormsLocal import ProcessWormsLocal
from helperFunc import getDefaultSequence

if __name__ == '__main__':
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_17112015_205616.hdf5'
    #results_dir = '/Users/ajaver/Desktop/Videos/Avelino_17112015/Results1/'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Pratheeban/MaskedVideos/L1_early/15_07_07_C1_overnt_Ch1_07072015_160917.hdf5'
    #results_dir = '/Users/ajaver/Desktop/Videos/Pratheeban/Results/L1_early/'
    
    masked_image_file = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/300 LSJ1 on food L_2011_03_10__10_52_16___6___1.hdf5'
    results_dir = '/Users/ajaver/Desktop/Videos/single_worm/global_sample_v2/Results/'
    
    tmp_mask_dir = os.path.expanduser('~/Tmp/MaskedVideos/')
    tmp_results_dir = os.path.expanduser('~/Tmp/Results/')
    
    masks_dir = os.path.split(masked_image_file)[0]
    if not os.path.exists(results_dir):
        os.mkdir(results_dir)
    
    ap = AnalysisPoints(masked_image_file, masks_dir, results_dir, is_single_worm=True)
    checkpoints2process = getDefaultSequence('Track', is_single_worm=True, use_skel_filter=True)
    
    spl = ProcessWormsLocal(masked_image_file, masks_dir, results_dir, tmp_mask_dir,
            tmp_results_dir, json_file='', analysis_checkpoints = checkpoints2process, 
            is_single_worm=True, use_skel_filter=True, is_copy_video = True)
    
    cmd = spl.start()
    
    import subprocess
    pid = subprocess.Popen(cmd)
    pid.wait()
    
    spl.clean()