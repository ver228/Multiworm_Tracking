# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 12:44:07 2015

@author: ajaver
"""

import json
import os
from MWTracker import AUX_FILES_DIR
#get default parameters files
from MWTracker import DFLT_PARAMS_PATH, DFLT_PARAMS_FILES


#deprecated variables that will be ignored
deprecated_fields = ['has_timestamp', 'min_displacement']

#the dict key are the old names and the value the new name
deprecated_alias = {
    'fps': 'expected_fps',
    'threshold_factor': 'worm_bw_thresh_factor',
    'is_invert_thresh' : 'is_light_background',
    'is_fluorescence' : 'is_light_background',
    'min_length' : 'min_box_width',
    'max_area' : 'mask_max_area',
    'save_int_maps': 'int_save_maps'}

dflt_param_list = [
    ('mask_min_area', 50, 'minimum allowed area in pixels allowed for in the compression mask.'),
    ('mask_max_area', int(1e8), 'maximum allowed area in pixels allowed for in the compression mask..'),
    ('min_box_width', 5, 'minimum allowed width of bounding box in pxels.'),
    ('thresh_C', 15, 'constant offset used by the adaptative thresholding to calculate the mask.'),
    ('thresh_block_size', 61, 'block size used by the adaptative thresholding.'),
    ('dilation_size', 9, 'size of the structural element used in morphological operations to calculate the worm mask.'),
    ('expected_fps', 25, 'expected frame rate.'),
    ('compression_buff', -1, 'number of images "min-averaged" to calculate the image mask. If it is -1 the program will read the expected_fps from the file.'),
    ('keep_border_data', False, 'set it to false if you want to remove any connected component that touches the border.'),
    ('is_light_background', True, 'set to true to indentify dark worms over a light background.'),
    ('traj_min_area', 25, 'minimum allowed area in pixels allowed for the trajectories and the videos.'),
    ('traj_max_allowed_dist', 25, 'Maximum displacement expected between frames to be consider same track.'),
    ('traj_area_ratio_lim', [0.5, 2], 'Limits of the consecutive blob areas to be consider the same object.'),
    ('worm_bw_thresh_factor', 1.05, 'This factor multiplies the threshold used to binarize the individual worms image.'),
    ('resampling_N', 49, 'number of segments used to renormalize the worm skeleton and contours.'),
    ('max_gap_allowed_block', 10, 'maximum time gap allowed between valid skeletons to be considered as belonging in the same group. Head/Tail correction by movement.'),
    ('strel_size', 5, 'Structural element size. Used to calculate skeletons and trajectories.'),
    ('fps_filter', 0, 'PROBALY USELESS (Used in joinTrajectories). frame per second used to calculate filters for trajectories. Set to zero to eliminate filtering.'),
    
    ('ht_orient_segment', -1, 'Segment size to calculate the head_tail.'),

    ('filt_bad_seg_thresh', 0.8, 'minimum fraction of succesfully skeletonized frames in a worm trajectory to be considered valid'),
    ('filt_min_displacement', 10, 'minimum total displacement of a trajectory to be used to calculate the threshold to dectect bad skeletons.'),
    ('filt_critical_alpha', 0.01, 'critical chi2 alpha used in the mahalanobis distance to considered a worm a global outlier.'),
    ('filt_max_width_ratio', 2.25, 'Maximum width radio between midbody and head or tail. Does the worm more than double its width from the head/tail? Useful for coils.'),
    ('filt_max_area_ratio', 6, 'maximum area ratio between head+tail and the rest of the body to be a valid worm.  Are the head and tail too small (or the body too large)?'),
    
    ('int_save_maps', False, 'save the intensity maps and not only the profile along the worm major axis.'),
    ('int_avg_width_frac', 0.3, 'width fraction from the center used to calculate the worm axis intensity profile.'),
    ('int_width_resampling', 15, 'width in pixels of the intensity maps'),
    ('int_length_resampling', 131, 'length in pixels of the intensity maps'),
    ('int_max_gap_allowed_block', -1, 'maximum time gap allowed between valid intensity maps to be considered as belonging in the same group. Head/Tail correction by intensity.'),
    ('split_traj_time', 300, 'time in SECONDS that a trajectory will be subdivided to calculate the splitted features.'),
    ('roi_size', -1, ''),
    ('filter_model_name', '', ''),
    ('n_cores_used', 1, 'Number of core used. Currently it is only suported by TRAJ_CREATE and it is only recommended at high particle densities.'),
    
    ('is_bgnd_subtraction', False, 'Do the background subtraction step'),
    ('bgnd_buff_size', 25, 'Number of image to keep to calculate the background'),
    ('bgnd_frame_gap', 250, 'Frame gap between images used to calculate the background.'),

    ('analysis_type', 'WORM', 'Analysis functions to use. Valid options: WORM, SINGLE_WORM_SHAFER, ZEBRAFISH (broken)'),
    ('w_num_segments', 24, 'Number of segments used to calculate the skeleton curvature (or half the number of segments used for the contour curvature).  Reduced for rounder objects and decreased for sharper organisms.'),
    ('w_head_angle_thresh', 60, 'Threshold to consider a peak on the curvature as the head or tail.'),

    #not tested (used for the zebra fish)
    ('zf_num_segments', 12, 'Number of segments to use in tail model.'),
    ('zf_min_angle', -90, 'The lowest angle to test for each segment. Angles are set relative to the angle of the previous segment.'),
    ('zf_max_angle', 90, 'The highest angle to test for each segment.'),
    ('zf_num_angles', 90, 'The total number of angles to test for each segment. Eg., If the min angle is -90 and the max is 90, setting this to 90 will test every 2 degrees, as follows: -90, -88, -86, ...88, 90.'),
    ('zf_tail_length', 60, 'The total length of the tail model in pixels.'),
    ('zf_tail_detection', 'MODEL_END_POINT', 'Algorithm to use to detect the fish tail point.'),
    ('zf_prune_retention', 1, 'Number of models to retain after scoring for each round of segment addition. Higher numbers will be much slower.'),
    ('zf_test_width', 2, 'Width of the tail in pixels. This is used only for scoring the model against the test frame.'),
    ('zf_draw_width', 2, 'Width of the tail in pixels. This is used for drawing the final model.'),
    ('zf_auto_detect_tail_length', True, 'Flag to determine whether zebrafish tail length detection is used. If set to True, values for zf_tail_length, zf_num_segments and zf_test_width are ignored.')
]

#separate parameters default data into dictionaries for values and help
default_param = {x: y for x, y, z in dflt_param_list}
param_help = {x: z for x, y, z in dflt_param_list}


def _correct_filter_model_name(filter_model_name):
    if filter_model_name:
        if not os.path.exists(filter_model_name):
            #try to look for the file in the AUX_FILES_DIR
            filter_model_name = os.path.join(AUX_FILES_DIR, filter_model_name)
        assert  os.path.exists(filter_model_name)

    return filter_model_name

def _correct_fps(expected_fps):
    if not isinstance(expected_fps, int):
        expected_fps = int(expected_fps)
    return expected_fps

def get_all_prefix(input_params, prefix):
    return {x.replace(prefix, ''):input_params[x] for x in input_params if x.startswith(prefix)}


def _correct_json_path(json_file):
    if json_file in DFLT_PARAMS_FILES:
        json_file = os.path.join(DFLT_PARAMS_PATH, json_file)
    return json_file


class tracker_param:

    def __init__(self, source_file=''):
        p = self._read_clean_input(source_file)

        self.expected_fps = _correct_fps(p['expected_fps'])
        self.analysis_type = p['analysis_type']
        self.is_single_worm = self.analysis_type == 'SINGLE_WORM_SHAFER'
        self.use_skel_filter = True #useless but important in other functions

        #default parameters that depend on other properties
        if p['max_gap_allowed_block'] < 0:
            p['max_gap_allowed_block'] = self.expected_fps // 2
        
        if p['ht_orient_segment'] > 0:
            p['ht_orient_segment'] = round(p['resampling_N'] / 10)
        
        if p['int_max_gap_allowed_block'] < 0:
            p['int_max_gap_allowed_block'] = p['max_gap_allowed_block'] / 2
       


        # getROIMask
        mask_param_f = ['mask_min_area', 'mask_max_area', 'thresh_block_size', 
        'thresh_C', 'dilation_size', 'keep_border_data', 'is_light_background']
        self.mask_param = {x.replace('mask_', ''):p[x] for x in mask_param_f}

        #background subtraction
        bgnd_param_f = ['is_bgnd_subtraction', 'bgnd_buff_size', 'bgnd_frame_gap']
        self.bgnd_param = {x.replace('bgnd_', ''):p[x] for x in bgnd_param_f}

        
        # compressVideo
        self.compress_vid_param = {
            'buffer_size': p['compression_buff'],
            'save_full_interval': -1,
            'max_frame': 1e32,
            'mask_param': self.mask_param,
            'bgnd_param': self.bgnd_param,
            'expected_fps': self.expected_fps
        }

        # parameters for a subsampled video
        self.subsample_vid_param = {
            'time_factor' : 8, 
            'size_factor' : 5, 
            'expected_fps' : self.expected_fps
        }

        # getBlobsTable
        trajectories_param_f = ['traj_min_area', 'min_box_width',
        'worm_bw_thresh_factor', 'strel_size', 'analysis_type', 'thresh_block_size',
        'n_cores_used']
        self.trajectories_param = {x.replace('traj_', ''):p[x] for x in trajectories_param_f}
        self.trajectories_param['buffer_size']=p['compression_buff']

        # joinTrajectories
        min_track_size = max(1, p['fps_filter'] * 2)
        max_time_gap = max(0, p['fps_filter'] * 4)
        self.join_traj_param = {
            'max_allowed_dist': p['traj_max_allowed_dist'],
            'min_track_size': min_track_size,
            'max_time_gap': max_time_gap,
            'area_ratio_lim': p['traj_area_ratio_lim'],
            'is_single_worm': self.is_single_worm}

        # getSmoothTrajectories
        self.smoothed_traj_param = {
            'min_track_size': min_track_size,
            'displacement_smooth_win': self.expected_fps + 1,
            'threshold_smooth_win': self.expected_fps * 20 + 1,
            'roi_size': p['roi_size']}

        
        self.init_skel_param = {
            'smoothed_traj_param': self.smoothed_traj_param,
            'filter_model_name' : _correct_filter_model_name(p['filter_model_name'])
            }

        self.blob_feats_param =  {
            'is_light_background' : p['is_light_background'],
            'strel_size' : p['strel_size']
            }

        if self.analysis_type == 'ZEBRAFISH':
            skel_args = get_all_prefix(input_params, 'zf_')
        else:
            skel_args = {'num_segments' : p['w_num_segments'],
                         'head_angle_thresh' : p['w_head_angle_thresh']}


        # trajectories2Skeletons

        self.skeletons_param = {
            'resampling_N': p['resampling_N'],
            'worm_midbody': (0.33, 0.67),
            'min_blob_area': p['traj_min_area'],
            'strel_size': p['strel_size'],
            'analysis_type': self.analysis_type,
            'skel_args' : skel_args}
            

        
        self.head_tail_param = {
            'max_gap_allowed': p['max_gap_allowed_block'],
            'window_std': self.expected_fps,
            'segment4angle': p['ht_orient_segment'],
            'min_block_size': self.expected_fps * 10}

        min_num_skel = 4 * self.expected_fps
        self.feat_filt_param = get_all_prefix(p, 'filt_')
        self.feat_filt_param['min_num_skel'] = min_num_skel


        self.int_profile_param = {
            'width_resampling': p['int_width_resampling'],
            'length_resampling': p['int_length_resampling'],
            'min_num_skel': min_num_skel,
            'smooth_win': 11,
            'pol_degree': 3,
            'width_percentage': p['int_avg_width_frac'],
            'save_maps': p['int_save_maps']}

        
        
        smooth_W = max(1, round(self.expected_fps / 5))
        self.head_tail_int_param = {
            'smooth_W': smooth_W,
            'gap_size': p['int_max_gap_allowed_block'],
            'min_block_size': (2*self.expected_fps)//5,
            'local_avg_win': 10 * self.expected_fps,
            'min_frac_in': 0.85,
            'head_tail_param': self.head_tail_param}
        # getWormFeatures
        self.feats_param = {
            'expected_fps': self.expected_fps, 
            'feat_filt_param': self.feat_filt_param,
            'split_traj_time' : p['split_traj_time'],
            'is_single_worm': self.is_single_worm
        }

        self.p_dict = p


    def _read_clean_input(self, source_file):
        self.json_file = _correct_json_path(source_file)

        input_param = default_param.copy()
        if self.json_file:
            with open(self.json_file) as fid:
                param_in_file = json.load(fid)
            for key in param_in_file:

                if key in deprecated_fields:
                    #ignore deprecated fields
                    continue
                elif key in deprecated_alias:
                    #rename deprecated alias
                    input_param[deprecated_alias[key]] = param_in_file[key]
                
                elif key == 'min_area':
                    #special case of deprecated alias
                    input_param['mask_min_area'] = param_in_file['min_area']
                    input_param['traj_min_area'] = param_in_file['min_area']/2

                else:
                    input_param[key] = param_in_file[key]
        return input_param


if __name__=='__main__':
    json_file = '/Users/ajaver/Documents/GitHub/Multiworm_Tracking/fluorescence/pharynx.json'
    params = tracker_param(json_file)
    print(params.trajectories_param)

