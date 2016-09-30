# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 12:44:07 2015

@author: ajaver
"""

import json

#deprecated variables that will be ignored
deprecated_fields = ['has_timestamp', 'min_displacement']

#the dict key are the old names and the value the new name
deprecated_alias = {
    'fps': 'expected_fps',
    'threshold_factor': 'worm_bw_thresh_factor',
    'is_invert_thresh' : 'is_light_background',
    'is_fluorescence' : 'is_light_background',
    'min_length' : 'min_box_width'}

dflt_param_list = [
    ('min_area', 50, 'minimum allowed area in pixels.'),
    ('max_area', int(1e8), 'maximum allowed area in pixels.'),
    ('min_box_width', 5, 'minimum allowed width of bounding box in pxels.'),
    ('thresh_C', 15, 'constant offset used by the adaptative thresholding to calculate the mask.'),
    ('thresh_block_size', 61, 'block size used by the adaptative thresholding.'),
    ('dilation_size', 9, 'size of the structural element used in morphological operations.'),
    ('compression_buff', 25, 'number of images "min-averaged" to calculate the image mask.'),
    ('keep_border_data', False, 'set it to false if you want to remove any connected component that touches the border.'),
    ('is_light_background', True, 'set to true to indentify dark worms over a light background.'),
    ('expected_fps', 25, 'expected frame rate.'),
    ('traj_max_allowed_dist', 25, 'Maximum displacement expected between frames to be consider same track.'),
    ('worm_bw_thresh_factor', 1.05, 'This factor multiplies the threshold used to binarize the individual worms image.'),
    ('resampling_N', 49, 'number of segments used to renormalize the worm skeleton and contours.'),
    ('max_gap_allowed_block', 10, ''),
    ('fps_filter', -1, 'frame per second used to calculate filters for trajectories. As default it will have the same value as expected_fps. Set to zero to eliminate filtering.'),
    ('strel_size', 5, ''),
    ('filt_bad_seg_thresh', 0.8, 'minimum fraction of succesfully skeletonized frames in a worm trajectory to be considered valid'),
    ('filt_min_displacement', 10, 'minimum total displacement of a trajectory to be used to calculate the threshold to dectect bad skeletons.'),
    ('filt_critical_alpha', 0.01, ''),
    ('filt_max_width_ratio', 2.25, ''),
    ('filt_max_area_ratio', 6, ''),
    ('save_int_maps', False, 'save the intensity maps and not only the profile along the worm major axis.'),
    ('int_avg_width_frac', 0.3, ''),
    ('int_width_resampling', 15, ''),
    ('int_length_resampling', 131, ''),
    ('int_max_gap_allowed_block', -1, ''),
    ('use_background_subtraction', False, 'Flag to determine whether background should be subtracted from original frames.'),
    ('background_threshold', 1, 'Threshold value to use when applying background subtraction.'),
    ('ignore_mask', False, 'Mask is not used if set to True. Only applies if background subtraction is also active.'),
    ('background_type', 'GENERATE_DYNAMICALLY', 'If background subtraction is enabled, determines whether background is generated dynamically or loaded from a file'),
    ('background_frame_offset', 500, 'Number of frames offset from current frame used for generating background images.'),
    ('background_generation_function', 'MAXIMUM', 'Function to apply to frames in order to generate background images.'),
    ('background_file', '', 'Image file to use for background subtraction. If a filepath is set here, this file will be used instead of dynamically-generated background images.'),
    ('analysis_type', 'WORM', 'Analysis functions to use.'),
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

default_param = {x: y for x, y, z in dflt_param_list}
param_help = {x: z for x, y, z in dflt_param_list}


class tracker_param:

    def __init__(self, source_file=''):
        input_param = default_param.copy()
        if source_file:
            with open(source_file) as fid:
                param_in_file = json.load(fid)
            for key in param_in_file:
                if key in deprecated_fields:
                    continue
                elif key in deprecated_alias:
                    input_param[deprecated_alias[key]] = param_in_file[key]
                else:
                    input_param[key] = param_in_file[key]

        self._get_param(**input_param)
        # print(input_param)

    def _get_param(
            self,
            min_area,
            max_area,
            min_box_width,
            thresh_C,
            thresh_block_size,
            dilation_size,
            compression_buff,
            keep_border_data,
            is_light_background,
            expected_fps,
            traj_max_allowed_dist,
            worm_bw_thresh_factor,
            resampling_N,
            max_gap_allowed_block,
            fps_filter,
            strel_size,
            filt_bad_seg_thresh,
            filt_min_displacement,
            filt_critical_alpha,
            filt_max_width_ratio,
            filt_max_area_ratio,
            save_int_maps,
            int_avg_width_frac,
            int_width_resampling,
            int_length_resampling,
            int_max_gap_allowed_block,
            use_background_subtraction,
            ignore_mask,
            background_type,
            background_threshold,
            background_frame_offset,
            background_generation_function,
            background_file,
            analysis_type,
            zf_num_segments,
            zf_min_angle,
            zf_max_angle,
            zf_num_angles,
            zf_tail_length,
            zf_tail_detection,
            zf_prune_retention,
            zf_test_width,
            zf_draw_width,
            zf_auto_detect_tail_length):

        if not isinstance(expected_fps, int):
            expected_fps = int(expected_fps)

        self.expected_fps = expected_fps

        # getROIMask
        self.mask_param = {
            'min_area': min_area,
            'max_area': max_area,
            'thresh_block_size': thresh_block_size,
            'thresh_C': thresh_C,
            'dilation_size': dilation_size,
            'keep_border_data': keep_border_data,
            'is_light_background': is_light_background}

        # compressVideo
        self.compress_vid_param = {
            'buffer_size': compression_buff,
            'save_full_interval': 200 * expected_fps,
            'max_frame': 1e32,
            'mask_param': self.mask_param,
            'expected_fps': expected_fps,
            'use_background_subtraction': use_background_subtraction,
            'ignore_mask': ignore_mask,
            'background_type': background_type,
            'background_threshold': background_threshold,
            'background_frame_offset': background_frame_offset,
            'background_generation_function': background_generation_function,
            'background_file': background_file}
        
        # getWormTrajectories
        self.trajectories_param = {
            'initial_frame': 0,
            'last_frame': -1,
            'min_area': min_area / 2,
            'min_box_width': min_box_width,
            #'min_track_length': max(1, fps_filter / 5), # this filter is currently not used in getWormTrajectories
            'max_allowed_dist': traj_max_allowed_dist,
            'area_ratio_lim': (
                0.5,
                2),
            'buffer_size': compression_buff,
            'worm_bw_thresh_factor': worm_bw_thresh_factor,
            'strel_size': (
                strel_size,
                strel_size),
            'analysis_type': analysis_type}

        # joinTrajectories
        min_track_size = max(1, fps_filter * 2)
        max_time_gap = max(0, fps_filter * 4)
        self.join_traj_param = {
            'min_track_size': min_track_size,
            'max_time_gap': max_time_gap,
            'area_ratio_lim': (
                0.67,
                1.5)}

        # getSmoothTrajectories
        self.smoothed_traj_param = {
            'min_track_size': min_track_size,
            'displacement_smooth_win': expected_fps + 1,
            'threshold_smooth_win': expected_fps * 20 + 1,
            'roi_size': -1,
            'analysis_type': analysis_type}

        # trajectories2Skeletons
        self.skeletons_param = {
            'resampling_N': resampling_N,
            'worm_midbody': (
                0.33,
                0.67),
            'min_mask_area': min_area / 2,
            'smoothed_traj_param': self.smoothed_traj_param,
            'strel_size': strel_size,
            'analysis_type': analysis_type,
            'zf_num_segments': zf_num_segments,
            'zf_min_angle': zf_min_angle,
            'zf_max_angle': zf_max_angle,
            'zf_num_angles': zf_num_angles,
            'zf_tail_length': zf_tail_length,
            'zf_tail_detection': zf_tail_detection,
            'zf_prune_retention': zf_prune_retention,
            'zf_test_width': zf_test_width,
            'zf_draw_width': zf_draw_width,
            'zf_auto_detect_tail_length': zf_auto_detect_tail_length}

        # correctHeadTail
        if max_gap_allowed_block < 0:
            expected_fps // 2
        self.head_tail_param = {
            'max_gap_allowed': max_gap_allowed_block,
            'window_std': expected_fps,
            'segment4angle': round(
                resampling_N / 10),
            'min_block_size': expected_fps * 10}

        min_num_skel = 4 * expected_fps
        # getWormFeatures
        self.feat_filt_param = {
            'min_num_skel': min_num_skel,
            'bad_seg_thresh': filt_bad_seg_thresh,
            'min_displacement': filt_min_displacement,
            'critical_alpha': filt_critical_alpha,
            'max_width_ratio': filt_max_width_ratio,
            'max_area_ratio': filt_max_area_ratio}

        self.int_profile_param = {
            'width_resampling': int_width_resampling,
            'length_resampling': int_length_resampling,
            'min_num_skel': min_num_skel,
            'smooth_win': 11,
            'pol_degree': 3,
            'width_percentage': int_avg_width_frac,
            'save_int_maps': save_int_maps}

        if int_max_gap_allowed_block < 0:
            int_max_gap_allowed_block = max_gap_allowed_block / 2

        smooth_W = max(1, round(expected_fps / 5))
        self.head_tail_int_param = {
            'smooth_W': smooth_W,
            'gap_size': int_max_gap_allowed_block,
            'min_block_size': (
                2 * expected_fps // 5),
            'local_avg_win': 10 * expected_fps,
            'min_frac_in': 0.85,
            'head_tail_param': self.head_tail_param}
