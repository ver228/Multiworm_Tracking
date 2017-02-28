# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 16:33:34 2015

@author: ajaver
"""

import os
from math import sqrt

import cv2
import numpy as np
import tables
import pandas as pd
import skimage.filters as skf
import skimage.morphology as skm

from MWTracker.analysis.compress.extractMetaData import read_and_save_timestamp
from MWTracker.helper.timeCounterStr import timeCounterStr
from MWTracker.helper.misc import TABLE_FILTERS, print_flush

from functools import partial
import multiprocessing as mp
    
def _thresh_bw(pix_valid):
    # calculate otsu_threshold as lower limit. Otsu understimates the threshold.
    try:
        otsu_thresh = skf.threshold_otsu(pix_valid)
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

def _thresh_bodywallmuscle(pix_valid):
    pix_mean = np.mean(pix_valid)
    pix_median = np.median(pix_valid)
    # when fluorescent worms are present, the distribution of pixels should be asymmetric, with a peak at low values corresponding to the background
    if pix_mean > pix_median*1.1: # alternatively, could use scipy.stats.skew and some threshold, like >1/2
        thresh = pix_mean
    else: # try usual thresholding otherwise
        thresh = 255 - _thresh_bw(255 - pix_valid) #correct for fluorescence images
    return thresh

def getBufferThresh(ROI_buffer, worm_bw_thresh_factor, is_light_background, analysis_type):
    ''' calculate threshold using the nonzero pixels.  Using the
     buffer instead of a single image, improves the threshold
     calculation, since better statistics are recovered'''
     
    if analysis_type == "ZEBRAFISH":
        # Override threshold
        thresh = 255
    else: 
        pix_valid = ROI_buffer[ROI_buffer != 0]


        if pix_valid.size > 0:
            if is_light_background:
                thresh = _thresh_bw(pix_valid)
            else:
                if if analysis_type == "WORM":
                    thresh = _thresh_bodywallmuscle(pix_valid)
                else:
                    #correct for fluorescence images
                    MAX_PIX = 255 #for uint8 images
                    thresh = _thresh_bw(MAX_PIX - pix_valid)
                    thresh = MAX_PIX - thresh

            thresh *= worm_bw_thresh_factor
        else:
            thresh = np.nan
    
    return thresh


def _remove_corner_blobs(ROI_image):
    #remove blobs specially in the corners that could be part of other ROI
    # get the border of the ROI mask, this will be used to filter for valid
    # worms
    ROI_valid = (ROI_image != 0).astype(np.uint8)
    _, ROI_border_ind, _ = cv2.findContours(ROI_valid, 
                                            cv2.RETR_EXTERNAL, 
                                            cv2.CHAIN_APPROX_NONE)

    if len(ROI_border_ind) > 1:
        # consider the case where there is more than one contour in the blob
        # i.e. there is a neighboring ROI in the square, just keep the largest area
        ROI_area = [cv2.contourArea(x) for x in ROI_border_ind]
        valid_ind = np.argmax(ROI_area)
        ROI_valid = np.zeros_like(ROI_valid)
        ROI_valid = cv2.drawContours(ROI_valid, ROI_border_ind, valid_ind, 1, -1)
        ROI_image = ROI_image * ROI_valid

    return ROI_image

def _get_blob_mask(ROI_image, thresh, thresh_block_size, is_light_background, analysis_type):
    # get binary image, 
    if is_light_background:
        ## apply a median filter to reduce rough edges / sharpen the boundary btw worm and background
        ROI_image_th = cv2.medianBlur(ROI_image, 3)
        ROI_mask = ROI_image_th < thresh
    else:
        if analysis_type == "PHARYNX":
            # for fluorescent pharynx labeled images, refine the threshold with a local otsu (http://scikit-image.org/docs/dev/auto_examples/plot_local_otsu.html)
            # this compensates for local variations in brightness in high density regions, when many worms are close to each other
            ROI_rank_otsu = skf.rank.otsu(ROI_image, skm.disk(thresh_block_size))
            ROI_mask = (ROI_image>ROI_rank_otsu)
            # as a local threshold introcudes artifacts at the edge of the mask, also use a global threshold to cut these out
            ROI_mask &= (ROI_image>=thresh)
        else:
            # this case applies for example to worms where the whole body is fluorecently labeled
            ROI_image_th = cv2.medianBlur(ROI_image, 3)
            ROI_mask = ROI_image_th >= thresh
        
    ROI_mask &= (ROI_image != 0)
    ROI_mask = ROI_mask.astype(np.uint8)

    return ROI_mask, thresh # returning thresh here seems redundant, as it isn't actually changed



def getBlobContours(ROI_image, 
                    thresh, 
                    strel_size=(5, 5), 
                    is_light_background=True, 
                    analysis_type="WORM", 
                    thresh_block_size=15):

    
    ROI_image = _remove_corner_blobs(ROI_image)
    ROI_mask, thresh = _get_blob_mask(ROI_image, thresh, thresh_block_size, is_light_background, analysis_type)
    
    # clean it using morphological closing - make this optional by setting strel_size to 0
    if np.all(strel_size):
        strel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, strel_size)
        ROI_mask = cv2.morphologyEx(ROI_mask, cv2.MORPH_CLOSE, strel)

    # get worms, assuming each contour in the ROI is a worm
    _, ROI_worms, hierarchy = cv2.findContours(ROI_mask, 
                                               cv2.RETR_EXTERNAL, 
                                               cv2.CHAIN_APPROX_NONE)

    return ROI_worms, hierarchy


def getBlobDimesions(worm_cnt, ROI_bbox):
    
    area = float(cv2.contourArea(worm_cnt))
    
    worm_bbox = cv2.boundingRect(worm_cnt)
    bounding_box_xmin = ROI_bbox[0] + worm_bbox[0]
    bounding_box_xmax = bounding_box_xmin + worm_bbox[2]
    bounding_box_ymin = ROI_bbox[1] + worm_bbox[1]
    bounding_box_ymax = bounding_box_ymin + worm_bbox[3]

    # save everything into the the proper output format
    blob_bbox =(bounding_box_xmin, 
                bounding_box_xmax,
                bounding_box_ymin,
                bounding_box_ymax)


    (CMx, CMy), (L, W), angle = cv2.minAreaRect(worm_cnt)
    #adjust CM from the ROI reference frame to the image reference
    CMx += ROI_bbox[0]
    CMy += ROI_bbox[1]

    if W > L:
        L, W = W, L  # switch if width is larger than length
    
    blob_dims = (CMx, CMy, L, W, angle)
    return blob_dims, area, blob_bbox
    
def generateROIBuff(masked_image_file, buffer_size, blob_params):
    
    
    with tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node("/mask")
        for frame_number in range(0, mask_dataset.shape[0], buffer_size):
            # load image buffer
            ini = frame_number
            fin = (frame_number+buffer_size)
            image_buffer = mask_dataset[ini:fin, :, :]
            
            
            # z projection and select pixels as connected regions that were selected as worms at
            # least once in the masks
            main_mask = np.any(image_buffer, axis=0)

            # change from bool to uint since same datatype is required in
            # opencv
            main_mask = main_mask.astype(np.uint8)

            #calculate the contours, only keep the external contours (no holes) and 
            _, ROI_cnts, _ = cv2.findContours(main_mask, 
                                                      cv2.RETR_EXTERNAL, 
                                                      cv2.CHAIN_APPROX_NONE)

            yield ROI_cnts, image_buffer, frame_number
            
           

def getBlobsData(buff_data, blob_params):
    
    #I packed input data to be able top to map the function into generateROIBuff
    ROI_cnts, image_buffer, frame_number = buff_data
    
    is_light_background, min_area, min_box_width, worm_bw_thresh_factor, \
    strel_size, analysis_type, thresh_block_size = blob_params
    
    blobs_data = []
    # examinate each region of interest
    for ROI_cnt in ROI_cnts:
        ROI_bbox = cv2.boundingRect(ROI_cnt)
        # bounding box too small to be a worm - ROI_bbox[2] and [3] are width and height
        if ROI_bbox[2] > min_box_width and ROI_bbox[3] > min_box_width:
            # select ROI for all buffer slides 
            ini_x = ROI_bbox[1]
            fin_x = ini_x + ROI_bbox[3]
            ini_y = ROI_bbox[0]
            fin_y = ini_y + ROI_bbox[2]
            ROI_buffer = image_buffer[:, ini_x:fin_x, ini_y:fin_y]

            # calculate threshold
            thresh_buff = getBufferThresh(ROI_buffer, worm_bw_thresh_factor, is_light_background, analysis_type)
            
            for buff_ind in range(image_buffer.shape[0]):
                curr_ROI = ROI_buffer[buff_ind, :, :]
    
                # get the contour of possible worms
                ROI_worms, hierarchy = getBlobContours(curr_ROI, 
                                                        thresh_buff, 
                                                        strel_size, 
                                                        is_light_background,
                                                        analysis_type, 
                                                        thresh_block_size)
                current_frame = frame_number + buff_ind
        
                for worm_ind, worm_cnt in enumerate(ROI_worms):
                    # ignore contours from holes. This shouldn't occur with the flag RETR_EXTERNAL
                    assert hierarchy[0][worm_ind][3] == -1
                        
    
                    # obtain features for each worm
                    blob_dims, area, blob_bbox = getBlobDimesions(worm_cnt, ROI_bbox)
                    
                    if area >= min_area:
                        # append data to pytables only if the object is larget than min_area
                        row = (-1, -1, current_frame, *blob_dims, area, *blob_bbox, thresh_buff)
                        blobs_data.append(row)
            
    return blobs_data

    
def _get_light_flag(masked_image_file):
    with tables.File(masked_image_file, 'r') as mask_fid:
        mask_dataset = mask_fid.get_node('/', 'mask')
        is_light_background = 1 if not 'is_light_background' in mask_dataset._v_attrs \
                 else mask_dataset._v_attrs['is_light_background']
    return is_light_background
    
def _get_fps(masked_image_file):
    with tables.File(masked_image_file, 'r') as mask_fid:
        try:
            expected_fps = mask_fid.get_node('/', 'mask')._v_attrs['expected_fps']
        except:
            expected_fps = 25 
    return expected_fps


def getBlobsTable(masked_image_file, 
                  trajectories_file,
                  buffer_size = -1,
                    min_area=25,
                    min_box_width=5,
                    worm_bw_thresh_factor=1.,
                    strel_size=(5,5),
                    analysis_type="WORM",
                    thresh_block_size=15,
                    n_cores_used = 2):



    #correct strel if it is not a tuple or list
    if not isinstance(strel_size, (tuple,list)):
        strel_size = (strel_size, strel_size)
    assert len(strel_size) == 2


    #create generators
    is_light_background = _get_light_flag(masked_image_file)
    expected_fps = _get_fps(masked_image_file)
    
    if buffer_size < 0: #invalid value of buff size, expected_fps instead
        buffer_size = expected_fps


    def _ini_plate_worms(traj_fid, masked_image_file):
        # intialize main table
    
        int_dtypes = [('worm_index_blob', np.int),
                      ('worm_index_joined', np.int),
                      ('frame_number', np.int)]
        dd = ['coord_x', 
              'coord_y', 
              'box_length', 
              'box_width', 
              'angle',
              'area',
              'bounding_box_xmin',
              'bounding_box_xmax',
              'bounding_box_ymin',
              'bounding_box_ymax',
              'threshold']
        
        float32_dtypes = [(x, np.float32) for x in dd]
        
        plate_worms_dtype = np.dtype(int_dtypes + float32_dtypes)
        plate_worms = traj_fid.create_table('/',
                                            "plate_worms",
                                            plate_worms_dtype,
                                            "Worm feature List",
                                            filters = TABLE_FILTERS)

        
        
        #find if it is a mask from fluorescence and save it in the new group
        is_light_background = _get_light_flag(masked_image_file)
        plate_worms._v_attrs['is_light_background'] = is_light_background
        
        expected_fps = _get_fps(masked_image_file)
        plate_worms._v_attrs['expected_fps'] = expected_fps
        

        read_and_save_timestamp(masked_image_file, trajectories_file)
        return plate_worms, is_light_background
    

    blob_params = (is_light_background,
                  min_area,
                  min_box_width,
                  worm_bw_thresh_factor,
                  strel_size,
                  analysis_type,
                  thresh_block_size)
    
    buff_generator = generateROIBuff(masked_image_file, 
                      buffer_size,
                      blob_params)
    
    f_blob_data = partial(getBlobsData, blob_params = blob_params)
    
    
    if n_cores_used > 1:
        p = mp.Pool(n_cores_used)
        blobs_generator = p.imap(f_blob_data, buff_generator)
    else:
        blobs_generator = map(f_blob_data, buff_generator)
    
    #loop, save data and display progress
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_str = base_name + ' Calculating trajectories.'
    
    progressTime = timeCounterStr(progress_str)  
    with tables.open_file(trajectories_file, mode='w') as traj_fid:
        plate_worms, is_light_background = _ini_plate_worms(traj_fid, masked_image_file)
        
        for ibuf, blobs_data in enumerate(blobs_generator):
            if blobs_data:
                plate_worms.append(blobs_data)
            
            frames = ibuf*buffer_size
            if frames % (expected_fps*20) == 0:
                # calculate the progress and put it in a string
                print_flush(progressTime.getStr(frames))
                
    print_flush( progressTime.getStr(frames))
    

    
    


    
if __name__ == '__main__':
    #%%
    #dname = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/fluorescence/'
    #masked_image_file = os.path.join(dname, 'test_s.hdf5')
#    min_area=15/2
#    buffer_size=9
#    thresh_block_size=15    
#    max_allowed_dist = 20
#    area_ratio_lim = (0.25, 4)
#    n_proc = 20
    
    masked_image_file = '/Users/ajaver/OneDrive - Imperial College London/Local_Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_17112015_205616.hdf5'
    min_area=25/2
    buffer_size=25
    thresh_block_size=15 
    max_allowed_dist = 25
    area_ratio_lim = (0.5, 2)
    n_cores_used = 1
    
    trajectories_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
    skeletons_file = masked_image_file.replace('.hdf5', '_skeletons.hdf5')
        
    
    
    from MWTracker.analysis.ske_init.processTrajectoryData import processTrajectoryData
    from MWTracker.helper.tracker_param import tracker_param, default_param
    from MWTracker.analysis.traj_join.correctTrajectories import correctTrajectories
    
    default_param['expected_fps'] = buffer_size
    default_param['traj_area_ratio_lim'] = area_ratio_lim
    param = tracker_param()
    param._get_param(**default_param)
    
    #correctTrajectories(trajectories_file, False, param.join_traj_param)
    processTrajectoryData(skeletons_file, masked_image_file, skeletons_file, param.smoothed_traj_param, filter_model_name = '')
