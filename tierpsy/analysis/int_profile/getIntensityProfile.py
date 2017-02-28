# -*- coding: utf-8 -*-
"""
Created on Mon Jun  1 22:15:48 2015

@author: ajaver
"""

import os

import numpy as np
import pandas as pd
import tables
from scipy.interpolate import RectBivariateSpline
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter

from MWTracker.analysis.ske_create.helperIterROI import getWormROI
from MWTracker.analysis.ske_filt.getFilteredSkels import saveModifiedTrajData
from MWTracker.helper.misc import print_flush
from MWTracker.helper.timeCounterStr import timeCounterStr


def smoothSkeletons(
        skeleton,
        length_resampling=131,
        smooth_win=11,
        pol_degree=3):
    xx = savgol_filter(skeleton[:, 0], smooth_win, pol_degree)
    yy = savgol_filter(skeleton[:, 1], smooth_win, pol_degree)

    ii = np.arange(xx.size)
    ii_new = np.linspace(0, xx.size - 1, length_resampling)

    fx = interp1d(ii, xx)
    fy = interp1d(ii, yy)

    xx_new = fx(ii_new)
    yy_new = fy(ii_new)

    skel_new = np.vstack((xx_new, yy_new)).T
    return skel_new


def getStraightenWormInt(worm_img, skeleton, half_width, width_resampling):
    '''
        Code to straighten the worm worms.
        worm_image - image containing the worm
        skeleton - worm skeleton
        half_width - half width of the worm, if it is -1 it would try to calculated from cnt_widths
        cnt_widths - contour widths used in case the half width is not given
        width_resampling - number of data points used in the intensity map along the worm width
        length_resampling - number of data points used in the intensity map along the worm length
        ang_smooth_win - window used to calculate the skeleton angles.
            A small value will introduce noise, therefore obtaining bad perpendicular segments.
            A large value will over smooth the skeleton, therefore not capturing the correct shape.

    '''

    assert half_width > 0 or cnt_widths.size > 0
    assert not np.any(np.isnan(skeleton))

    dX = np.diff(skeleton[:, 0])
    dY = np.diff(skeleton[:, 1])

    skel_angles = np.arctan2(dY, dX)
    skel_angles = np.hstack((skel_angles[0], skel_angles))

    #%get the perpendicular angles to define line scans (orientation doesn't
    #%matter here so subtracting pi/2 should always work)
    perp_angles = skel_angles - np.pi / 2

    #%for each skeleton point get the coordinates for two line scans: one in the
    #%positive direction along perpAngles and one in the negative direction (use
    #%two that both start on skeleton so that the intensities are the same in
    #%the line scan)

    r_ind = np.linspace(-half_width, half_width, width_resampling)

    # create the grid of points to be interpolated (make use of numpy implicit
    # broadcasting Nx1 + 1xM = NxM)
    grid_x = skeleton[:, 0] + r_ind[:, np.newaxis] * np.cos(perp_angles)
    grid_y = skeleton[:, 1] + r_ind[:, np.newaxis] * np.sin(perp_angles)

    # interpolated the intensity map
    f = RectBivariateSpline(
        np.arange(
            worm_img.shape[0]), np.arange(
            worm_img.shape[1]), worm_img)
    straighten_worm = f.ev(grid_y, grid_x)

    return straighten_worm, grid_x, grid_y


def getWidthWinLimits(width_resampling, width_percentage):
    # let's calculate the window along the minor axis of the skeleton to be
    # average, as a percentage of the total interpolated width
    width_average_win = int(width_resampling * width_percentage)
    if width_average_win % 2 == 0:
        width_average_win += 1
    mid_w = width_resampling // 2
    win_w = width_average_win // 2
    # add plus one to use the correct numpy indexing
    return (mid_w - win_w, mid_w + win_w + 1)


def setIntMapIndexes(skeletons_file, min_num_skel):
    # get index of valid skeletons. Let's use pandas because it is easier to
    # process.
    with pd.HDFStore(skeletons_file, 'r') as fid:
        trajectories_data = fid['/trajectories_data']

        if 'is_good_skel' in trajectories_data:
            # select rows with only valid filtered skeletons
            good = trajectories_data['is_good_skel'] == 1
        else:
            # or that at least have an skeleton
            good = trajectories_data['has_skeleton'] == 1

        trajectories_data_valid = trajectories_data[good]

        # select trajectories that have at least min_num_skel valid skeletons
        N = trajectories_data_valid.groupby(
            'worm_index_joined').agg({'has_skeleton': np.nansum})
        N = N[N > min_num_skel].dropna()
        good = trajectories_data_valid['worm_index_joined'].isin(N.index)
        trajectories_data_valid = trajectories_data_valid.loc[good]

    # assing indexes to the new rows
    tot_valid_rows = len(trajectories_data_valid)
    trajectories_data['int_map_id'] = -1
    trajectories_data.loc[
        trajectories_data_valid.index,
        'int_map_id'] = np.arange(tot_valid_rows)

    # let's save this data into the skeletons file
    saveModifiedTrajData(skeletons_file, trajectories_data)

    # get the valid trajectories with the correct index. There is probably a
    # faster way to do this, but this is less prone to errors.
    trajectories_data_valid = trajectories_data[
        trajectories_data['int_map_id'] != -1]

    # return the reduced version with only valid rows
    return trajectories_data_valid


