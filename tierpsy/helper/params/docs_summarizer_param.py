'''
List of default values and description of the tierpsy.gui.Summarizer
'''

from .helper import repack_dflt_list

summarizer_valid_options = {
    'feature_type':['openworm','tierpsy'],
    'summary_type' : ['plate', 'trajectory', 'plate_augmented'],
    'time_units' : ['frame_numbers', 'seconds'],
    'select_feat' : ['all', 'tierpsy_8', 'tierpsy_16', 'tierpsy_256', 'tierpsy_2k','select_by_keywords']
}

dflt_args_list = [
    ('root_dir',
        '',
        'Root directory where the features files are located and the results are going to be saved.'
        ),
    ('feature_type',
        'tierpsy',
        '''
        Type of feature file to be used. Either the original OpenWorm features or the new Tierpsy Features.
        '''
        ),
    ('summary_type',
        'plate',
        '''
        Indicates if the summary is going to be done over each individual plate, each individual trajectory or
        is going to be a data augmentation by randomingly sampling over a subset of the plate trajectories.
        '''
        ),
    ('is_manual_index',
        False,
        'Set to true to calculate data using manually edited trajectories used Tierpsy Viewer.'
        ),
    ('time_windows',
        '0:end',
        '''
        Define time windows to extract features from the parts of the video included in each window.
        Each window must be defined by the start_time and the end_time connected by \':\' (start_time:end_time).
        Different windows must be separated by \',\' (start_time_1:end_time_1, start_time_2:end_time_2).
        A sequence of equally sized windows can be defined using the format \'start_time:end_time:step'\.
        Attention: the start_time is included in the window, but the end_time is not included.
        '''
        ),
    ('time_units',
        'frame_numbers',
        'Units of start time and end time in Time Windows.'
        ),
    ('select_feat',
        'all',
        '''
        Get a pre-selected subset of tierpsy features or select features by keywords.
        '''
        ),
    ('abbreviate_features',
        False,
        'Shorten the feature names so that they are compatible with MATLAB'
        ),
    ('dorsal_side_known',
        False,
        '''
        Dorsal side of worm has been annotated on videos. If dorsal side is not
        known then only absolute values for d/v signed features are returned.
        (nb. d/v features are not included in the 2k, 512, 256, 16 and 8 sets anyway)
        ''',
        ),
    ('keywords_include',
        '',
        '''
        Select only features that contain any of the given keywords. Provide keywords separated by comma \',\'.
        '''
        ),
    ('keywords_exclude',
        '',
        '''
        Exclude features that contain any of the given keywords. Provide keywords separated by comma \',\'.
        '''
        ),
    ('n_folds',
        5,
        '''
        Number of times each subsampling is going to be repeated (only for plate_augmentation).
        '''
        ),

    ('frac_worms_to_keep',
        0.8,
        'Fraction of the total number trajectories that is going to be keep for each subsampling.'
        ),
    ('time_sample_seconds',
        600,
        'Total time in seconds that is going to be keep for each subsampling.'
        )
    ]

summarizer_args_dflt, summarizer_args_info = repack_dflt_list(dflt_args_list, valid_options=summarizer_valid_options)
