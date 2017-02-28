import os
import pandas as pd
import tables
import cv2
import numpy as np
import json

from tierpsy.analysis.ske_create.helperIterROI import generateMoviesROI
from tierpsy.analysis.ske_create.getSkeletonsTables import getWormMask
from tierpsy.helper.misc import TABLE_FILTERS

def _getBlobFeatures(blob_cnt, blob_mask, roi_image, roi_corner):
    if blob_cnt.size > 0:
        area = float(cv2.contourArea(blob_cnt))
        # find use the best rotated bounding box, the fitEllipse function produces bad results quite often
        # this method is better to obtain an estimate of the worm length than
        # eccentricity
        (CMx, CMy), (L, W), angle = cv2.minAreaRect(blob_cnt)
        #adjust CM from the ROI reference frame to the image reference
        CMx += roi_corner[0]
        CMy += roi_corner[1]
    
        if L == 0 or W == 0:
            return None #something went wrong abort
        
        if W > L:
            L, W = W, L  # switch if width is larger than length
        quirkiness = np.sqrt(1 - W**2 / L**2)
    
        hull = cv2.convexHull(blob_cnt)  # for the solidity
        solidity = area / cv2.contourArea(hull)
        perimeter = float(cv2.arcLength(blob_cnt, True))
        compactness = 4 * np.pi * area / (perimeter**2)
    
        # calculate the mean intensity of the worm
        intensity_mean, intensity_std = cv2.meanStdDev(roi_image, mask=blob_mask)
        intensity_mean = intensity_mean[0,0]
        intensity_std = intensity_std[0,0]
    
        # calculate hu moments, they are scale and rotation invariant
        hu_moments = cv2.HuMoments(cv2.moments(blob_cnt))
    
        
        # save everything into the the proper output format
        mask_feats = (CMx,
                    CMy,
                    area,
                    perimeter,
                    L,
                    W,
                    quirkiness,
                    compactness,
                    angle,
                    solidity,
                    intensity_mean,
                    intensity_std,
                    *hu_moments.flatten())
    else:
        return tuple([np.nan]*19)

    return mask_feats

    
def getBlobsFeats(skeletons_file, masked_image_file, strel_size):
    # extract the base name from the masked_image_file. This is used in the
    # progress status.
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_prefix =  base_name + ' Calculating individual blobs features.'
    

    #read trajectories data with pandas
    with pd.HDFStore(skeletons_file, 'r') as ske_file_id:
        trajectories_data = ske_file_id['/trajectories_data']
    

    with tables.File(skeletons_file, 'r') as ske_file_id:
        dd = ske_file_id.get_node('/trajectories_data')
        is_light_background = dd._v_attrs['is_light_background']
        expected_fps = dd._v_attrs['expected_fps']
        bgnd_param = dd._v_attrs['bgnd_param']
        bgnd_param = json.loads(bgnd_param.decode("utf-8"))

    #get generators to get the ROI for each frame
    ROIs_generator = generateMoviesROI(masked_image_file, 
                                         trajectories_data, 
                                         progress_prefix = progress_prefix)
    
    def _gen_rows_blocks():
        block_size = 1000
        #use rows for the ROIs_generator, this should balance the data in a given tread
        block = []
        for roi_dicts in ROIs_generator:
            for irow, (roi_image, roi_corner) in roi_dicts.items():
                block.append((irow, (roi_image, roi_corner)))
                if len(block) == block_size:
                    yield block
                    block = []
        if len(block) > 0:
            yield block
    
    
    def _roi2feats(block):
        #from a 
        output= []
        for irow, (roi_image, roi_corner) in block:
            row_data = trajectories_data.loc[irow]  
            blob_mask, blob_cnt, _ = getWormMask(roi_image, 
                                                 row_data['threshold'], 
                                                 strel_size,
                                                 min_blob_area=row_data['area'] / 2, 
                                                 is_light_background = is_light_background)
            feats = _getBlobFeatures(blob_cnt, blob_mask, roi_image, roi_corner)
            
            output.append((irow, feats))
        return output
    
    
    # initialize output data as a numpy recarray (pytables friendly format)
    feats_names = ['coord_x', 'coord_y', 'area', 'perimeter', 
    'box_length', 'box_width', 'quirkiness', 'compactness', 
    'box_orientation', 'solidity', 'intensity_mean', 'intensity_std', 
    'hu0', 'hu1', 'hu2', 'hu3', 'hu4', 'hu5', 'hu6']                                     
    
    features_df = np.recarray(len(trajectories_data), 
                              dtype = [(x, np.float32) for x in feats_names])
                                                   
                                                   
    feats_generator = map(_roi2feats, _gen_rows_blocks())
    
        
    for block in feats_generator:
        for irow, row_dat in block:
            features_df[irow] = row_dat
    
    with tables.File(skeletons_file, 'r+') as fid: 
        if '/blob_features' in fid:
            fid.remove_node('/blob_features')
            
        fid.create_table(
                '/',
                'blob_features',
                obj=features_df,
                filters=TABLE_FILTERS) 
        assert all(x in feats_names for x in fid.get_node('/blob_features').colnames)

if __name__ == '__main__':
    #masked_image_file = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/short_movies/MaskedVideos/double_pick_021216/N2_N6_Set4_Pos5_Ch5_02122016_160343.hdf5'
    
    masked_image_file = '/Volumes/behavgenom_archive$/Serena/MaskedVideos/recording 29.9 green 100-200/recording 29.9 green_X1.hdf5'
    skeletons_file = masked_image_file.replace('MaskedVideos', 'Results').replace('.hdf5', '_skeletons.hdf5')
    
    is_light_background = True
    strel_size = 5
    getBlobFeats(skeletons_file, masked_image_file, is_light_background, strel_size)