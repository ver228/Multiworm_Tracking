import argparse
import os

from MWTracker.processing.batchProcHelperFunc import getDefaultSequence

class BaseMultipleFilesParser(argparse.ArgumentParser):
    def __init__(self, description, dflt_vals):
        super().__init__(
            description=description)
        self.add_argument(
            '--videos_list',
            default=dflt_vals['videos_list'],
            help='File containing the full path of the videos to be analyzed, otherwise there will be search from root directory using pattern_include and pattern_exclude.')

        self.add_argument(
            '--json_file',
            default=dflt_vals['json_file'],
            help='File (.json) containing the tracking parameters.')

        self.add_argument(
            '--tmp_dir_root',
            default=dflt_vals['tmp_dir_root'],
            help='Temporary directory where files are going to be stored.')

        self.add_argument(
            '--max_num_process',
            default=dflt_vals['max_num_process'],
            type=int,
            help='Max number of process to be executed in parallel.')

        self.add_argument(
            '--refresh_time',
            default=dflt_vals['refresh_time'],
            type=float,
            help='Refresh time in seconds of the process screen.')

        self.add_argument(
            '--pattern_include',
            default=dflt_vals['pattern_include'],
            help='Pattern used to find the valid video files in video_dir_root')
        self.add_argument(
            '--pattern_exclude',
            default=dflt_vals['pattern_exclude'],
            help='Pattern used to exclude files in video_dir_root')

        self.add_argument(
            '--only_summary',
            action='store_true',
            help='Use this flag if you only want to print a summary of the files in the directory.')


class CompressMultipleFilesParser(BaseMultipleFilesParser):
    description="Compress video files in the local drive using several parallel processes"
    dflt_vals = {
    'tmp_dir_root': os.path.join(
        os.path.expanduser("~"),
        'Tmp'),
    'json_file': '',
    'pattern_include': '*.mjpg',
    'pattern_exclude': '',
    'max_num_process': 6,
    'refresh_time': 10,
    'only_summary': False,
    'is_copy_video': False,
    'videos_list': ''}

    def __init__(self):
        super().__init__(
            self.description, self.dflt_vals)
        self.add_argument('video_dir_root',
                             help='Root directory with the raw videos.')
        self.add_argument('mask_dir_root',
            help='Root directory with the masked videos. It must the hdf5 from a previous compression step.')
        self.add_argument('--is_copy_video',
                action='store_true',
                help='The video file would be copied to the temporary directory.')


class TrackMultipleFilesParser(BaseMultipleFilesParser):
    description = "Track worm's hdf5 files in the local drive using several parallel processes"
    dflt_vals = {
    'results_dir_root': '',
    'tmp_dir_root': os.path.join(
        os.path.expanduser("~"),
        'Tmp'),
    'videos_list': '',
    'json_file': '',
    'pattern_include': '*.hdf5',
    'pattern_exclude': '',
    'max_num_process': 6,
    'refresh_time': 10,
    'force_start_point': '',
    'end_point': '',
    'only_summary': False}

    def __init__(self):
        super().__init__(
            self.description, self.dflt_vals)

        checkpoints2process = getDefaultSequence('track', is_single_worm=True, use_manual_join=True)

        self.add_argument('mask_dir_root',
            help='Root directory with the masked videos. It must the hdf5 from a previous compression step.')    
        self.add_argument(
            '--results_dir_root',
            default=self.dflt_vals['results_dir_root'],
            help='Root directory where the tracking results will be stored. If not given it will be estimated from the mask_dir_root directory.')
        self.add_argument(
            '--use_manual_join',
            action='store_true',
            help='Use this flag to calculate features on manually joined data.')
        self.add_argument(
            '--force_start_point',
            default=self.dflt_vals['force_start_point'],
            choices = checkpoints2process,
            help='Force the program to start at a specific point in the analysis.')
        self.add_argument(
            '--end_point',
            default=self.dflt_vals['end_point'],
            choices = checkpoints2process,
            help='End point of the analysis.')


    
    

    def __init__(self):
        super().__init__(
            self.description, self.dflt_vals)
        
class ProcessMultipleFilesParser(BaseMultipleFilesParser):
    description = "Process worm video in the local drive using several parallel processes"
    dflt_vals = {
    'video_dir_root': '',
    'mask_dir_root': '',
    'results_dir_root': '',
    'tmp_dir_root': os.path.join(
        os.path.expanduser("~"),
        'Tmp'),
    'videos_list': '',
    'json_file': '',
    'pattern_include': '*.hdf5',
    'pattern_exclude': '',
    'max_num_process': 6,
    'refresh_time': 10,
    'force_start_point': '',
    'end_point': '',
    'is_copy_video': False,
    'only_summary': False,
    'analysis_type':'',
    'analysis_checkpoints': []}

    def __init__(self):
        super().__init__(
            self.description, self.dflt_vals)
        
        checkpoints2process = getDefaultSequence('all', is_single_worm=True, add_manual_feats=True)

        self.add_argument('--video_dir_root',
            default=self.dflt_vals['video_dir_root'],
            help='Root directory with the raw videos.')
        
        self.add_argument('--mask_dir_root',
            default=self.dflt_vals['mask_dir_root'],
            help='Root directory with the masked videos. It must the hdf5 from a previous compression step.')
        
        self.add_argument('--results_dir_root',
            default=self.dflt_vals['results_dir_root'],
            help='Root directory where the tracking results will be stored. If not given it will be estimated from the mask_dir_root directory.')
        
        self.add_argument('--is_copy_video',
                action='store_true',
                help='The video file would be copied to the temporary directory.')

        self.add_argument(
            '--use_manual_join',
            action='store_true',
            help='Use this flag to calculate features on manually joined data.')
        
        group = self.add_mutually_exclusive_group()

        group.add_argument(
            '--analysis_type',
            default = 'all',
            choices = ['compress', 'track', 'all'],
            help='Type of analysis to be processed.',
            )

        group.add_argument(
            '--analysis_checkpoints',
            default=self.dflt_vals['analysis_checkpoints'],
            choices = checkpoints2process,
            nargs='+',
            help='List of the points to be processed.')
        

        self.add_argument(
            '--force_start_point',
            default=self.dflt_vals['force_start_point'],
            choices = checkpoints2process,
            help='Force the program to start at a specific point in the analysis.')
        
        self.add_argument(
            '--end_point',
            default=self.dflt_vals['end_point'],
            choices = checkpoints2process,
            help='End point of the analysis.')

        