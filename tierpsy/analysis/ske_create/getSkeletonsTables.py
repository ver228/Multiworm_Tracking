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
import tables
import os
import cv2
import numpy as np
import pandas as pd
import json

from tierpsy.analysis.ske_create.helperIterROI import generateMoviesROI

from tierpsy.analysis.ske_create.segWormPython.mainSegworm import getSkeleton, resampleAll
from tierpsy.helper.misc import TABLE_FILTERS
#zebrafish functions, I am not sure it really works
from tierpsy.analysis.ske_create.zebrafishAnalysis import zebrafishAnalysis, zebrafishSkeleton

def _zebra_func(worm_img, skel_args, resampling_N):
    # Get zebrafish mask
    config = zebrafishAnalysis.ModelConfig(**skel_args)
    worm_mask, worm_cnt, cnt_area, cleaned_mask, head_point, smoothed_points = zebrafishAnalysis.getZebrafishMask(worm_img, config)

    if worm_mask is None:
        return None

    # Get zebrafish skeleton
    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area = zebrafishSkeleton.getZebrafishSkeleton(cleaned_mask, head_point, smoothed_points, config)

    if skeleton is None:
        return None

    # Resample skeleton and other variables
    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths = resampleAll(skeleton, cnt_side1, cnt_side2, cnt_widths, resampling_N)

    if skeleton is None or cnt_side1 is None or cnt_side2 is None:
        return None

    return skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area




def getWormMask(
        worm_img,
        threshold,
        strel_size=5,
        min_blob_area=50,
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
        worm_mask, min_blob_area=min_blob_area, roi_center_x=roi_center_x, roi_center_y=roi_center_y)

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
        worm_mask, min_blob_area=min_blob_area, roi_center_x=roi_center_x, roi_center_y=roi_center_y)

    worm_mask = np.zeros_like(worm_mask)
    cv2.drawContours(worm_mask, [worm_cnt.astype(np.int32)], 0, 1, -1)

    return worm_mask, worm_cnt, cnt_area


