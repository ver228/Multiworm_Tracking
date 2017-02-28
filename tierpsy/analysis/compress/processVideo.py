# -*- coding: utf-8 -*-
"""
Created on Fri Oct 14 15:30:11 2016

@author: worm_rig
"""

import json
import os

import h5py
import tables
from tierpsy.analysis.compress.compressVideo import compressVideo, initMasksGroups

from  tierpsy.analysis.compress.selectVideoReader import selectVideoReader
from tierpsy.helper.misc import print_flush
from tierpsy.helper.timeCounterStr import timeCounterStr

#default parameters if wormencoder.ini does not exist
DFLT_SAVE_FULL_INTERVAL = 5000
DFLT_BUFFER_SIZE = 5
DFLT_MASK_PARAMS = {'min_area' : 50,
        'max_area' : 500000000,
        'thresh_C' : 15,
        'thresh_block_size' : 61,
        'dilation_size' : 7
        }

def _getWormEnconderParams(fname):
    def numOrStr(x):
        x = x.strip()
        try:
            return int(x)
        except:
            return x

    if os.path.exists(fname):

        with open(fname, 'r') as fid:
            dd = fid.read().split('\n')
            plugin_params =  {a.strip() : numOrStr(b) for a,b in 
              [x.split('=') for x in dd if x and x[0].isalpha()]}
    else:
        plugin_params = {}

    return plugin_params
    
def _getReformatParams(plugin_params):
    if plugin_params:
        save_full_interval = plugin_params['UNMASKEDFRAMES']
        buffer_size = plugin_params['MASK_RECALC_RATE']
        
        mask_params = {'min_area' : plugin_params['MINBLOBSIZE'],
        'max_area' : plugin_params['MAXBLOBSIZE'],
        'thresh_C' : plugin_params['THRESHOLD_C'],
        'thresh_block_size' : plugin_params['THRESHOLD_BLOCK_SIZE'],
        'dilation_size' : plugin_params['DILATION_KERNEL_SIZE']}
    else:
        #if an empty dictionary was given return default values
        save_full_interval = DFLT_SAVE_FULL_INTERVAL
        buffer_size = DFLT_BUFFER_SIZE
        mask_params = DFLT_MASK_PARAMS

    return save_full_interval, buffer_size, mask_params

           
def _isValidSource(original_file):
    try:
        with tables.File(original_file, 'r') as fid:
            fid.get_node('/mask')
            return True
    except tables.exceptions.HDF5ExtError:
        return False
        
    
def reformatRigMaskedVideo(original_file, new_file, plugin_param_file, expected_fps):
    plugin_params = _getWormEnconderParams(plugin_param_file)
     
    base_name = original_file.rpartition('.')[0].rpartition(os.sep)[-1]
    
    if not _isValidSource(original_file):
        print_flush(new_file + ' ERROR. File might be corrupt. ' + original_file)
        
        return
    
    
    progress_timer = timeCounterStr('Reformating Gecko plugin hdf5 video.')
    
    save_full_interval, buffer_size, mask_params = _getReformatParams(plugin_params)

    with tables.File(original_file, 'r') as fid_old, \
        h5py.File(new_file, 'w') as fid_new:
        
        mask_old = fid_old.get_node('/mask')
        
        tot_frames, im_height, im_width = mask_old.shape
    
        
        mask_new, full_new =  initMasksGroups(fid_new, tot_frames, im_height, im_width, 
        expected_fps, True, save_full_interval)
        
        
    
        mask_new.attrs['plugin_params'] = json.dumps(plugin_params)
        
        img_buff_ini = mask_old[:buffer_size]
        full_new[0] = img_buff_ini[0]
        
        
        mask_new[:buffer_size] = img_buff_ini*(mask_old[buffer_size] != 0)
        
        for frame in range(buffer_size, tot_frames):
            if frame % save_full_interval != 0:
                mask_new[frame] = mask_old[frame]
            else:
                
                full_frame_n = frame //save_full_interval
                
                img = mask_old[frame]
                full_new[full_frame_n] = img
                mask_new[frame] = img*(mask_old[frame-1] != 0)
            
            if frame % 500 == 0:
                # calculate the progress and put it in a string
                progress_str = progress_timer.getStr(frame)
                print_flush(base_name + ' ' + progress_str)
            
        #tag as finished reformatting
        mask_new.attrs['has_finished'] = 1

        print_flush(
            base_name +
            ' Compressed video done. Total time:' +
            progress_timer.getTimeStr())

def isGoodVideo(video_file):
    try:
        vid = selectVideoReader(video_file)
        # i have problems with corrupt videos that can create infinite loops...
        #it is better to test it before start a large taks
        vid.release()
        return True
    except OSError:
        # corrupt file, cannot read the size
        return False

def processVideo(video_file, masked_image_file, compress_vid_param):
    if video_file.endswith('hdf5'):
        plugin_param_file = os.path.join(os.path.dirname(video_file), 'wormencoder.ini')
        reformatRigMaskedVideo(video_file, masked_image_file, plugin_param_file, compress_vid_param['expected_fps'])
    else:
        compressVideo(video_file, masked_image_file, **compress_vid_param)

if __name__ == '__main__':        
    
    import argparse
    
    fname_wenconder = os.path.join(os.path.dirname(__file__), 'wormencoder.ini')
    parser = argparse.ArgumentParser(description='Reformat the files produced by the Gecko plugin in to the format of tierpsy.')
    parser.add_argument('original_file', help='path of the original file produced by the plugin')
    parser.add_argument('new_file', help='new file name')
    parser.add_argument(
            '--plugin_param_file',
            default = fname_wenconder,
            help='wormencoder file used by the Gecko plugin.')

    parser.add_argument(
            '--expected_fps',
            default=25,
            help='Expected recording rate in frame per seconds.')

    args = parser.parse_args()
    reformatRigMaskedVideo(**vars(args))
    