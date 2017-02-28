
import sys
import os
import shutil
import stat
import glob

import tierpsy
from tierpsy import DFLT_PARAMS_PATH

def execute_cmd(command):
    cmd_dd = []
    for ii, x in enumerate(command):
        if ii != 0 and not x.startswith('--'):
            cmd_dd.append('"' + x + '"')
        else:
            cmd_dd.append(x)

    cmd_dd = ' '.join(cmd_dd)
    print(cmd_dd)

    os.system(cmd_dd)


def remove_dir(dir2remove):
    if os.path.exists(dir2remove):
        if sys.platform == 'darwin':
            for fname in glob.glob(os.path.join(dir2remove, '*.hdf5')):
                os.chflags(fname, not stat.UF_IMMUTABLE)
        shutil.rmtree(dir2remove)


def test1(script_dir, examples_dir):
    print('%%%%%% TEST1 %%%%%%\nGenerate mask files from .mjpg files.')
    main_dir = os.path.join(examples_dir, 'test_1')
    masked_files_dir = os.path.join(main_dir, 'MaskedVideos')
    raw_video_dir = os.path.join(main_dir, 'RawVideos')

    remove_dir(masked_files_dir)

    cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--video_dir_root',
        raw_video_dir,
        '--mask_dir_root',
        masked_files_dir,
        '--analysis_type',
        'compress',
        '--pattern_include',
        '*.mjpg'
        ]
    execute_cmd(cmd)


def test2(script_dir, examples_dir):
    print('%%%%%% TEST2 %%%%%%\nGenerate mask files from .avi files.')
    main_dir = os.path.join(examples_dir, 'test_2')
    masked_files_dir = os.path.join(main_dir, 'MaskedVideos')
    raw_video_dir = os.path.join(main_dir, 'RawVideos')
    json_file = os.path.join(main_dir, 'test2.json')

    remove_dir(masked_files_dir)

    cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--video_dir_root',
        raw_video_dir,
        '--mask_dir_root',
        masked_files_dir,
        '--analysis_type',
        'compress',
        "--json_file",
        json_file,
        '--pattern_include',
        '*.avi'
        ]
    execute_cmd(cmd)


def test3(script_dir, examples_dir):
    print('%%%%%% TEST3 %%%%%%\nTrack from masked video files.')
    main_dir = os.path.join(examples_dir, 'test_3')
    masked_files_dir = os.path.join(main_dir, 'MaskedVideos')
    results_dir = os.path.join(main_dir, 'Results')
    json_file = os.path.join(main_dir, 'test3.json')

    remove_dir(results_dir)

    cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--mask_dir_root',
        masked_files_dir,
        '--analysis_type',
        'track',
        "--json_file",
        json_file
        ]

    execute_cmd(cmd)


def test4(script_dir, examples_dir):
    print('%%%%%% TEST4 %%%%%%\nCalculate features from manually joined trajectories.')
    main_dir = os.path.join(examples_dir, 'test_4')
    masked_files_dir = os.path.join(main_dir, 'MaskedVideos')
    json_file = os.path.join(examples_dir, 'test_3', 'test3.json')

    feat_manual_file = os.path.join(
        main_dir,
        'Results',
        'Capture_Ch1_18062015_140908_feat_manual.hdf5')
    if os.path.exists(feat_manual_file):
        os.remove(feat_manual_file)

    cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--mask_dir_root',
        masked_files_dir,
        '--analysis_checkpoints',
        'FEAT_MANUAL_CREATE',
        "--json_file",
        json_file
        ]

    execute_cmd(cmd)


def test5(script_dir, examples_dir):
    print('%%%%%% TEST5 %%%%%%\nComplete analysis from video to calculate features.')
    main_dir = os.path.join(examples_dir, 'test_5')
    results_dir = os.path.join(main_dir, 'Results')
    masked_files_dir = main_dir

    remove_dir(results_dir)
    cmd = cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--mask_dir_root',
        masked_files_dir,
        '--analysis_type',
        'track']
    execute_cmd(cmd)




def test6(script_dir, examples_dir):
    print('%%%%%% TEST6 %%%%%%\nReformat mask file produced by the rig.')
    main_dir = os.path.join(examples_dir, 'test_6')
    masked_files_dir = os.path.join(main_dir, 'MaskedVideos')
    raw_video_dir = os.path.join(main_dir, 'RawVideos')

    json_file = os.path.join(DFLT_PARAMS_PATH, 'single_worm_on_food.json')
    #remove_dir(masked_files_dir)

    extra_cmd = ['STAGE_ALIGMENT', 'CONTOUR_ORIENT', 'FEAT_CREATE', 'WCON_EXPORT']
    
    cmd = [
        sys.executable,
        os.path.join(
            script_dir,
            'processMultipleFiles.py'),
        '--video_dir_root',
        raw_video_dir,
        '--mask_dir_root',
        masked_files_dir,
        '--json_file',
        json_file,
        '--pattern_include', 
        '*.avi',
        '--analysis_checkpoints',
        'COMPRESS',
        'COMPRESS_ADD_DATA',
        'VID_SUBSAMPLE',
        'TRAJ_CREATE',
        'TRAJ_JOIN',
        'SKE_INIT',
        'BLOB_FEATS',
        'SKE_CREATE',
        'SKE_FILT',
        'SKE_ORIENT',
        'INT_PROFILE',
        'INT_SKE_ORIENT',
        ]
    execute_cmd(cmd)

import argparse

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('n_tests', metavar='N', type=int, nargs='*',
                    help='Number of tests to be done. If it is empty it will execute all the tests.')
parser.add_argument('--tests', dest='accumulate', action='store_const',
                    const=sum, default=max,
                    help='sum the integers (default: find the max)')

if __name__ == '__main__':
    args = parser.parse_args()
    n_tests = args.n_tests
    

    root_dir = os.path.abspath(os.path.join(os.path.dirname(tierpsy.__file__), '..'))

    examples_dir = os.path.join(root_dir, 'tests', 'data')
    script_dir = os.path.join(root_dir, 'cmd_scripts')

    all_tests = [test1, test2, test3, test4, test5, test6] 
    
    tests_ind = [x-1 for x in n_tests]

    if tests_ind:
        test_to_exec = [all_tests[x] for x in tests_ind]
    else:
        test_to_exec = all_tests #execute all tests
    
    
    for fun in test_to_exec:
        fun(script_dir, examples_dir)
