# -*- coding: utf-8 -*-
"""
Created on Tue Jun  2 15:16:41 2015

@author: ajaver
"""
import tables
import numpy as np


class WormClass:
    # helper class to extract worm data from the plate table. For the moment
    # it is only used in checkHeadOrientation.

    def __init__(self, skeleton_file, worm_index, rows_range=(0, 0)):
        assert rows_range[0] <= rows_range[1]

        self.file_name = skeleton_file
        with tables.File(self.file_name, 'r') as file_id:
            # data range
            if rows_range[0] == 0 and rows_range[1] == 0:
                # try to read it from the file
                tab = file_id.get_node('/trajectories_data')
                skeleton_id = tab.read_where(
                    'worm_index_joined==%i' %
                    1, field='skeleton_id')

                # the indexes must be continous
                assert np.all(np.diff(skeleton_id) == 1)

                rows_range = (np.min(skeleton_id), np.max(skeleton_id))
                del skeleton_id

            ini, end = rows_range

            self.index = worm_index
            self.rows_range = rows_range
            self.data_fields = [
                'skeleton',
                'skeleton_length',
                'contour_side1',
                'contour_side2',
                'contour_width',
                'contour_area']  # 'contour_side1_length', 'contour_side2_length'

            tab = file_id.get_node('/trajectories_data')
            self.frames = tab.read(ini, end, 1, 'frame_number')
            self.coord_x = tab.read(ini, end, 1, 'coord_x')
            self.coord_y = tab.read(ini, end, 1, 'coord_y')

            self.skeleton = file_id.get_node('/skeleton')[ini:end + 1, :, :]

            self.contour_side1 = file_id.get_node(
                '/contour_side1')[ini:end + 1, :, :]
            self.contour_side2 = file_id.get_node(
                '/contour_side2')[ini:end + 1, :, :]

            # self.contour_side1_length = file_id.get_node('/contour_side1_length')[ini:end+1]#pixels
            # self.contour_side2_length =
            # file_id.get_node('/contour_side2_length')[ini:end+1]#pixels
            self.skeleton_length = file_id.get_node(
                '/skeleton_length')[ini:end + 1]  # pixels

            self.contour_width = file_id.get_node(
                '/contour_width')[ini:end + 1, :]

            self.contour_area = file_id.get_node('/contour_area')[ini:end + 1]

        # change invalid data zeros for np.nan
        invalid = self.skeleton_length == 0
        for field in self.data_fields:
            getattr(self, field)[invalid] = np.nan

    def writeData(self):
        with tables.File(self.file_name, 'r+') as file_id:
            ini, end = self.rows_range
            for field in self.data_fields:
                file_id.get_node(
                    '/' +
                    field)[
                    ini:end +
                    1] = getattr(
                    self,
                    field)

    def switchHeadTail(self, is_switched):
        self.skeleton[is_switched] = self.skeleton[is_switched, ::-1, :]
        self.contour_side1[is_switched] = self.contour_side1[
            is_switched, ::-1, :]
        self.contour_side2[is_switched] = self.contour_side2[
            is_switched, ::-1, :]
        self.contour_width[is_switched] = self.contour_width[is_switched, ::-1]

        # contours must be switched to keep the same clockwise orientation
        self.switchContourSides(is_switched)

    def switchContourSides(self, is_switched):
        self.contour_side1[is_switched], self.contour_side2[is_switched ] = \
            self.contour_side2[is_switched], self.contour_side1[is_switched]

        # self.contour_side1_length[is_switched], self.contour_side2_length[is_switched] = \
        #self.contour_side2_length[is_switched], self.contour_side1_length[is_switched]

    def getImage(self, masked_image_file, index, roi_size=128):
        # reading a video frame for one worm is very slow. Use it only in small
        # scale
        with tables.File(masked_image_file, 'r') as mask_fid:
            img = mask_fid.get_node("/mask")[self.frames[index], :, :]
        worm_img, roi_corner = getWormROI(
            img, self.coord_x[index], self.coord_y[index], roi_size)
        return worm_img, roi_corner

if __name__ == '__main__':
    import sys
    sys.path.append('../tracking_worms/')
    from getSkeletons import getWormROI

    sys.path.append('../segworm_python/')
    from main_segworm import getStraightenWormInt

    #import matplotlib.pylab as plt

    #base_name = 'Capture_Ch3_12052015_194303'
    #root_dir = '/Users/ajaver/Desktop/Gecko_compressed/20150512/'

    root_dir = '/Users/ajaver/Desktop/Gecko_compressed/20150511/'
    base_name = 'Capture_Ch1_11052015_195105'

    masked_image_file = root_dir + '/Compressed/' + base_name + '.hdf5'
    trajectories_file = root_dir + '/Trajectories/' + base_name + '_trajectories.hdf5'
    skeleton_file = root_dir + '/Trajectories/' + base_name + '_skeletons.hdf5'

    worm_data = WormClass(skeleton_file, 773)

    #%%
    for ff in [np.nanargmin, np.nanargmax]:
        ii = ff(worm_data.skeleton_length)
        plt.figure()
        for mm, delta in enumerate([-10, 0, 10]):
            index = ii + delta
            worm_img, roi_corner = worm_data.getImage(masked_image_file, index)
            skeleton = worm_data.skeleton[index] - roi_corner

            plt.subplot(1, 3, mm + 1)
            plt.imshow(worm_img, cmap='gray', interpolation='none')
            plt.title(worm_data.skeleton_length[index])
            plt.plot(skeleton[:, 0], skeleton[:, 1], '.-')
    #%%
    half_width = np.nanmedian(worm_data.contour_width[
                              len(worm_data.contour_width) / 2]) / 2 + 0.5
    for ff in [np.nanargmin, np.nanargmax]:
        ii = ff(worm_data.skeleton_length)
        plt.figure()
        for mm, delta in enumerate([-10, 0, 10]):
            index = ii + delta
            worm_img, roi_corner = worm_data.getImage(masked_image_file, index)
            skeleton = worm_data.skeleton[index] - roi_corner
            #cnt_widths = worm_data.contour_width[index]
            int_img = getStraightenWormInt(
                worm_img,
                skeleton,
                half_width=half_width,
                width_resampling=13,
                length_resampling=121)

            plt.subplot(3, 1, mm + 1)
            plt.imshow(int_img, cmap='gray', interpolation='none')
