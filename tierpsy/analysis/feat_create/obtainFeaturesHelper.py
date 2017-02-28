# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 2015

@author: ajaver
"""

import copy
import os
import math
import numpy as np
import pandas as pd
import tables
from scipy.signal import savgol_filter

from MWTracker import AUX_FILES_DIR
from MWTracker.analysis.ske_filt.getFilteredSkels import _h_calAreaArray

# (http://www.pytables.org/usersguide/parameter_files.html)
tables.parameters.MAX_COLUMNS = 1024

from collections import OrderedDict
import open_worm_analysis_toolbox as mv
np.seterr(invalid='ignore')


def calWormAngles(x, y, segment_size):
    '''
    Get the skeleton angles from its x, y coordinates
    '''
    assert(x.ndim == 1)
    assert(y.ndim == 1)

    dx = x[segment_size:] - x[:-segment_size]
    dy = y[segment_size:] - y[:-segment_size]

    pad_down = math.floor(segment_size / 2)
    pad_up = math.ceil(segment_size / 2)

    # pad the rest of the array with delta of one segment
    #dx = np.hstack((np.diff(x[0:pad_down]), dx, np.diff(x[-pad_up:])))
    #dy = np.hstack((np.diff(y[0:pad_down]), dy, np.diff(y[-pad_up:])))

    #dx = np.diff(x);
    #dy = np.diff(y);

    angles = np.arctan2(dx, dy)
    dAngles = np.diff(angles)

    #    % need to deal with cases where angle changes discontinuously from -pi
    #    % to pi and pi to -pi.  In these cases, subtract 2pi and add 2pi
    #    % respectively to all remaining points.  This effectively extends the
    #    % range outside the -pi to pi range.  Everything is re-centred later
    #    % when we subtract off the mean.
    #
    #    % find discontinuities larger than pi (skeleton cannot change direction
    #    % more than pi from one segment to the next)
    # %+1 to cancel shift of diff
    positiveJumps = np.where(dAngles > np.pi)[0] + 1
    negativeJumps = np.where(dAngles < -np.pi)[0] + 1

    #% subtract 2pi from remainging data after positive jumps
    for jump in positiveJumps:
        angles[jump:] = angles[jump:] - 2 * np.pi

    #% add 2pi to remaining data after negative jumps
    for jump in negativeJumps:
        angles[jump:] = angles[jump:] + 2 * np.pi

    #% rotate skeleton angles so that mean orientation is zero
    meanAngle = np.mean(angles)
    angles = angles - meanAngle

    pad_left = np.full(pad_down, np.nan)
    pad_right = np.full(pad_up, np.nan)
    angles = np.hstack((pad_left, angles, pad_right))
    return (angles, meanAngle)


def calWormAnglesAll(skeleton, segment_size=5):
    '''calculate the angles of each of the skeletons'''

    #segment_half = segment_size/2
    #ang_pad =  (floor(segment_half),ceil(segment_half))

    meanAngles_all = np.zeros(skeleton.shape[0])
    angles_all = np.full((skeleton.shape[0], skeleton.shape[1]), np.nan)
    for ss in range(skeleton.shape[0]):
        if skeleton[ss, 0, 0] == np.nan:
            continue  # skip if skeleton is invalid

        angles_all[
            ss, :], meanAngles_all[ss] = calWormAngles(
            skeleton[
                ss, :, 0], skeleton[
                ss, :, 1], segment_size=segment_size)

        # angles_all[ss,ang_pad[0]:-ang_pad[1]],meanAngles_all[ss] = \
        #calWormAngles(skeleton[ss,:,0],skeleton[ss,:,1], segment_size=segment_size)

    return angles_all, meanAngles_all


def smoothCurve(curve, window=5, pol_degree=3):
    '''smooth curves using the savgol_filter'''

    if curve.shape[0] < window:
        # nothing to do here return an empty array
        return np.full_like(curve, np.nan)

    # consider the case of one (widths) or two dimensions (skeletons, contours)
    if curve.ndim == 1:
        smoothed_curve = savgol_filter(curve, window, pol_degree)
    else:
        smoothed_curve = np.zeros_like(curve)
        for nn in range(curve.ndim):
            smoothed_curve[:, nn] = savgol_filter(
                curve[:, nn], window, pol_degree)

    return smoothed_curve


def smoothCurvesAll(curves, window=5, pol_degree=3):
    for ii in range(curves.shape[0]):
        if not np.any(np.isnan(curves[ii])):
            curves[ii] = smoothCurve(
                curves[ii], window=window, pol_degree=pol_degree)
    return curves


class WormFromTable(mv.NormalizedWorm):
    """
    Encapsulates the notion of a worm's elementary measurements, scaled
    (i.e. "normalized") to 49 points along the length of the worm.
    In the future it might become a method of NormalizedWorm,
    but for the moment let's test it as a separate identity
    """

    def __init__(self, file_name, worm_index, use_skel_filter=True,
                 worm_index_str='worm_index_joined', micronsPerPixel=1, fps=25,
                 smooth_window=-1, POL_DEGREE_DFLT=3):
        # Populates an empty normalized worm.
        mv.NormalizedWorm.__init__(self)

        # savitzky-golay filter polynomial order default
        self.POL_DEGREE_DFLT = POL_DEGREE_DFLT
        # save the input parameters
        self.file_name = file_name
        self.worm_index = worm_index
        self.micronsPerPixel = micronsPerPixel
        self.use_skel_filter = use_skel_filter
        self.worm_index_str = worm_index_str
        # set to less than POL_DEGREE_DFLT to eliminate smoothing
        self.smooth_window = smooth_window

        # smooth window must be an odd number larger than the polynomial degree
        # (savitzky-golay filter requirement)
        if self.smooth_window >= self.POL_DEGREE_DFLT and self.smooth_window % 2 == 0:
            self.smooth_window += 1

        # video info, for the moment we intialize it with the fps
        self.video_info = mv.VideoInfo('', fps)

        skeleton_id, timestamp = self.getTrajDataTable(
            self.file_name, self.worm_index, self.use_skel_filter, self.worm_index_str)

        self.readSkeletonsData(skeleton_id, timestamp, self.micronsPerPixel)

        # smooth data if required
        if self.smooth_window > self.POL_DEGREE_DFLT:
            # print('Smoothing...')
            self.skeleton = smoothCurvesAll(
                self.skeleton, window=self.smooth_window)
            self.widths = smoothCurvesAll(
                self.widths, window=self.smooth_window)

        # calculate angles
        self.angles, meanAngles_all = calWormAnglesAll(
            self.skeleton, segment_size=1)

        # calculate the number of valid skeletons
        self.n_valid_skel = np.sum(~np.isnan(self.length))

        # assert the dimenssions of the read data are correct
        self.assertDataDim()

    def getTrajDataTable(
            self,
            file_name,
            worm_index,
            use_skel_filter,
            worm_index_str):
        '''
        Get the relevant info from the trajectory_data table for a single worm. skeleton_id, timestamp.
        '''
        # intialize just to make clear the relevant variables for this function

        with pd.HDFStore(file_name, 'r') as ske_file_id:
            trajectories_data = ske_file_id['/trajectories_data']

            # get the rows of valid skeletons
            assert worm_index_str in trajectories_data
            good = trajectories_data[worm_index_str] == worm_index

            trajectories_data = trajectories_data.loc[good]

            skeleton_id = trajectories_data['skeleton_id'].values

            try:
                # try to read the time stamps, if there are repeated or not a
                # number use the frame nuber instead
                timestamp_raw = trajectories_data['timestamp_raw'].values
                if np.any(np.isnan(timestamp_raw)) or np.any(np.diff(timestamp_raw) == 0):
                    raise ValueError
                else:
                    timestamp_raw = timestamp_raw.astype(np.int)
            except (ValueError, KeyError):
                # if the time stamp fails use the frame_number value instead
                # (the index of the mask) and return nan as the fps
                timestamp_raw = trajectories_data['frame_number'].values

            # we need to use (.values) to be able to use the & operator
            good_skeletons = (trajectories_data['has_skeleton'] == 1).values
            if use_skel_filter and 'is_good_skel' in trajectories_data:
                # only keep skeletons that where labeled as good skeletons in
                # the filtering step
                good_skeletons &= (
                    trajectories_data['is_good_skel'] == 1).values

            skeleton_id = skeleton_id[good_skeletons]
            timestamp_raw = timestamp_raw[good_skeletons]

            return skeleton_id, timestamp_raw

    def readSkeletonsData(self, skeleton_id, timestamp, micronsPerPixel):

        # use real frames to define the size of the object arrays
        self.first_frame = np.min(timestamp)
        self.last_frame = np.max(timestamp)
        self.n_frames = self.last_frame - self.first_frame + 1

        # get the apropiate index in the object array
        ind_ff = timestamp - self.first_frame

        # get the number of segments from the normalized skeleton
        with tables.File(self.file_name, 'r') as ske_file_id:
            self.n_segments = ske_file_id.get_node('/skeleton').shape[1]

        # add the data from the skeleton_id's and timestamps used
        self.timestamp = np.full(self.n_frames, -1, np.int32)
        self.skeleton_id = np.full(self.n_frames, -1, np.int32)
        self.timestamp[ind_ff] = timestamp
        self.skeleton_id[ind_ff] = skeleton_id

        # flag as segmented flags should be marked by the has_skeletons column
        self.video_info.frame_code = np.zeros(self.n_frames, np.int32)
        self.video_info.frame_code[ind_ff] = 1
        
        # initialize the rest of the arrays
        self.skeleton = np.full((self.n_frames, self.n_segments, 2), np.nan)
        self.ventral_contour = np.full(
            (self.n_frames, self.n_segments, 2), np.nan)
        self.dorsal_contour = np.full(
            (self.n_frames, self.n_segments, 2), np.nan)
        self.length = np.full(self.n_frames, np.nan)
        self.widths = np.full((self.n_frames, self.n_segments), np.nan)
        self.area = np.full(self.n_frames, np.nan)

        # read data from the skeletons table
        with tables.File(self.file_name, 'r') as ske_file_id:
            #print('reading skeletons...')
            self.skeleton[ind_ff] = ske_file_id.get_node(
                '/skeleton')[skeleton_id, :, :] * micronsPerPixel

            microsPerPixel_abs = np.mean(np.abs(micronsPerPixel))
            self.length[ind_ff] = ske_file_id.get_node(
                '/skeleton_length')[skeleton_id] * microsPerPixel_abs
            self.widths[ind_ff] = ske_file_id.get_node(
                '/contour_width')[skeleton_id, :] * microsPerPixel_abs
            
            #print('reading ventral contours...')
            self.ventral_contour[ind_ff] = ske_file_id.get_node(
                '/contour_side1')[skeleton_id, :, :] * micronsPerPixel

            #print('reading dorsal contours...')
            self.dorsal_contour[ind_ff] = ske_file_id.get_node(
                '/contour_side2')[skeleton_id, :, :] * micronsPerPixel

            #support older versions where the area is not calculated before
            if '/contour_area' in ske_file_id:
                self.area[ind_ff] = ske_file_id.get_node(
                    '/contour_area')[skeleton_id] * (microsPerPixel_abs**2)
            else:
                self.area = _h_calAreaArray(self.ventral_contour, self.dorsal_contour)


    def assertDataDim(self):
        # assertions to check the data has the proper dimensions
        #assert self.frame_number.shape[0] == self.n_frames
        assert self.timestamp.shape[0] == self.n_frames
        assert self.skeleton_id.shape[0] == self.n_frames
        assert self.video_info.frame_code.shape[0] == self.n_frames

        assert self.skeleton.shape[0] == self.n_frames
        assert self.length.shape[0] == self.n_frames
        assert self.widths.shape[0] == self.n_frames

        assert self.angles.shape[0] == self.n_frames
        assert self.area.shape[0] == self.n_frames

        assert self.skeleton.shape[2] == 2
        assert self.widths.shape[1] == self.n_segments

        assert self.ventral_contour.shape[0] == self.n_frames
        assert self.dorsal_contour.shape[0] == self.n_frames

        assert self.ventral_contour.shape[2] == 2
        assert self.dorsal_contour.shape[2] == 2

        assert self.ventral_contour.shape[1] == self.n_segments
        assert self.dorsal_contour.shape[1] == self.n_segments

        assert self.length.ndim == 1

        assert self.angles.shape[1] == self.n_segments

    def changeAxis(self):
        fields2change = [
            'skeleton',
            'widths',
            'angles',
            'ventral_contour',
            'dorsal_contour']

        for field in fields2change:
            A = getattr(self, field)
            # roll axis to have it as 49x2xn
            A = np.rollaxis(A, 0, A.ndim)
            # change the memory order so the last dimension changes slowly
            A = np.asfortranarray(A)
            # finally copy it back to the field
            setattr(self, field, A)

            #assert getattr(self, field).shape[0] == self.n_segments

    def splitWormTraj(self, split_size):

        #get the indexes to made the splits
        split_ind = np.arange(split_size, self.n_frames, split_size)
        n_splits = split_ind.size + 1

        #get the fields that will be splitted, they should be ndarrays with the same number of elements in the fisrt dimension
        fields2split = [field for field, val in self.__dict__.items() if isinstance(val, np.ndarray)]
        # check all the fields have the same number of frames in the first dimension
        assert all(getattr(self, x).shape[0] for x in fields2split)
        
        #copy the main object to initialize the smaller trajectories
        base_worm =copy.copy(self)
        #delete the ndarray fields so we don't copy large amount of data twice
        [setattr(base_worm, x, np.nan) for x in fields2split]

        #split each fields
        splitted_worms = [copy.copy(base_worm) for n in range(n_splits)]
        for field in fields2split:
            splitted_field = np.split(getattr(self, field), split_ind, axis=0)
            
            for worm_s, dat_s in zip(splitted_worms, splitted_field):
                setattr(worm_s, field, dat_s)

        #correct for first_frame, n_frames, last_Frame
        for worm_s in splitted_worms:
            worm_s.n_frames = worm_s.timestamp.size
            worm_s.first_frame = worm_s.timestamp[0]
            worm_s.last_frame = worm_s.timestamp[-1]
            worm_s.n_valid_skel = np.sum(~np.isnan(worm_s.skeleton[:, 0, 0]))

        return splitted_worms

class WormStatsClass():

    def __init__(self):
        '''get the info for each feature chategory'''
        
        feat_names_file = os.path.join(AUX_FILES_DIR, 'features_names.csv')
        #feat_names_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'aux', 'features_names.csv')
        
        self.extra_fields =  ['worm_index', 'n_frames', 'n_valid_skel', 'first_frame']
        self.features_info = pd.read_csv(feat_names_file, index_col=0)
        self.builtFeatAvgNames()  # create self.feat_avg_names

        # get files that would be used in the construction of objects
        self.feat_avg_dtype = [(x, np.float32) for x in self.feat_avg_names]
        self.feat_timeseries = list(
            self.features_info[
                self.features_info['is_time_series'] == 1].index.values)
        self.feat_timeseries_dtype = [
            (x, np.float32) for x in [
                'worm_index', 'timestamp', 'motion_modes'] + self.feat_timeseries]

        self.feat_events = list(
            self.features_info[
                self.features_info['is_time_series'] == 0].index.values)

    def builtFeatAvgNames(self):
        feat_avg_names = self.extra_fields[:]
        for feat_name, feat_info in self.features_info.iterrows():

            motion_types = ['']
            if feat_info['is_time_series']:
                motion_types += ['_foward', '_paused', '_backward']

            for mtype in motion_types:
                sub_name = feat_name + mtype
                feat_avg_names.append(sub_name)
                if feat_info['is_signed']:
                    for atype in ['_abs', '_neg', '_pos']:
                        feat_avg_names.append(sub_name + atype)

        self.feat_avg_names = feat_avg_names

    def getFieldData(worm_features, name):
        data = worm_features
        for field in name.split('.'):
            data = getattr(data, field)
        return data

    def getWormStats(self, worm_features, stat_func=np.mean):
        ''' Calculate the statistics of an object worm features, subdividing data
            into Backward/Foward/Paused and/or Positive/Negative/Absolute, when appropiated.
            The default is to calculate the mean value, but this can be changed
            using stat_func.

            Return the feature list as an ordered dictionary.
        '''
        # return data as a numpy recarray
        feat_stats = np.full(1, np.nan, dtype=self.feat_avg_dtype)

        motion_mode = worm_features._features['locomotion.motion_mode'].value
        for feat_name, feat_props in self.features_info.iterrows():
            feat_obj = feat_props['feat_name_obj']
            tmp_data = worm_features._features[feat_obj].value

            if tmp_data is None:
                feat_stats[feat_name] = np.nan

            elif isinstance(tmp_data, (int, float)):
                feat_stats[feat_name] = tmp_data

            else:
                feat_avg = self._featureStat(
                    stat_func,
                    tmp_data,
                    feat_name,
                    feat_props['is_signed'],
                    feat_props['is_time_series'],
                    motion_mode)
                for feat_avg_name in feat_avg:
                    feat_stats[feat_avg_name] = feat_avg[feat_avg_name]

        return feat_stats

    @staticmethod
    def _featureStat(
            stat_func,
            data,
            name,
            is_signed,
            is_time_series,
            motion_mode=np.zeros(0)):
        # I prefer to keep this function quite independend and pass the stats and moition_mode argument
        # rather than save those values in the class
        if data is None:
            data = np.zeros(0)

        motion_types = OrderedDict()
        motion_types['all'] = np.nan
        #print(is_time_series, type(is_time_series))
        if is_time_series:
            # if the the feature is motion type we can subdivide in Foward,
            # Paused or Backward motion
            assert motion_mode.size == data.size

            motion_types['foward'] = motion_mode == 1
            motion_types['paused'] = motion_mode == 0
            motion_types['backward'] = motion_mode == -1

        stats = OrderedDict()
        for key in motion_types:
            if key == 'all':
                valid = ~np.isnan(data)
                sub_name = name
            else:
                valid = motion_types[key]
                sub_name = name + '_' + key

            stats[sub_name] = stat_func(data[valid])
            if is_signed:
                # if the feature is signed we can subdivide in positive,
                # negative and absolute
                stats[sub_name + '_abs'] = stat_func(np.abs(data[valid]))
                stats[sub_name + '_neg'] = stat_func(data[data < 0 & valid])
                stats[sub_name + '_pos'] = stat_func(data[data > 0 & valid])
        return stats