def getIntensityProfile(
        masked_image_file,
        skeletons_file,
        intensities_file,
        width_resampling=15,
        length_resampling=131,
        min_num_skel=100,
        smooth_win=11,
        pol_degree=3,
        width_percentage=0.5,
        save_maps=False):

    assert smooth_win > pol_degree
    assert min_num_skel > 0
    assert 0 < width_percentage < 1

    # we want to use symetrical distance centered in the skeleton
    if length_resampling % 2 == 0:
        length_resampling += 1
    if width_resampling % 2 == 0:
        width_resampling += 1

    # get the limits to be averaged from the intensity map
    if save_maps:
        width_win_ind = getWidthWinLimits(width_resampling, width_percentage)
    else:
        width_win_ind = (0, width_resampling)

    # filters for the tables structures
    table_filters = tables.Filters(complevel=5, complib='zlib',
                                   shuffle=True, fletcher32=True)

    # Get a reduced version of the trajectories_data table with only the valid skeletons.
    # The rows of this new table are going to be saved into skeletons_file
    trajectories_data_valid = setIntMapIndexes(skeletons_file, min_num_skel)

    # let's save this new table into the intensities file
    with tables.File(intensities_file, 'w') as fid:
        fid.create_table(
            '/',
            'trajectories_data_valid',
            obj=trajectories_data_valid.to_records(
                index=False),
            filters=table_filters)

    tot_rows = len(trajectories_data_valid)
    if tot_rows == 0:
        with tables.File(intensities_file, "r+") as int_file_id:
            # nothing to do here let's save empty data and go out
            worm_int_avg_tab = int_file_id.create_array(
                "/", "straighten_worm_intensity_median", obj=np.zeros(0))
            worm_int_avg_tab._v_attrs['has_finished'] = 1
        return

    with tables.File(masked_image_file, 'r')  as mask_fid, \
            tables.File(skeletons_file, 'r') as ske_file_id, \
            tables.File(intensities_file, "r+") as int_file_id:

        # pointer to the compressed videos
        mask_dataset = mask_fid.get_node("/mask")

        # pointer to skeletons
        skel_tab = ske_file_id.get_node('/skeleton')
        skel_width_tab = ske_file_id.get_node('/width_midbody')

        filters = tables.Filters(complevel=5, complib='zlib', shuffle=True)

        # we are using Float16 to save space, I am assuing the intensities are
        # between uint8
        worm_int_avg_tab = int_file_id.create_carray(
            "/",
            "straighten_worm_intensity_median",
            tables.Float16Atom(
                dflt=np.nan),
            (tot_rows,
             length_resampling),
            chunkshape=(
                1,
                length_resampling),
            filters=table_filters)

        worm_int_avg_tab._v_attrs['has_finished'] = 0
        worm_int_avg_tab.attrs['width_win_ind'] = width_win_ind

        if save_maps:
            worm_int_tab = int_file_id.create_carray(
                "/",
                "straighten_worm_intensity",
                tables.Float16Atom(
                    dflt=np.nan),
                (tot_rows,
                 length_resampling,
                 width_resampling),
                chunkshape=(
                    1,
                    length_resampling,
                    width_resampling),
                filters=table_filters)
        # variables used to report progress
        base_name = skeletons_file.rpartition(
            '.')[0].rpartition(os.sep)[-1].rpartition('_')[0]
        progressTime = timeCounterStr('Obtaining intensity maps.')

        for frame, frame_data in trajectories_data_valid.groupby(
                'frame_number'):
            img = mask_dataset[frame, :, :]
            for ii, row_data in frame_data.iterrows():
                skeleton_id = int(row_data['skeleton_id'])
                worm_index = int(row_data['worm_index_joined'])
                int_map_id = int(row_data['int_map_id'])

                # read ROI and skeleton, and put them in the same coordinates
                # map
                worm_img, roi_corner = getWormROI(
                    img, row_data['coord_x'], row_data['coord_y'], row_data['roi_size'])
                skeleton = skel_tab[skeleton_id, :, :] - roi_corner

                half_width = skel_width_tab[skeleton_id] / 2

                assert not np.isnan(skeleton[0, 0])

                skel_smooth = smoothSkeletons(
                    skeleton,
                    length_resampling=length_resampling,
                    smooth_win=smooth_win,
                    pol_degree=pol_degree)
                straighten_worm, grid_x, grid_y = getStraightenWormInt(
                    worm_img, skel_smooth, half_width=half_width, width_resampling=width_resampling)

                # if you use the mean it is better to do not use float16
                int_avg = np.median(
                    straighten_worm[
                        width_win_ind[0]:width_win_ind[1],
                        :],
                    axis=0)

                worm_int_avg_tab[int_map_id] = int_avg

                # only save the full map if it is specified by the user
                if save_maps:
                    worm_int_tab[int_map_id] = straighten_worm.T

            if frame % 500 == 0:
                progress_str = progressTime.getStr(frame)
                print_flush(base_name + ' ' + progress_str)

        worm_int_avg_tab._v_attrs['has_finished'] = 1

if __name__ == '__main__':
    # base directory
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch5_17112015_205616.hdf5'
    masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch3_17112015_205616.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/Avelino_17112015/MaskedVideos/CSTCTest_Ch1_18112015_075624.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/04-03-11/MaskedVideos/575 JU440 swimming_2011_03_04__13_16_37__8.hdf5'
    #masked_image_file = '/Users/ajaver/Desktop/Videos/04-03-11/MaskedVideos/575 JU440 on food Rz_2011_03_04__12_55_53__7.hdf5'

    skeletons_file = masked_image_file.replace('MaskedVideos', 'Results')[
        :-5] + '_skeletons.hdf5'
    intensities_file = skeletons_file.replace('_skeletons', '_intensities')
    # parameters

    dd = np.asarray([131, 15, 7])  # *2+1
    argkws = {
        'width_resampling': dd[1],
        'length_resampling': dd[0],
        'min_num_skel': 100,
        'smooth_win': dd[2],
        'pol_degree': 3}
    getIntensityProfile(
        masked_image_file,
        skeletons_file,
        intensities_file,
        **argkws)

    #%%
