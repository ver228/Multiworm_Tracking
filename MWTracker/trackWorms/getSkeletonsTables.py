# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:21:39 2015

@author: ajaver
"""

# -*- coding: utf-8 -*-
"""
Created on Fri Mar 13 19:39:41 2015

@author: ajaver
"""
import pandas as pd
# h5py gives an error when I tried to do a large amount of write
# operations (~1e6)
import math
import tables
import os
import sys
import shutil
import cv2
import numpy as np

from scipy.ndimage.filters import median_filter
from scipy.signal import savgol_filter
from scipy.interpolate import interp1d

from MWTracker.helperFunctions.timeCounterStr import timeCounterStr
from MWTracker.trackWorms.segWormPython.mainSegworm import getSkeleton, resampleAll

from MWTracker.zebrafishAnalysis import zebrafishAnalysis
from MWTracker.zebrafishAnalysis import zebrafishSkeleton

# pytables filters.
TABLE_FILTERS = tables.Filters(
        complevel=5,
        complib='zlib',
        shuffle=True,
        fletcher32=True)

def getWormROI(img, CMx, CMy, roi_size=128):
    '''
    Extract a square Region Of Interest (ROI)
    img - 2D numpy array containing the data to be extracted
    CMx, CMy - coordinates of the center of the ROI
    roi_size - side size in pixels of the ROI

    -> Used by trajectories2Skeletons
    '''

    if np.isnan(CMx) or np.isnan(CMy):
        return np.zeros(0, dtype=np.uint8), np.array([np.nan] * 2)

    roi_center = int(roi_size) // 2
    roi_range = np.round(np.array([-roi_center, roi_center]))

    # obtain bounding box from the trajectories
    range_x = (CMx + roi_range).astype(np.int)
    range_y = (CMy + roi_range).astype(np.int)

    if range_x[0] < 0:
        range_x[0] = 0
    if range_y[0] < 0:
        range_y[0] = 0
    #%%
    if range_x[1] > img.shape[1]:
        range_x[1] = img.shape[1]
    if range_y[1] > img.shape[0]:
        range_y[1] = img.shape[0]

    worm_img = img[range_y[0]:range_y[1], range_x[0]:range_x[1]]

    roi_corner = np.array([range_x[0], range_y[0]])

    return worm_img, roi_corner


def getWormMask(
        worm_img,
        threshold,
        strel_size=5,
        min_mask_area=50,
        roi_center_x=-1,
        roi_center_y=-1,
        is_light_background=True):
    '''
    Calculate worm mask using an specific threshold.

    -> Used by trajectories2Skeletons
    '''

    if any(x < 3 for x in worm_img.shape):
        return np.zeros_like(worm_img), np.zeros(0), 0

    # let's make sure the strel is larger than 3 and odd, otherwise it will
    # shift the mask position.
    strel_size_half = round(strel_size / 2)
    if strel_size_half % 2 == 0:
        strel_size_half += 1
    if strel_size_half < 3:
        strel_size_half = 3

    strel_half = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (strel_size_half, strel_size_half))

    # make the worm more uniform. This is important to get smoother contours.
    worm_img = cv2.medianBlur(worm_img, 3)

    # compute the thresholded mask
    worm_mask = worm_img < threshold if is_light_background else worm_img > threshold
    worm_mask = (worm_mask & (worm_img != 0)).astype(np.uint8)
    
    # first compute a small closing to join possible fragments of the worm.
    worm_mask = cv2.morphologyEx(worm_mask, cv2.MORPH_CLOSE, strel_half)

    # then get the best contour to be the worm
    worm_cnt, _ = binaryMask2Contour(
        worm_mask, min_mask_area=min_mask_area, roi_center_x=roi_center_x, roi_center_y=roi_center_y)

    # create a new mask having only the best contour
    worm_mask = np.zeros_like(worm_mask)
    cv2.drawContours(worm_mask, [worm_cnt.astype(np.int32)], 0, 1, -1)

    # let's do closing with a larger structural element to close any gaps inside the worm.
    # It is faster to do several iterations rather than use a single larger
    # strel.
    worm_mask = cv2.morphologyEx(
        worm_mask,
        cv2.MORPH_CLOSE,
        strel_half,
        iterations=3)

    # finally get the contour from the last element
    worm_cnt, cnt_area = binaryMask2Contour(
        worm_mask, min_mask_area=min_mask_area, roi_center_x=roi_center_x, roi_center_y=roi_center_y)

    worm_mask = np.zeros_like(worm_mask)
    cv2.drawContours(worm_mask, [worm_cnt.astype(np.int32)], 0, 1, -1)

    return worm_mask, worm_cnt, cnt_area


def binaryMask2Contour(
        worm_mask,
        min_mask_area=50,
        roi_center_x=-1,
        roi_center_y=-1,
        pick_center=True):
    '''
    convert binary mask into a single work contour.

    -> Used by getWormMask
    '''
    if worm_mask.size == 0:
        return np.zeros(0), 0  # assest this is not an empty arrays

    # get the center of the mask
    if roi_center_x < 1:
        roi_center_x = (worm_mask.shape[1] - 1) / 2.
    if roi_center_y < 1:
        roi_center_y = (worm_mask.shape[0] - 1) / 2.

    # select only one contour in the binary mask
    # get contour
    _, contour, hierarchy = cv2.findContours(
        worm_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    if len(contour) == 1:
        contour = np.squeeze(contour[0], axis=1)
        # filter for small areas
        cnt_area = cv2.contourArea(contour)
        if cnt_area < min_mask_area:
            return np.zeros(0), cnt_area

    elif len(contour) > 1:
        # clean mask if there is more than one contour
        # select the largest area  object
        cnt_areas = [cv2.contourArea(cnt) for cnt in contour]

        # filter only contours with areas larger than min_mask_area and do not
        # consider contour with holes
        cnt_tuple = [(contour[ii], cnt_area) for ii, cnt_area in enumerate(
            cnt_areas) if cnt_area >= min_mask_area and hierarchy[0][ii][3] == -1] # shouldn't the last condition be automatically satisified by using RETR_EXTERNAL in cv2.findContours?

        # if there are not contour left continue
        if not cnt_tuple:
            return np.zeros(0), 0

        # get back the contour areas for filtering
        contour, cnt_areas = zip(*cnt_tuple)

        if pick_center:
            # In the multiworm tracker the worm should be in the center of the
            # ROI
            min_dist_center = np.inf
            valid_ind = -1
            for ii, cnt in enumerate(contour):
                # print(cnt.shape)
                #mm = cv2.moments(cnt)
                cm_x = np.mean(cnt[:, :, 1])  # mm['m10']/mm['m00']
                cm_y = np.mean(cnt[:, :, 0])  # mm['m01']/mm['m00']
                dist_center = (cm_x - roi_center_x)**2 + \
                    (cm_y - roi_center_y)**2
                if min_dist_center > dist_center:
                    min_dist_center = dist_center
                    valid_ind = ii
        else:
            # select the largest area  object
            valid_ind = np.argmax(cnt_areas)

        # return the correct contour if there is a valid number
        contour = np.squeeze(contour[valid_ind])
        cnt_area = cnt_areas[valid_ind]
    else:
        return np.zeros(0), 0

    return contour, cnt_area


def _getSmoothTrajectories(
        trajectories_file,
        roi_size=-1,
        min_track_size=100,
        displacement_smooth_win=101,
        threshold_smooth_win=501,
        analysis_type='WORM'):
    '''
    Smooth trajectories and thresholds created by getWormTrajectories.
    -> Used by trajectories2Skeletons
    '''

    # Use a fixed roi_size if Analysis Type is Zebrafish
    if analysis_type == 'ZEBRAFISH':
        roi_size = 200

    # a track size less than 2 will break the interp_1 function
    if min_track_size < 2:
        min_track_size = 2

    # the filter window must be odd
    if displacement_smooth_win % 2 == 0:
        displacement_smooth_win += 1

    # read that frame an select trajectories that were considered valid by
    # join_trajectories
    with pd.HDFStore(trajectories_file, 'r') as table_fid:
        df = table_fid['/plate_worms'][['worm_index_joined',
                                        'frame_number',
                                        'coord_x',
                                        'coord_y',
                                        'threshold',
                                        'bounding_box_xmax',
                                        'bounding_box_xmin',
                                        'bounding_box_ymax',
                                        'bounding_box_ymin',
                                        'area']]

        df = df[df['worm_index_joined'] > 0]

    with tables.File(trajectories_file, 'r') as fid:
        timestamp_raw = fid.get_node('/timestamp/raw')[:]
        timestamp_time = fid.get_node('/timestamp/time')[:]

    if len(timestamp_raw) < df['frame_number'].max():
        raise Exception(
            'bad %i, %i. \nFile: %s' %
            (len(timestamp_raw),
             df['frame_number'].max(),
                trajectories_file))

    tracks_data = df.groupby('worm_index_joined').aggregate(
        ['max', 'min', 'count'])

    # get the total length of the tracks, this is more accurate than using
    # count since parts of the track could have got lost for a few frames
    track_lenghts = (
        tracks_data['frame_number']['max'] -
        tracks_data['frame_number']['min'] +
        1)
    tot_rows_ini = track_lenghts[track_lenghts > min_track_size].sum()
    del track_lenghts

    # add the possibility to have variable size ROI
    if roi_size <= 0:
        # calculate the ROI size as the maximum bounding box size for a given
        # trajectory
        bb_x = df['bounding_box_xmax'] - df['bounding_box_xmin'] + 1
        bb_y = df['bounding_box_ymax'] - df['bounding_box_ymin'] + 1
        worm_lim = pd.concat([bb_x, bb_y], axis=1).max(axis=1)

        df_bb = pd.DataFrame(
            {'worm_index_joined': df['worm_index_joined'], 'roi_range': worm_lim})
        #roi_size = df_bb.groupby('worm_index').agg([max , functools.partial(np.percentile, q=0.98)])
        roi_range = df_bb.groupby('worm_index_joined').agg(max) + 10
        roi_range = dict(roi_range['roi_range'])
    else:
        roi_range = {ii: roi_size for ii in np.unique(df['worm_index_joined'])}

    # initialize output data as a numpy recarray (pytables friendly format)
    trajectories_df = np.recarray(tot_rows_ini, dtype=[('frame_number', np.int32),
                                                       ('worm_index_joined', np.int32),
                                                       ('plate_worm_id', np.int32), ('skeleton_id', np.int32),
                                                       ('coord_x', np.float32), ('coord_y', np.float32), ('threshold', np.float32),
                                                       ('has_skeleton', np.uint8), ('roi_size', np.float32), ('area', np.float32),
                                                       ('timestamp_raw', np.float32), ('timestamp_time', np.float32),
                                                       ('cnt_coord_x', np.float32), ('cnt_coord_y', np.float32), ('cnt_area', np.float32)])

    # store the maximum and minimum frame of each worm
    worms_frame_range = {}

    # smooth trajectories (reduce giggling from the CM to obtain a nicer video)
    # interpolate for possible missing frames in the trajectories
    tot_rows = 0
    for worm_index, worm_data in df.groupby('worm_index_joined'):
        x = worm_data['coord_x'].values
        y = worm_data['coord_y'].values
        t = worm_data['frame_number'].values
        thresh = worm_data['threshold'].values
        area = worm_data['area'].values

        first_frame = np.min(t)
        last_frame = np.max(t)
        worms_frame_range[worm_index] = (first_frame, last_frame)

        tnew = np.arange(first_frame, last_frame + 1, dtype=np.int32)

        if len(tnew) <= min_track_size:
            continue

        # iterpolate missing points in the trajectory and smooth data using the
        # savitzky golay filter
        fx = interp1d(t, x)
        fy = interp1d(t, y)
        xnew = fx(tnew)
        ynew = fy(tnew)

        farea = interp1d(t, area)
        areanew = farea(tnew)

        fthresh = interp1d(t, thresh)
        threshnew = fthresh(tnew)

        if len(tnew) > displacement_smooth_win and displacement_smooth_win > 3:
            xnew = savgol_filter(xnew, displacement_smooth_win, 3)
            ynew = savgol_filter(ynew, displacement_smooth_win, 3)
            areanew = median_filter(areanew, displacement_smooth_win)

        # smooth the threshold (the worm intensity shouldn't change abruptly
        # along the trajectory)
        if len(tnew) > threshold_smooth_win:
            threshnew = median_filter(threshnew, threshold_smooth_win)

        # skeleton_id useful to organize the data in the other tables
        # (skeletons, contours, etc)
        new_total = tot_rows + xnew.size
        skeleton_id = np.arange(tot_rows, new_total, dtype=np.int32)
        tot_rows = new_total

        # store the indexes in the original plate_worms table
        plate_worm_id = np.empty(xnew.size, dtype=np.int32)
        plate_worm_id.fill(-1)
        plate_worm_id[t - first_frame] = worm_data.index

        trajectories_df['worm_index_joined'][skeleton_id] = worm_index
        trajectories_df['coord_x'][skeleton_id] = xnew
        trajectories_df['coord_y'][skeleton_id] = ynew

        frame_number = np.arange(first_frame, last_frame + 1, dtype=np.int32)
        trajectories_df['frame_number'][skeleton_id] = frame_number
        trajectories_df['timestamp_raw'][
            skeleton_id] = timestamp_raw[frame_number]
        trajectories_df['timestamp_time'][
            skeleton_id] = timestamp_time[frame_number]

        trajectories_df['threshold'][skeleton_id] = threshnew
        trajectories_df['plate_worm_id'][skeleton_id] = plate_worm_id
        trajectories_df['skeleton_id'][skeleton_id] = skeleton_id
        trajectories_df['has_skeleton'][skeleton_id] = False
        trajectories_df['roi_size'][skeleton_id] = roi_range[worm_index]

        trajectories_df['area'][skeleton_id] = areanew

    trajectories_df['cnt_coord_x'] = np.nan
    trajectories_df['cnt_coord_y'] = np.nan
    trajectories_df['cnt_area'] = 0
    assert tot_rows == tot_rows_ini

    return trajectories_df, worms_frame_range, tot_rows, timestamp_raw, timestamp_time

def _initializeSkeletonsArrays(ske_file_id, tot_rows, resampling_N, worm_midbody):
    '''initialize arrays to save the skeletons data.
        Used by trajectories2Skeletons
    '''

    # this is to initialize the arrays to one row, pytables do not accept empty arrays as initializers of carrays
    if tot_rows == 0:
        tot_rows = 1  

    skel_arrays = {}
    # initialize compressed arrays to save the data. Note that the data
    # will be sorted according to trajectories_df
    for data_str in ['skeleton', 'contour_side1', 'contour_side2']:
        length_str = data_str + '_length'

        skel_arrays[length_str] = ske_file_id.create_carray(
            "/",
            length_str,
            tables.Float32Atom(
                dflt=np.nan),
            (tot_rows,
             ),
            filters=TABLE_FILTERS)

        skel_arrays[data_str] = ske_file_id.create_carray(
            "/",
            data_str,
            tables.Float32Atom(
                dflt=np.nan),
            (tot_rows,
             resampling_N,
             2),
            filters=TABLE_FILTERS,
            chunkshape=(
                1,
                resampling_N,
                2))

    skel_arrays['contour_width'] = ske_file_id.create_carray(
        '/',
        "contour_width",
        tables.Float32Atom(
            dflt=np.nan),
        (tot_rows,
         resampling_N),
        filters=TABLE_FILTERS,
        chunkshape=(
            1,
            resampling_N))

    # get the indexes that would be use in the calculation of the worm
    # midbody width
    skel_arrays['width_midbody'] = ske_file_id.create_carray(
        "/",
        'width_midbody',
        tables.Float32Atom(
            dflt=np.nan),
        (tot_rows,
         ),
        filters=TABLE_FILTERS)

    #array with the countour areas
    skel_arrays['contour_area'] = ske_file_id.create_carray(
        '/',
        "contour_area",
        tables.Float32Atom(
            dflt=np.nan),
        (tot_rows,
         ),
        filters=TABLE_FILTERS)

    # flag to mark if this function finished succesfully
    skel_arrays['skeleton']._v_attrs['has_finished'] = 0

    return skel_arrays

def _getSaveTrajectoriesData(trajectories_file, skeletons_file, masked_image_file, smoothed_traj_param):
    
    #create a smoothed trajectories table from the trajectories file
    trajectories_df, _, tot_rows, timestamp_raw, timestamp_time = \
        _getSmoothTrajectories(trajectories_file, **smoothed_traj_param)

    # pytables saving format is more convenient...
    with tables.File(skeletons_file, "w") as ske_file_id, tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")
        ske_file_id.create_table(
            '/',
            'trajectories_data',
            obj=trajectories_df,
            filters=TABLE_FILTERS)

        #save some extra info as attributes in the trajectories_data

        # save a copy of the video timestamp data
        ske_file_id.create_group('/', 'timestamp')
        ske_file_id.create_carray('/timestamp', 'raw', obj=timestamp_raw)
        ske_file_id.create_carray('/timestamp', 'time', obj=timestamp_time)

        #read and the pixel information
        trajectories_data = ske_file_id.get_node('/trajectories_data')
        if 'pixels2microns_x' in mask_dataset._v_attrs:
            trajectories_data._v_attrs['pixels2microns_x'] = \
                            mask_dataset._v_attrs['pixels2microns_x']
            trajectories_data._v_attrs['pixels2microns_y'] = \
                            mask_dataset._v_attrs['pixels2microns_y']

        #find if it is a mask from fluorescence and save it in the new group
        is_light_background = 1 if not 'is_light_background' in mask_dataset._v_attrs \
                        else mask_dataset._v_attrs['is_light_background']
        trajectories_data._v_attrs['is_light_background'] = is_light_background


    #...but it is easier to process data with pandas
    with pd.HDFStore(skeletons_file, 'r') as ske_file_id:
        trajectories_df = ske_file_id['/trajectories_data']
        trajectories_df['area_new'] = np.nan
        trajectories_df['coord_x_new'] = np.nan
        trajectories_df['coord_y_new'] = np.nan

    return trajectories_df



def _getTrajFields(ske_file_id):
    '''
    Read some columns fields from the trajectories file that will be modified
    '''

    # flags to mark if a frame was skeletonized
    has_skeleton = ske_file_id.get_node(
        '/trajectories_data').cols.has_skeleton

    # get the center of mass coordinates and area of the contour with the
    # corrected threshold
    cnt_coord_x = ske_file_id.get_node(
        '/trajectories_data').cols.cnt_coord_x
    cnt_coord_y = ske_file_id.get_node(
        '/trajectories_data').cols.cnt_coord_y
    cnt_areas = ske_file_id.get_node('/trajectories_data').cols.cnt_area

    return has_skeleton, cnt_coord_x, cnt_coord_y, cnt_areas


    

def trajectories2Skeletons(masked_image_file, skeletons_file, trajectories_file, create_single_movies=False,
    resampling_N=49, min_mask_area=50, strel_size=5, smoothed_traj_param={}, worm_midbody=(0.35, 0.65),
    analysis_type="WORM", zf_num_segments=12, zf_min_angle=-90, zf_max_angle=90, zf_num_angles=90, zf_tail_length=60,
    zf_tail_detection='MODEL_END_POINT', zf_prune_retention=1, zf_test_width=2, zf_draw_width=2,
    zf_auto_detect_tail_length=True):

    #get the index number for the width limit
    midbody_ind = (int(np.floor(
        worm_midbody[0]*resampling_N)), int(np.ceil(worm_midbody[1]*resampling_N)))
    
    # extract the base name from the masked_image_file. This is used in the
    # progress status.
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]

    # get trajectories, threshold and indexes from the first part of the tracker.
    # Note that data is sorted by worm index. This speed up access for access
    # individual worm data.
    trajectories_df = _getSaveTrajectoriesData(trajectories_file, skeletons_file, masked_image_file, smoothed_traj_param)
    tot_rows = len(trajectories_df)
    
    # open skeleton file for append and #the compressed videos as read
    with tables.File(skeletons_file, "r+") as ske_file_id, \
            tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")

        #initialize arrays to save the skeletons data
        skel_arrays = _initializeSkeletonsArrays(ske_file_id, tot_rows, resampling_N, worm_midbody)
        
        #get some files to be modified and flags
        has_skeleton, cnt_coord_x, cnt_coord_y, cnt_areas = _getTrajFields(ske_file_id)

        #attribute useful to understand if we are dealing with dark or light worms
        is_light_background = ske_file_id.get_node('/trajectories_data')._v_attrs['is_light_background']

        
        # dictionary to store previous skeletons
        prev_skeleton = {}


        # timer
        progressTime = timeCounterStr('Calculating skeletons.')
        for frame, frame_data in trajectories_df.groupby('frame_number'):
            img = mask_dataset[frame, :, :]
            for skeleton_id, row_data in frame_data.iterrows():

                worm_img, roi_corner = getWormROI(
                    img, row_data['coord_x'], row_data['coord_y'], row_data['roi_size'])


                # get the previous worm skeletons to orient them
                worm_index = row_data['worm_index_joined']
                if worm_index not in prev_skeleton:
                    prev_skeleton[worm_index] = np.zeros(0)


                if analysis_type == "WORM":

                    worm_mask, worm_cnt, cnt_area = getWormMask(
                        worm_img, row_data['threshold'], strel_size,
                        min_mask_area=row_data['area'] / 2, is_light_background = is_light_background)

                    if worm_cnt.size == 0:
                        continue

                    # get skeletons
                    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area = \
                        getSkeleton(worm_cnt, prev_skeleton[worm_index], resampling_N)

                elif analysis_type == "ZEBRAFISH":

                    # Get zebrafish mask
                    config = zebrafishAnalysis.ModelConfig(zf_num_segments, zf_min_angle, zf_max_angle, zf_num_angles, zf_tail_length, zf_tail_detection, zf_prune_retention, zf_test_width, zf_draw_width, zf_auto_detect_tail_length)
                    worm_mask, worm_cnt, cnt_area, cleaned_mask, head_point, smoothed_points = zebrafishAnalysis.getZebrafishMask(worm_img, config)

                    if worm_mask == None:
                        continue

                    # Get zebrafish skeleton
                    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area = zebrafishSkeleton.getZebrafishSkeleton(cleaned_mask, head_point, smoothed_points, config)

                    if skeleton == None:
                        continue

                    # Resample skeleton and other variables
                    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths = resampleAll(skeleton, cnt_side1, cnt_side2, cnt_widths, resampling_N)

                    if skeleton == None or cnt_side1 == None or cnt_side2 == None:
                        continue


                cnt_areas[skeleton_id] = cnt_area
                # calculate the mask center of mask and store it
                cnt_coord_y[skeleton_id] = np.mean(
                    worm_cnt[:, 1]) + roi_corner[1]
                cnt_coord_x[skeleton_id] = np.mean(
                    worm_cnt[:, 0]) + roi_corner[0]


                if skeleton.size > 0:
                    prev_skeleton[worm_index] = skeleton.copy()

                    # save segwrom_results
                    skel_arrays['skeleton_length'][skeleton_id] = ske_len
                    skel_arrays['contour_width'][skeleton_id, :] = cnt_widths
                    skel_arrays['width_midbody'][skeleton_id] = np.median(
                        cnt_widths[midbody_ind[0]:midbody_ind[1] + 1])

                    # convert into the main image coordinates
                    skel_arrays['skeleton'][skeleton_id, :, :] = skeleton + roi_corner
                    skel_arrays['contour_side1'][skeleton_id, :, :] = cnt_side1 + roi_corner
                    skel_arrays['contour_side2'][skeleton_id, :, :] = cnt_side2 + roi_corner
                    skel_arrays['contour_area'][skeleton_id] = cnt_area

                    has_skeleton[skeleton_id] = True

            if frame % 500 == 0:
                progress_str = progressTime.getStr(frame)
                print(base_name + ' ' + progress_str)
                sys.stdout.flush()

        # add data from the experiment info (currently only for singleworm)
        if '/experiment_info' in mask_fid:
            dd = mask_fid.get_node('/experiment_info').read()
            ske_file_id.create_array('/', 'experiment_info', obj=dd)

        # FINISH!!!
        # Mark a succesful termination
        skel_arrays['skeleton']._v_attrs['has_finished'] = 1
