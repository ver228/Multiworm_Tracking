# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 13:19:58 2015

@author: ajaver
"""
import os

import cv2
import h5py
import numpy as np
from MWTracker.analysis.compress.BackgroundSubtractor import BackgroundSubtractor
from  MWTracker.analysis.compress.extractMetaData import store_meta_data, read_and_save_timestamp
from scipy.ndimage.filters import median_filter

from  MWTracker.analysis.compress.selectVideoReader import selectVideoReader
from MWTracker.helper.misc import print_flush
from MWTracker.helper.timeCounterStr import timeCounterStr

IMG_FILTERS = {"compression":"gzip",
        "compression_opts":4,
        "shuffle":True,
        "fletcher32":True}

def getROIMask(
        image,
        min_area,
        max_area,
        thresh_block_size,
        thresh_C,
        dilation_size,
        keep_border_data,
        is_light_background):
    '''
    Calculate a binary mask to mark areas where it is possible to find worms.
    Objects with less than min_area or more than max_area pixels are rejected.
        > min_area -- minimum blob area to be considered in the mask
        > max_area -- max blob area to be considered in the mask
        > thresh_C -- threshold used by openCV adaptiveThreshold
        > thresh_block_size -- block size used by openCV adaptiveThreshold
        > dilation_size -- size of the structure element to dilate the mask
        > keep_border_data -- (bool) if false it will reject any blob that touches the image border

    '''
    # Objects that touch the limit of the image are removed. I use -2 because
    # openCV findCountours remove the border pixels
    IM_LIMX = image.shape[0] - 2
    IM_LIMY = image.shape[1] - 2

    if thresh_block_size % 2 == 0:
        thresh_block_size += 1  # this value must be odd

    #let's add a median filter, this will smooth the image, and eliminate small variations in intensity
    image = median_filter(image, 5)

    # adaptative threshold is the best way to find possible worms. The
    # parameters are set manually, they seem to work fine if there is no
    # condensation in the sample
    if not is_light_background:  # invert the threshold (change thresh_C->-thresh_C and cv2.THRESH_BINARY_INV->cv2.THRESH_BINARY) if we are dealing with a fluorescence image
        mask = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            thresh_block_size,
            -thresh_C)
    else:
        mask = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV,
            thresh_block_size,
            thresh_C)

    # find the contour of the connected objects (much faster than labeled
    # images)
    _, contours, hierarchy = cv2.findContours(
        mask.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # find good contours: between max_area and min_area, and do not touch the
    # image border
    goodIndex = []
    for ii, contour in enumerate(contours):
        if not keep_border_data:
            # eliminate blobs that touch a border
            keep = not np.any(contour == 1) and \
                not np.any(contour[:, :, 0] ==  IM_LIMY)\
                and not np.any(contour[:, :, 1] == IM_LIMX)
        else:
            keep = True

        if keep:
            area = cv2.contourArea(contour)
            if (area >= min_area) and (area <= max_area):
                goodIndex.append(ii)

    # typically there are more bad contours therefore it is cheaper to draw
    # only the valid contours
    mask = np.zeros(image.shape, dtype=image.dtype)
    for ii in goodIndex:
        cv2.drawContours(mask, contours, ii, 1, cv2.FILLED)

    # drawContours left an extra line if the blob touches the border. It is
    # necessary to remove it
    mask[0, :] = 0
    mask[:, 0] = 0
    mask[-1, :] = 0
    mask[:, -1] = 0

    # dilate the elements to increase the ROI, in case we are missing
    # something important
    struct_element = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
    mask = cv2.dilate(mask, struct_element, iterations=3)

    return mask

def normalizeImage(img):
    # normalise image intensities if the data type is other
    # than uint8
    image = image.astype(np.double)
    
    imax = img.max()
    imin = img.min()
    factor = 255/(imax-imin)
    
    imgN = ne.evaluate('(img-imin)*factor')
    imgN = imgN.astype(np.uint8)

    return imgN, (imin, imax)
 
def reduceBuffer(Ibuff, is_light_background):
    if is_light_background:
        return np.min(Ibuff, axis=0)
    else:
        return np.max(Ibuff, axis=0)

def createImgGroup(fid, name, tot_frames, im_height, im_width):
    
    img_dataset = fid.create_dataset(
        name,
        (tot_frames,
         im_height,
         im_width),
        dtype="u1",
        maxshape=(
            None,
            im_height,
            im_width),
        chunks=(
            1,
            im_height,
            im_width),
        **IMG_FILTERS)

    img_dataset.attrs["CLASS"] = np.string_("IMAGE")
    img_dataset.attrs["IMAGE_SUBCLASS"] = np.string_("IMAGE_GRAYSCALE")
    img_dataset.attrs["IMAGE_WHITE_IS_ZERO"] = np.array(0, dtype="uint8")
    img_dataset.attrs["DISPLAY_ORIGIN"] = np.string_("UL")  # not rotated
    img_dataset.attrs["IMAGE_VERSION"] = np.string_("1.2")

    return img_dataset

def initMasksGroups(fid, expected_frames, im_height, im_width, 
    expected_fps, is_light_background, save_full_interval):

    # open node to store the compressed (masked) data
    mask_dataset = createImgGroup(fid, "/mask", expected_frames, im_height, im_width)
    mask_dataset.attrs['has_finished'] = 0 # flag to indicate if the conversion finished succesfully
    mask_dataset.attrs['expected_fps'] = expected_fps # setting the expected_fps attribute so it can be read later
    mask_dataset.attrs['is_light_background'] = int(is_light_background)
    

    tot_save_full = (expected_frames // save_full_interval) + 1
    full_dataset = createImgGroup(fid, "/full_data", tot_save_full, im_height, im_width)
    full_dataset.attrs['save_interval'] = save_full_interval
    full_dataset.attrs['expected_fps'] = expected_fps
        

    return mask_dataset, full_dataset

def compressVideo(video_file, masked_image_file, mask_param, bgnd_param, buffer_size=-1,
                  save_full_interval=-1, max_frame=1e32, expected_fps=25,
                  is_light_background=True):
    '''
    Compresses video by selecting pixels that are likely to have worms on it and making the rest of
    the image zero. By creating a large amount of redundant data, any lossless compression
    algorithm will dramatically increase its efficiency. The masked images are saved as hdf5 with gzip compression.
    The mask is calculated over a minimum projection of an image stack. This projection preserves darker regions
    (or brighter regions, in the case of fluorescent labelling)
    where the worm has more probability to be located. Additionally it has the advantage of reducing
    the processing load by only requiring to calculate the mask once per image stack.
     video_file --  original video file
     masked_image_file --
     buffer_size -- size of the image stack used to calculate the minimal projection and the mask
     save_full_interval -- have often a full image is saved
     max_frame -- last frame saved (default a very large number, so it goes until the end of the video)
     mask_param -- parameters used to calculate the mask
    '''

    if buffer_size < 0:
        buffer_size = expected_fps

    if save_full_interval < 0:
        save_full_interval = 200 * expected_fps

    # processes identifier.
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]

    # delete any previous  if it existed
    with h5py.File(masked_image_file, "w") as mask_fid:
        pass

    # select the video reader class according to the file type.
    vid = selectVideoReader(video_file)


    if vid.width == 0 or vid.height == 0:
        raise RuntimeError

    # extract and store video metadata using ffprobe
    print_flush(base_name + ' Extracting video metadata...')
    expected_frames = store_meta_data(video_file, masked_image_file)
    
    if bgnd_param['is_subtraction']:
        print_flush(base_name + ' Initializing background subtraction.')
        bgnd_subtractor = BackgroundSubtractor(video_file, bgnd_param['buff_size'], bgnd_param['frame_gap'], mask_param['is_light_background'])

    # intialize some variables
    max_intensity, min_intensity = np.nan, np.nan
    frame_number = 0
    full_frame_number = 0
    image_prev = np.zeros([])

    # initialize timers
    print_flush(base_name + ' Starting video compression.')
    progressTime = timeCounterStr('Compressing video.')

    with h5py.File(masked_image_file, "r+") as mask_fid:

        #initialize masks groups
        mask_dataset, full_dataset = initMasksGroups(mask_fid, 
            expected_frames, vid.height, vid.width, expected_fps, 
            mask_param['is_light_background'], save_full_interval)
        
        if vid.dtype != np.uint8:
            # this will worm as flags to be sure that the normalization took place.
            normalization_range = mask_fid.create_dataset(
                '/normalization_range',
                (expected_frames, 2),
                dtype='f4',
                maxshape=(None, 2),
                chunks=True,
                **IMG_FILTERS)
    
        while frame_number < max_frame:

            ret, image = vid.read()
            if ret != 0:
                # increase frame number
                frame_number += 1

                # opencv can give an artificial rgb image. Let's get it back to
                # gray scale.
                if image.ndim == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

                if image.dtype != np.uint8:
                    # normalise image intensities if the data type is other
                    # than uint8
                    image, img_norm_range = normalizeImage(image)

                    if normalization_range.shape[0] <= frame_number + 1:
                        normalization_range.resize(frame_number + 1000, axis=0)
                    normalization_range[frame_number] = img_norm_range

                #limit the image range to 1 to 255, 0 is a reserved value for the background
                assert image.dtype == np.uint8
                image = np.clip(image, 1,255)


                # Resize mask array every 1000 frames (doing this every frame
                # does not impact much the performance)
                if mask_dataset.shape[0] <= frame_number + 1:
                    mask_dataset.resize(frame_number + 1000, axis=0)

                # Add a full frame every save_full_interval
                if frame_number % save_full_interval == 1:
                    if full_dataset.shape[0] <= full_frame_number:
                        full_dataset.resize(full_frame_number + 1, axis=0)
                        # just to be sure that the index we are saving in is
                        # what we what we are expecting
                        assert(frame_number //
                               save_full_interval == full_frame_number)

                    full_dataset[full_frame_number, :, :] = image.copy()
                    full_frame_number += 1

                # buffer index
                ind_buff = (frame_number - 1) % buffer_size

                # initialize the buffer when the index correspond to 0
                if ind_buff == 0:
                    Ibuff = np.zeros(
                        (buffer_size, vid.height, vid.width), dtype=np.uint8)

                # add image to the buffer
                Ibuff[ind_buff, :, :] = image.copy()

            else:
                # sometimes the last image is all zeros, control for this case
                if np.all(Ibuff[ind_buff] == 0):
                    frame_number -= 1
                    ind_buff -= 1

                # close the buffer
                Ibuff = Ibuff[:ind_buff + 1]

            # mask buffer and save data into the hdf5 file
            if (ind_buff == buffer_size - 1 or ret == 0) and Ibuff.size > 0:

                #TODO this can be done in a more clever way
                
                # Subtract background if flag set
                if bgnd_param['is_subtraction']:
                    #use the oposite (like that we can avoid an unecessary subtraction)
                    oposite_flag = not mask_param['is_light_background']
                    Ibuff_b  = bgnd_subtractor.apply(Ibuff)
                    img_reduce = 255 - reduceBuffer(Ibuff_b, oposite_flag)
                else:
                    #calculate the max/min in the of the buffer
                    img_reduce = reduceBuffer(Ibuff, mask_param['is_light_background'])


                
                mask = getROIMask(img_reduce, **mask_param)
                Ibuff *= mask

                # add buffer to the hdf5 file
                frame_first_buff = frame_number - Ibuff.shape[0]
                mask_dataset[frame_first_buff:frame_number, :, :] = Ibuff

            if frame_number % 500 == 0:
                # calculate the progress and put it in a string
                progress_str = progressTime.getStr(frame_number)
                print_flush(base_name + ' ' + progress_str)
                
            # finish process
            if ret == 0:
                break

        # once we finished to read the whole video, we need to make sure that
        # the hdf5 array sizes are correct.
        if mask_dataset.shape[0] != frame_number:
            mask_dataset.resize(frame_number, axis=0)

        if full_dataset.shape[0] != full_frame_number:
            full_dataset.resize(full_frame_number, axis=0)

        # reshape or remove the normalization range
        if vid.dtype != np.uint8:
                normalization_range.resize(frame_number, axis=0)

        # close the video
        vid.release()

    read_and_save_timestamp(masked_image_file)
    # attribute to indicate the program finished correctly
    with h5py.File(masked_image_file, "r+") as mask_fid:
        mask_fid['/mask'].attrs['has_finished'] = 1

    print_flush(base_name + ' Compressed video done.')
    


