import json
import os
import sys

import numpy as np
import pandas as pd
import tables
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QPixmap, QImage, QPolygonF, QPen, QPainter, QColor
from PyQt5.QtWidgets import QApplication, QFileDialog

from tierpsy.gui.HDF5VideoPlayer import HDF5VideoPlayer_GUI, lineEditDragDrop
from tierpsy.gui.TrackerViewerAux_ui import Ui_TrackerViewerAux
from tierpsy.analysis.ske_create.getSkeletonsTables import getWormMask
from tierpsy.analysis.ske_create.segWormPython.mainSegworm import getSkeleton


#from scipy.signal import savgol_filter


class TrackerViewerAux_GUI(HDF5VideoPlayer_GUI):

    def __init__(self, ui=''):
        if not ui:
            super().__init__(Ui_TrackerViewerAux())
        else:
            super().__init__(ui)

        self.results_dir = ''
        self.skeletons_file = ''
        self.frame_number = -1
        self.trajectories_data = pd.DataFrame()
        self.traj_time_grouped = -1
        self.frame_save_interval = 1 

        self.ui.pushButton_skel.clicked.connect(self.getSkelFile)
        lineEditDragDrop(
            self.ui.lineEdit_skel,
            self.updateSkelFile,
            os.path.isfile)

    def getSkelFile(self):
        selected_file, _ = QFileDialog.getOpenFileName(
            self, 'Select file with the worm skeletons', self.results_dir, "Skeletons files (*_skeletons.hdf5);; All files (*)")

        if not os.path.exists(selected_file):
            return

        self.updateSkelFile(selected_file)

    def updateSkelFile(self, selected_file):
        
        self.skeletons_file = selected_file
        self.ui.lineEdit_skel.setText(self.skeletons_file)
        
        try:
            with pd.HDFStore(self.skeletons_file, 'r') as ske_file_id:
                self.trajectories_data = ske_file_id['/trajectories_data']
                self.traj_time_grouped = self.trajectories_data.groupby('frame_number')

                # read the size of the structural element used in to calculate
                # the mask
                if '/provenance_tracking/int_ske_orient' in ske_file_id:
                    prov_str = ske_file_id.get_node(
                        '/provenance_tracking/ske_create').read()
                    func_arg_str = json.loads(
                        prov_str.decode("utf-8"))['func_arguments']
                    strel_size = json.loads(func_arg_str)['strel_size']
                    if isinstance(strel_size, (list, tuple)):
                        strel_size = strel_size[0]

                    self.strel_size = strel_size
                else:
                    # use default
                    self.strel_size = 5

        except (IOError, KeyError):
            self.trajectories_data = pd.DataFrame()
            self.traj_time_grouped = -1
            self.skel_dat = {}

        if self.frame_number == 0:
            self.updateImage()
        else:
            self.ui.spinBox_frame.setValue(0)

    def updateImGroup(self):
        super().updateImGroup()
        if self.h5path == '/full_data':
            self.frame_save_interval = int(self.image_group._v_attrs['save_interval'])
        else:
            self.frame_save_interval = 1

    def updateVideoFile(self, vfilename):
        super().updateVideoFile(vfilename)
        if type(self.image_group) is int:
            return

        #find if it is a fluorescence image
        self.is_light_background = 1 if not 'is_light_background' in self.image_group._v_attrs \
            else self.image_group._v_attrs['is_light_background']
        
        videos_dir, basename = os.path.split(vfilename)
        basename = os.path.splitext(basename)[0]

        self.skeletons_file = ''
        self.results_dir = ''

        possible_dirs = [
            videos_dir, videos_dir.replace(
                'MaskedVideos', 'Results'), os.path.join(
                videos_dir, 'Results')]

        for new_dir in possible_dirs:
            new_skel_file = os.path.join(new_dir, basename + '_skeletons.hdf5')
            if os.path.exists(new_skel_file):
                self.skeletons_file = new_skel_file
                self.results_dir = new_dir
                break
        
        self.updateSkelFile(self.skeletons_file)

    def getFrameData(self, frame_number):
        try:
            if not isinstance(self.traj_time_grouped,
                pd.core.groupby.DataFrameGroupBy):
                raise KeyError
            
            frame_data = self.traj_time_grouped.get_group(self.frame_save_interval*frame_number)
            return frame_data

        except KeyError:
            return pd.DataFrame()

    def drawSkelResult(self, img, qimg, row_data, isDrawSkel, 
        roi_corner=(0,0), read_center=True):
        if isDrawSkel and isinstance(row_data, pd.Series):
            if row_data['has_skeleton'] == 1:
                self.drawSkel(
                    img,
                    qimg,
                    row_data,
                    roi_corner = roi_corner
                    )
            else:
                self.drawThreshMask(
                    img,
                    qimg,
                    row_data,
                    read_center=read_center)

        return qimg

    def drawSkel(self, worm_img, worm_qimg, row_data, roi_corner=(0, 0)):
        if not self.skeletons_file or not isinstance(
                self.trajectories_data, pd.DataFrame):
            return

        c_ratio_y = worm_qimg.width() / worm_img.shape[1]
        c_ratio_x = worm_qimg.height() / worm_img.shape[0]

        skel_id = int(row_data['skeleton_id'])

        qPlg = {}

        with tables.File(self.skeletons_file, 'r') as ske_file_id:
            for tt in ['skeleton', 'contour_side1', 'contour_side2']:
                dat = ske_file_id.get_node('/' + tt)[skel_id]
                dat[:, 0] = (dat[:, 0] - roi_corner[0]) * c_ratio_x
                dat[:, 1] = (dat[:, 1] - roi_corner[1]) * c_ratio_y

                # for nn in range(2):
                #    dat[:,nn] = savgol_filter(dat[:,nn], window_length=5, polyorder=3)

                qPlg[tt] = QPolygonF()
                for p in dat:
                    qPlg[tt].append(QPointF(*p))


        if 'is_good_skel' in row_data and row_data['is_good_skel'] == 0:
            self.skel_colors = {
                'skeleton': (
                    102, 0, 0), 'contour_side1': (
                    102, 0, 0), 'contour_side2': (
                    102, 0, 0)}
        else:
            self.skel_colors = {
                'skeleton': (
                    27, 158, 119), 'contour_side1': (
                    217, 95, 2), 'contour_side2': (
                    231, 41, 138)}

        pen = QPen()
        pen.setWidth(1)

        painter = QPainter()
        painter.begin(worm_qimg)

        for tt, color in self.skel_colors.items():
            pen.setColor(QColor(*color))
            painter.setPen(pen)
            painter.drawPolyline(qPlg[tt])

        pen.setColor(Qt.black)
        painter.setBrush(Qt.white)
        painter.setPen(pen)

        radius = 3
        painter.drawEllipse(qPlg['skeleton'][0], radius, radius)

        painter.drawEllipse(QPointF(0,0), radius, radius)

        painter.end()

    def drawThreshMask(self, worm_img, worm_qimg, row_data, read_center=True):
        #in very old versions of the tracker I didn't save the area in trajectories table, 
        #let's assign a default value to deal with this cases
        if 'area' in row_data:
            min_blob_area = row_data['area'] / 2
        else:
            min_blob_area = 10
        
        c1, c2 = (row_data['coord_x'], row_data[
                  'coord_y']) if read_center else (-1, -1)

        worm_mask, worm_cnt, _ = getWormMask(worm_img, row_data['threshold'], strel_size=self.strel_size,
                                      roi_center_x=c1, roi_center_y=c2, min_blob_area=min_blob_area,
                                      is_light_background = self.is_light_background)

        #worm_mask = np.zeros_like(worm_mask)
        #cv2.drawContours(worm_mask, [worm_cnt.astype(np.int32)], 0, 1, -1)

        worm_mask = QImage(
            worm_mask.data,
            worm_mask.shape[1],
            worm_mask.shape[0],
            worm_mask.strides[0],
            QImage.Format_Indexed8)
        worm_mask = worm_mask.convertToFormat(
            QImage.Format_RGB32, Qt.AutoColor)
        worm_mask = QPixmap.fromImage(worm_mask)

        worm_mask = worm_mask.createMaskFromColor(Qt.black)
        p = QPainter(worm_qimg)
        p.setPen(QColor(0, 204, 102))
        p.drawPixmap(worm_qimg.rect(), worm_mask, worm_mask.rect())
        
        if False:
            #test skeletonization
            skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area = \
                getSkeleton(worm_cnt, np.zeros(0), 49)
            for cnt in skeleton, cnt_side1, cnt_side2:
                p.setPen(Qt.black)
                polyline = QPolygonF()
                for point in cnt:
                    polyline.append(QPointF(*point))
                p.drawPolyline(polyline)

        p.end()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    ui = TrackerViewerAux_GUI()
    ui.show()

    sys.exit(app.exec_())
