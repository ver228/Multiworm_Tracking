# -*- coding: utf-8 -*-
"""
Created on Wed Aug 10 19:59:08 2016

@author: ajaver
"""
import os
import errno
import sys
import fnmatch

def walkAndFindValidFiles(root_dir, pattern_include='*', pattern_exclude=''):
    invalid_ext = [
                '*_intensities.hdf5',
                '*_skeletons.hdf5',
                '*_trajectories.hdf5',
                '*_features.hdf5',
                '*_feat_ind.hdf5']
    
    if not pattern_exclude:
        pattern_exclude = []
    elif not isinstance(pattern_exclude, (list, tuple)):
        pattern_exclude = [pattern_exclude]
    pattern_exclude += invalid_ext
    print(root_dir)
    return _walkAndFind(root_dir, 
                        pattern_include = pattern_include, 
                        pattern_exclude = pattern_exclude)

def _walkAndFind(root_dir, pattern_include='*', pattern_exclude=''):
    root_dir = os.path.abspath(root_dir)
    if not os.path.exists(root_dir):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), root_dir)
    # if there is only a string (only one pattern) let's make it a list to be
    # able to reuse the code
    if not isinstance(pattern_include, (list, tuple)):
        pattern_include = [pattern_include]
    if not isinstance(pattern_exclude, (list, tuple)):
        pattern_exclude = [pattern_exclude]

    valid_files = []
    for dpath, dnames, fnames in os.walk(root_dir):
        for fname in fnames:
            good_patterns = any(fnmatch.fnmatch(fname, dd)
                                for dd in pattern_include)
            bad_patterns = any(fnmatch.fnmatch(fname, dd)
                               for dd in pattern_exclude)
            if good_patterns and not bad_patterns:
                fullfilename = os.path.abspath(os.path.join(dpath, fname))
                assert os.path.exists(fullfilename)
                valid_files.append(fullfilename)

    return valid_files

def getRealPathName(fullfile):
    '''get the path name that works with pyinstaller binaries'''
    try:
        base_name = os.path.splitext(os.path.basename(fullfile))[0]
        # use this directory if it is a one-file produced by pyinstaller
        script_cmd = [os.path.join(sys._MEIPASS, base_name)]
        if os.name == 'nt':
            script_cmd[0] += '.exe'
        return script_cmd
    
    except AttributeError:
        return [sys.executable, os.path.realpath(fullfile)]

def create_script(base_cmd, args, argkws):
    cmd = base_cmd + args
    for key, dat in argkws.items():
        if isinstance(dat, bool):
            if dat:
                cmd.append('--' + key)
        elif isinstance(dat, (list, tuple)):
            cmd += ['--'+key] + list(dat)
        else:
            cmd += ['--' + key, str(dat)]
    return cmd


def getDefaultSequence(action, is_single_worm=False, add_manual_feats=''):
    action = action.lower()
    assert any(action == x for x in ['compress', 'track', 'all'])
    if is_single_worm:
        CHECKPOINTS_DFT = { 'compress': ['COMPRESS',
                                        'COMPRESS_ADD_DATA',
										'VID_SUBSAMPLE'],
                            'track' : ['VID_SUBSAMPLE',
                                        'TRAJ_CREATE',
                                        'TRAJ_JOIN',
                                        'SKE_INIT',
                                        'BLOB_FEATS',
                                        'SKE_CREATE',
                                        'SKE_FILT',
                                        'SKE_ORIENT',
                                        'INT_PROFILE',
                                        'INT_SKE_ORIENT',
                                        'STAGE_ALIGMENT',
                                        'CONTOUR_ORIENT',
                                        'FEAT_CREATE',
                                        'WCON_EXPORT'
                                        ]}
    else:
        CHECKPOINTS_DFT = { 'compress': ['COMPRESS',
										'VID_SUBSAMPLE'],
                            'track' : ['VID_SUBSAMPLE',
                                    'TRAJ_CREATE',
                                    'TRAJ_JOIN',
                                    'SKE_INIT',
                                    'BLOB_FEATS',
                                    'SKE_CREATE',
                                    'SKE_FILT',
                                    'SKE_ORIENT',
                                    'INT_PROFILE',
                                    'INT_SKE_ORIENT',
                                    'FEAT_CREATE'
                                    ]}
    
    if add_manual_feats:
        CHECKPOINTS_DFT['track'].append('FEAT_MANUAL_CREATE') 

    if action == 'all':
        points =  CHECKPOINTS_DFT['compress'] + CHECKPOINTS_DFT['track']

        #remove duplicates while keeping the order (http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-whilst-preserving-order)
        seen = set()
        seen_add = seen.add
        points =  [x for x in points if not (x in seen or seen_add(x))]

        assert len(points) == len(set(points))
        return points
    else:
        return CHECKPOINTS_DFT[action]

if __name__ == '__main__':
    print(getDefaultSequence('all'))
