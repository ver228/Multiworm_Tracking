# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:33:34 2015

@author: ajaver
"""


import numpy as np
import tables
from math import sqrt
import cv2
from skimage.filters import threshold_otsu
import os
import sys

from sklearn.utils.linear_assignment_ import linear_assignment  # hungarian algorithm
from scipy.spatial.distance import cdist

from MWTracker.helperFunctions.timeCounterStr import timeCounterStr
from MWTracker.compressVideos.extractMetaData import readAndSaveTimestamp

table_filters = tables.Filters(complevel=5, complib='zlib', shuffle=True)


class plate_worms(tables.IsDescription):
    # class for the pytables
    worm_index_blob = tables.Int32Col(pos=0)
    worm_index_joined = tables.Int32Col(pos=1)

    frame_number = tables.Int32Col(pos=2)
    coord_x = tables.Float32Col(pos=3)
    coord_y = tables.Float32Col(pos=4)
    area = tables.Float32Col(pos=5)
    perimeter = tables.Float32Col(pos=6)
    box_length = tables.Float32Col(pos=7)
    box_width = tables.Float32Col(pos=8)
    quirkiness = tables.Float32Col(pos=9)
    compactness = tables.Float32Col(pos=10)
    box_orientation = tables.Float32Col(pos=11)
    solidity = tables.Float32Col(pos=12)
    intensity_mean = tables.Float32Col(pos=13)
    intensity_std = tables.Float32Col(pos=14)

    threshold = tables.Int32Col(pos=15)
    bounding_box_xmin = tables.Int32Col(pos=16)
    bounding_box_xmax = tables.Int32Col(pos=17)
    bounding_box_ymin = tables.Int32Col(pos=18)
    bounding_box_ymax = tables.Int32Col(pos=19)

    # deprecated, probably it would be good to remove it in the future
    segworm_id = tables.Int32Col(pos=20)

    hu0 = tables.Float32Col(pos=21)
    hu1 = tables.Float32Col(pos=22)
    hu2 = tables.Float32Col(pos=23)
    hu3 = tables.Float32Col(pos=24)
    hu4 = tables.Float32Col(pos=25)
    hu5 = tables.Float32Col(pos=26)
    hu6 = tables.Float32Col(pos=27)


def _getWormThreshold(pix_valid):

    # calculate otsu_threshold as lower limit. Otsu understimates the threshold.
    try:
        otsu_thresh = threshold_otsu(pix_valid)
    except:
        return np.nan

    # calculate the histogram
    pix_hist = np.bincount(pix_valid)

    # the higher limit is the most frequent value in the distribution
    # (background)
    largest_peak = np.argmax(pix_hist)
    if otsu_thresh < largest_peak and otsu_thresh + 2 < len(pix_hist) - 1:
        # smooth the histogram to find a better threshold
        pix_hist = np.convolve(pix_hist, np.ones(3), 'same')
        cumhist = np.cumsum(pix_hist)

        xx = np.arange(otsu_thresh, cumhist.size)
        try:
            # the threshold is calculated as the first pixel level above the otsu threshold 
            # at which there would be larger increase in the object area.
            hist_ratio = pix_hist[xx] / cumhist[xx]
            thresh = np.where(
                (hist_ratio[3:] - hist_ratio[:-3]) > 0)[0][0] + otsu_thresh
        except IndexError:
            thresh = np.argmin(
                pix_hist[
                    otsu_thresh:largest_peak]) + otsu_thresh
    else:
        # if otsu is larger than the maximum peak keep otsu threshold
        thresh = otsu_thresh

    return thresh


def _getWormContours(ROI_image, threshold, strel_size=(5, 5), is_light_background=True):
    # get the border of the ROI mask, this will be used to filter for valid
    # worms
    ROI_valid = (ROI_image != 0).astype(np.uint8)
    _, ROI_border_ind, _ = cv2.findContours(
        ROI_valid, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    if len(ROI_border_ind) <= 1:
        valid_ind = 0
    else:
        # consider the case where there is more than one contour in the blob
        # i.e. there is a neighboring ROI in the square, just keep the largest area
        ROI_area = [cv2.contourArea(x) for x in ROI_border_ind]
        valid_ind = np.argmax(ROI_area)
        ROI_valid = np.zeros_like(ROI_valid)
        ROI_valid = cv2.drawContours(
            ROI_valid, ROI_border_ind, valid_ind, 1, -1)
        ROI_image = ROI_image * ROI_valid

    # get binary image, 
    ROI_mask = ROI_image < threshold if is_light_background else ROI_image > threshold
    ROI_mask = (ROI_mask & (ROI_image != 0)).astype(np.uint8)
    
    # clean it using morphological closing - make this optional by setting strel_size to 0
    if np.all(strel_size):
        strel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, strel_size)
        ROI_mask = cv2.morphologyEx(ROI_mask, cv2.MORPH_CLOSE, strel)

    # get worms, assuming each contour in the ROI is a worm
    [_, ROI_worms, hierarchy] = cv2.findContours(
        ROI_mask.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    return ROI_worms, hierarchy


def _getWormFeatures(
        worm_cnt,
        ROI_image,
        ROI_bbox,
        current_frame,
        thresh,
        min_area):
    SEGWORM_ID_DEFAULT = -1  # default value for the column segworm_id

    area = float(cv2.contourArea(worm_cnt))
    if area < min_area:
        return None  # area too small to be a worm

    worm_bbox = cv2.boundingRect(worm_cnt)
    # find use the best rotated bounding box, the fitEllipse function produces bad results quite often
    # this method is better to obtain an estimate of the worm length than
    # eccentricity
    (CMx, CMy), (L, W), angle = cv2.minAreaRect(worm_cnt)
    
    if L == 0 or W == 0:
        return None #something went wrong abort
    
    if W > L:
        L, W = W, L  # switch if width is larger than length
    quirkiness = sqrt(1 - W**2 / L**2)

    hull = cv2.convexHull(worm_cnt)  # for the solidity
    solidity = area / cv2.contourArea(hull)
    perimeter = float(cv2.arcLength(worm_cnt, True))
    compactness = 4 * np.pi * area / (perimeter**2)

    # calculate the mean intensity of the worm
    worm_mask = np.zeros(ROI_image.shape, dtype=np.uint8)
    cv2.drawContours(worm_mask, [worm_cnt], 0, 255, -1)
    intensity_mean, intensity_std = cv2.meanStdDev(ROI_image, mask=worm_mask)

    # calculate hu moments, they are scale and rotation invariant
    hu_moments = cv2.HuMoments(cv2.moments(worm_cnt))

    # save everything into the the proper output format
    mask_feat = (
        current_frame,
        CMx +
        ROI_bbox[0],
        CMy +
        ROI_bbox[1],
        area,
        perimeter,
        L,
        W,
        quirkiness,
        compactness,
        angle,
        solidity,
        intensity_mean[
            0,
            0],
        intensity_std[
            0,
            0],
        thresh,
        ROI_bbox[0] +
        worm_bbox[0],
        ROI_bbox[0] +
        worm_bbox[0] +
        worm_bbox[2],
        ROI_bbox[1] +
        worm_bbox[1],
        ROI_bbox[1] +
        worm_bbox[1] +
        worm_bbox[3],
        SEGWORM_ID_DEFAULT,
        *
        hu_moments)

    return mask_feat


def _joinConsecutiveFrames(
        index_list_prev,
        coord,
        coord_prev,
        area,
        area_prev,
        tot_worms,
        max_allowed_dist,
        area_ratio_lim):
    # TODO probably it is better to convert the whole getWormTrajectories
    # function into a class for clearity
    if coord_prev.size != 0:
        costMatrix = cdist(coord_prev, coord)  # calculate the cost matrix
        # costMatrix[costMatrix>MA] = 1e10 #eliminate things that are farther
        # use the hungarian algorithm
        assigment = linear_assignment(costMatrix)

        index_list = np.zeros(coord.shape[0], dtype=np.int)

        # Final assigment. Only allow assigments within a maximum allowed
        # distance, and an area ratio
        for row, column in assigment:
            if costMatrix[row, column] < max_allowed_dist:
                area_ratio = area[column] / area_prev[row]

                if area_ratio > area_ratio_lim[
                        0] and area_ratio < area_ratio_lim[1]:
                    index_list[column] = index_list_prev[row]

        # add a new index if no assigment was found
        unmatched = index_list == 0
        vv = np.arange(1, np.sum(unmatched) + 1) + tot_worms
        if vv.size > 0:
            tot_worms = vv[-1]
            index_list[unmatched] = vv
    else:
        # initialize worm indexes
        index_list = tot_worms + np.arange(1, len(area) + 1)
        tot_worms = index_list[-1]

    index_list = tuple(index_list)
    return index_list, tot_worms


def getWormTrajectories(
    masked_image_file,
    trajectories_file,
    initial_frame=0,
    last_frame=-1,
    min_area=25,
    min_box_width=5,
    max_allowed_dist=20,
    area_ratio_lim=(
        0.5,
        2),
        buffer_size=25,
        worm_bw_thresh_factor=1.,
        strel_size=(
            5,
        5),
    analysis_type="WORM"):
    '''
    #read images from 'masked_image_file', and save the linked trajectories and their features into 'trajectories_file'
    #use the first 'total_frames' number of frames, if it is equal -1, use all the frames in 'masked_image_file'
    min_area -- min area of the segmented worm
    min_box_width -- min size of the bounding box in the ROI of the compressed image
    max_allowed_dist -- maximum allowed distance between to consecutive trajectories
    area_ratio_lim -- allowed range between the area ratio of consecutive frames
    worm_bw_thresh_factor -- The calculated threshold will be multiplied by this factor. Desperate attempt to solve for the swimming case.
    '''

    # check that the mask file is correct
    if not os.path.exists(masked_image_file):
        raise Exception('HDF5 Masked Image file does not exists.')

    with tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")
        if 'has_finished' in mask_dataset._v_attrs and not mask_dataset._v_attrs[
                'has_finished'] >= 1:
            raise Exception('HDF5 Masked Image was not finished correctly.')
        if mask_dataset.shape[0] == 0:
            raise Exception(
                'Empty set in masked image file. Nothing to do here.')

    # intialize variables
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_str = '####'

    with tables.File(masked_image_file, 'r') as mask_fid, \
            tables.open_file(trajectories_file, mode='w') as feature_fid:
        mask_dataset = mask_fid.get_node("/mask")
        
        max_pix_allowed = np.iinfo(mask_dataset.dtype).max

        feature_table = feature_fid.create_table(
            '/',
            "plate_worms",
            plate_worms,
            "Worm feature List",
            filters=table_filters)

        # flag used to determine if the function finished correctly
        feature_table._v_attrs['has_finished'] = 0
        
        #find if it is a mask from fluorescence and save it in the new group
        is_light_background = 1 if not 'is_light_background' in mask_dataset._v_attrs \
                            else mask_dataset._v_attrs['is_light_background']
        feature_table._v_attrs['is_light_background'] = is_light_background

        #if the number of frames is not given use all the frames in the mask dataset
        if last_frame <= 0:
            last_frame = mask_dataset.shape[0]

        # initialized variables
        tot_worms = 0
        buff_last_coord, buff_last_index, buff_last_area = (np.empty([0]),) * 3

        progressTime = timeCounterStr('Calculating trajectories.')
        for frame_number in range(initial_frame, last_frame, buffer_size):

            # load image buffer
            image_buffer = mask_dataset[
                frame_number:(
                    frame_number + buffer_size), :, :]

            # select pixels as connected regions that were selected as worms at
            # least once in the masks
            main_mask = np.any(image_buffer, axis=0)

            # change from bool to uint since same datatype is required in
            # opencv
            main_mask = main_mask.astype(np.uint8)

            [_, ROI_cnts, hierarchy] = cv2.findContours(
                main_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE) # why is this using RETR_CCOMP here?

            buffer_features = []
            last_frame_features = []
            # examinate each region of interest
            for ROI_cnt in ROI_cnts:
                ROI_bbox = cv2.boundingRect(ROI_cnt)
                # bounding box too small to be a worm
                if ROI_bbox[1] < min_box_width or ROI_bbox[3] < min_box_width:
                    continue

                # select ROI for all buffer slides and apply a median filter to reduce rough edges / sharpen the boundary btw worm and background
                ROI_buffer = image_buffer[
                    :,
                    ROI_bbox[1]:(
                        ROI_bbox[1] +
                        ROI_bbox[3]),
                    ROI_bbox[0]:(
                        ROI_bbox[0] +
                        ROI_bbox[2])]
                ROI_buffer_med = np.zeros_like(ROI_buffer)
                for ii in range(ROI_buffer.shape[0]):
                    ROI_buffer_med[ii] = cv2.medianBlur(ROI_buffer[ii], 3)

                # calculate threshold using the nonzero pixels.  Using the
                # buffer instead of a single image, improves the threshold
                # calculation, since better statistics are recoverd
                pix_valid = ROI_buffer_med[ROI_buffer_med != 0]
                if pix_valid.size == 0:
                    # no valid pixels in this buffer, nothing to do here
                    continue
                # caculate threshold
                if analysis_type == "WORM":

                    if is_light_background:
                        thresh = _getWormThreshold(pix_valid)
                    else:
                        #invert pixel values
                        thresh = _getWormThreshold(max_pix_allowed - pix_valid)
                        thresh = max_pix_allowed - thresh

                    thresh *= worm_bw_thresh_factor

                elif analysis_type == "ZEBRAFISH":

                    # Override threshold and min_area
                    thresh = 255
                    min_area = 30

                if buff_last_coord.size != 0:
                    # select data from previous trajectories only within the contour bounding box.
                    # used to link with the previous chunks (buffers)
                    good = (buff_last_coord[:, 0] > ROI_bbox[0]) & \
                        (buff_last_coord[:, 1] > ROI_bbox[1]) & \
                        (buff_last_coord[:, 0] < ROI_bbox[0] + ROI_bbox[2]) & \
                        (buff_last_coord[:, 1] < ROI_bbox[1] + ROI_bbox[3])

                    coord_prev = buff_last_coord[good, :]
                    area_prev = buff_last_area[good]
                    index_list_prev = buff_last_index[good]

                else:
                    # if it is the first buffer, reinitiailize all the
                    # variables
                    coord_prev, area_prev, index_list_prev = (
                        np.empty([0]),) * 3

                for buff_ind in range(image_buffer.shape[0]):
                    # get the contour of possible worms
                    ROI_worms, hierarchy = _getWormContours(
                        ROI_buffer_med[buff_ind, :, :], thresh, strel_size, is_light_background)

                    current_frame = frame_number + buff_ind
                    frame_features = []
                    for worm_ind, worm_cnt in enumerate(ROI_worms):
                        # ignore contours from holes
                        if hierarchy[0][worm_ind][3] != -1:
                            continue

                        # obtain features for each worm
                        mask_features = _getWormFeatures(
                            worm_cnt,
                            ROI_buffer[
                                buff_ind,
                                :,
                                :],
                            ROI_bbox,
                            current_frame,
                            thresh,
                            min_area)

                        # append worm features.
                        if mask_features is not None:
                            frame_features.append(mask_features)

                    if len(frame_features) > 0:
                        frame_features = list(zip(*frame_features))

                        coord = np.array(frame_features[1:3]).T
                        area = np.array(frame_features[3]).T.astype(np.float)

                        index_list, tot_worms = _joinConsecutiveFrames(
                            index_list_prev, coord, coord_prev, area, area_prev, tot_worms, max_allowed_dist, area_ratio_lim)

                        # append the new feature list to the pytable
                        # used to leave space for worm_index_joined
                        dum_column = len(index_list) * (-1,)
                        frame_features = list(
                            zip(*([index_list, dum_column] + frame_features)))
                        buffer_features += frame_features

                        if buff_ind == image_buffer.shape[0] - 1:
                            # add only features if it is the last frame in the
                            # list
                            last_frame_features += frame_features
                    else:
                        # consider the case where not valid coordinates where
                        # found
                        coord = np.empty([0])
                        area = np.empty([0])
                        index_list = []

                    # save the features for the linkage to the next frame in
                    # the buffer
                    coord_prev, area_prev, index_list_prev = coord, area, index_list

            # save the features for the linkage to the next buffer
            last_frame_features = list(zip(*last_frame_features))
            buff_last_coord = np.array(last_frame_features[3:5]).T
            buff_last_index = np.array(last_frame_features[0:1]).T
            buff_last_area = np.array(last_frame_features[5:6]).T

            # append data to pytables
            if buffer_features:
                feature_table.append(buffer_features)

            if frame_number % 1000 == 0:
                feature_fid.flush()

            if frame_number % 500 == 0:
                # calculate the progress and put it in a string
                progress_str = progressTime.getStr(frame_number)
                print(base_name + ' ' + progress_str)
                sys.stdout.flush()
        # flush any remaining and create indexes
        feature_table.flush()
        feature_table.cols.frame_number.create_csindex()  # make searches faster
        feature_table.cols.worm_index_blob.create_csindex()
        feature_table.flush()

    readAndSaveTimestamp(masked_image_file, trajectories_file)
    with tables.open_file(trajectories_file, mode='r+') as feature_fid:
        # flag used to determine if the function finished correctly
        feature_fid.get_node('/plate_worms')._v_attrs['has_finished'] = 1

    print(base_name + ' ' + progress_str)
    sys.stdout.flush()