def binaryMask2Contour(
        worm_mask,
        min_blob_area=50,
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
        if cnt_area < min_blob_area:
            return np.zeros(0), cnt_area

    elif len(contour) > 1:
        # clean mask if there is more than one contour
        # select the largest area  object
        cnt_areas = [cv2.contourArea(cnt) for cnt in contour]

        # filter only contours with areas larger than min_blob_area and do not
        # consider contour with holes
        cnt_tuple = [(contour[ii], cnt_area) for ii, cnt_area in enumerate(
            cnt_areas) if cnt_area >= min_blob_area and hierarchy[0][ii][3] == -1] # shouldn't the last condition be automatically satisified by using RETR_EXTERNAL in cv2.findContours?

        # if there are not contour left continue
        if not cnt_tuple:
            return np.zeros(0), 0
        else:
            # get back the contour areas for filtering
            contour, cnt_areas = zip(*cnt_tuple)

        if pick_center:
            # In the multiworm tracker the worm should be in the center of the
            # ROI
            min_dist_center = np.inf
            valid_ind = -1
            for ii, cnt in enumerate(contour):
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



def _initSkeletonsArrays(ske_file_id, tot_rows, resampling_N, worm_midbody):
    '''initialize arrays to save the skeletons data.
        Used by trajectories2Skeletons
    '''

    # this is to initialize the arrays to one row, pytables do not accept empty arrays as initializers of carrays
    if tot_rows == 0:
        tot_rows = 1  
    
    #define  dimession of each array, it is the only part of the array that varies
    data_dims = {}
    for data_str in ['skeleton', 'contour_side1', 'contour_side2']:
        data_dims[data_str + '_length'] = (tot_rows,)
        data_dims[data_str] = (tot_rows, resampling_N, 2)
    data_dims['contour_width'] = (tot_rows, resampling_N)
    data_dims['width_midbody'] = (tot_rows,)
    data_dims['contour_area'] = (tot_rows,)
    
    #create and reference all the arrays
    def _create_array(field, dims):
        if '/' + field in ske_file_id:
            ske_file_id.remove_node('/', field)
            
        return ske_file_id.create_carray('/', 
                                  field, 
                                  tables.Float32Atom(dflt=np.nan), 
                                  dims, 
                                  filters=TABLE_FILTERS)
        
    skel_arrays = {field:_create_array(field, dims) for field, dims in data_dims.items()}
    
    # flags to mark if a frame was skeletonized
    traj_dat = ske_file_id.get_node('/trajectories_data')
    has_skeleton = traj_dat.cols.has_skeleton
    has_skeleton[:] = np.zeros_like(has_skeleton) #delete previous
    
    return skel_arrays, has_skeleton



def trajectories2Skeletons(skeletons_file, 
                            masked_image_file,
                            resampling_N=49, 
                            min_blob_area=50, 
                            strel_size=5, 
                            worm_midbody=(0.35, 0.65),
                            analysis_type="WORM", 
                            skel_args = {'num_segments' : 24, 
                                         'head_angle_thresh' : 60}
                            ):
    
    #get the index number for the width limit
    midbody_ind = (int(np.floor(
        worm_midbody[0]*resampling_N)), int(np.ceil(worm_midbody[1]*resampling_N)))
    
    #read trajectories data with pandas
    with pd.HDFStore(skeletons_file, 'r') as ske_file_id:
        trajectories_data = ske_file_id['/trajectories_data']
    
    # extract the base name from the masked_image_file. This is used in the
    # progress status.
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_prefix =  base_name + ' Calculating skeletons.'
        
    
    
    # open skeleton file for append and #the compressed videos as read
    with tables.File(skeletons_file, "r+") as ske_file_id:

        #attribute useful to understand if we are dealing with dark or light worms
        bgnd_param = ske_file_id.get_node('/trajectories_data')._v_attrs['bgnd_param']
        bgnd_param = json.loads(bgnd_param.decode("utf-8"))

        is_light_background = ske_file_id.get_node('/trajectories_data')._v_attrs['is_light_background']
        if len(bgnd_param) > 0:
            #invert (at least if is_light_background is true)
            is_light_background = not is_light_background

        
        #get generators to get the ROI for each frame
        ROIs_generator = generateMoviesROI(masked_image_file, 
                                         trajectories_data, 
                                         bgnd_param = bgnd_param,
                                         progress_prefix = progress_prefix)

        # add data from the experiment info (currently only for singleworm)
        with tables.File(skeletons_file, "r") as mask_fid:  
            if '/experiment_info' in ske_file_id:
                    ske_file_id.remove_node('/', 'experiment_info')
            if '/experiment_info' in mask_fid:
                dd = mask_fid.get_node('/experiment_info').read()
                ske_file_id.create_array('/', 'experiment_info', obj=dd)
        
                
        #initialize arrays to save the skeletons data
        tot_rows = len(trajectories_data)
        skel_arrays, has_skeleton = _initSkeletonsArrays(ske_file_id, tot_rows, resampling_N, worm_midbody)
        
        
        # dictionary to store previous skeletons
        prev_skeleton = {}
        
        for worms_in_frame in ROIs_generator:
            for ind, roi_dat in worms_in_frame.items():
                row_data = trajectories_data.loc[ind]
                worm_img, roi_corner = roi_dat
                skeleton_id = int(row_data['skeleton_id'])
                
                # get the previous worm skeletons to orient them
                worm_index = row_data['worm_index_joined']
                if worm_index not in prev_skeleton:
                    prev_skeleton[worm_index] = np.zeros(0)

                if analysis_type == "ZEBRAFISH":
                     output = _zebra_func(worm_img, skel_args, resampling_N)
                else:
                    _, worm_cnt, _ = getWormMask(worm_img, 
                                                 row_data['threshold'], 
                                                 strel_size,
                                                 min_blob_area=row_data['area'] / 2, 
                                                 is_light_background = is_light_background)
                    # get skeletons
                    output = getSkeleton(worm_cnt, prev_skeleton[worm_index], resampling_N, **skel_args)

                
                
                
                if output is not None and output[0].size > 0:
                    skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area = output
                    prev_skeleton[worm_index] = skeleton.copy()

                    #mark row as a valid skeleton
                    has_skeleton[skeleton_id] = True
                    
                    # save segwrom_results
                    skel_arrays['skeleton_length'][skeleton_id] = ske_len
                    skel_arrays['contour_width'][skeleton_id, :] = cnt_widths
                    
                    mid_width = np.median(cnt_widths[midbody_ind[0]:midbody_ind[1]+1])
                    skel_arrays['width_midbody'][skeleton_id] = mid_width

                    # convert into the main image coordinates
                    skel_arrays['skeleton'][skeleton_id, :, :] = skeleton + roi_corner
                    skel_arrays['contour_side1'][skeleton_id, :, :] = cnt_side1 + roi_corner
                    skel_arrays['contour_side2'][skeleton_id, :, :] = cnt_side2 + roi_corner
                    skel_arrays['contour_area'][skeleton_id] = cnt_area

        
if __name__ == '__main__':
    root_dir = '/Volumes/behavgenom$/Andre/fishVideos/'
        
    #ff = 'N2_N10_F1-3_Set1_Pos7_Ch1_12112016_024337.hdf5'
    #ff = 'unc-9_N10_F1-3_Set1_Pos1_Ch5_17112016_193814.hdf5'
    #ff = 'trp-4_N1_Set3_Pos6_Ch1_19102016_172113.hdf5'
    #ff = 'trp-4_N10_F1-1_Set1_Pos2_Ch4_02112016_201534.hdf5'
    ff = 'f3_ss_uncompressed.hdf5'
    masked_image_file = os.path.join(root_dir, 'MaskedVideos', ff)    
    skeletons_file = os.path.join(root_dir, 'Results', ff.replace('.hdf5', '_skeletons.hdf5'))
    
    json_file = os.path.join(root_dir, 'f3_ss_uncompressed.json')

    from tierpsy.helper.tracker_param import tracker_param
    params = tracker_param(json_file)



    trajectories2Skeletons(skeletons_file, masked_image_file, **params.skeletons_param)
