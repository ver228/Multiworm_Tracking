import json
import os
from functools import partial

import numpy as np
import pandas as pd
import tables
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPixmap, QPainter, QFont, QPen, QPolygonF, QColor
from PyQt5.QtWidgets import QApplication, QMessageBox

from tierpsy.gui.AnalysisProgress import WorkerFunQt, AnalysisProgress
from tierpsy.gui.MWTrackerViewer_ui import Ui_MWTrackerViewer
from tierpsy.gui.TrackerViewerAux import TrackerViewerAux_GUI
from tierpsy.analysis.feat_create.obtainFeatures import getWormFeaturesFilt
from tierpsy.analysis.ske_create.helperIterROI import getWormROI
from tierpsy.analysis.ske_filt.getFilteredSkels import getValidIndexes
from tierpsy.helper.trackProvenance import getGitCommitHash, execThisPoint
from tierpsy.helper.tracker_param import tracker_param


class MWTrackerViewer_GUI(TrackerViewerAux_GUI):

    def __init__(self, ui='', argv=''):
        if not ui:
            super().__init__(Ui_MWTrackerViewer())
        else:
            super().__init__(ui)

        self.vfilename = '' if len(argv) <= 1 else argv[1]

        self.lastKey = ''
        self.isPlay = False
        self.fid = -1
        self.image_group = -1
        self.trajectories_data = -1
        self.traj_for_plot = {}


        self.worm_index_roi1 = 1
        self.worm_index_roi2 = 1
        self.frame_data = -1
        self.h5path = self.ui.comboBox_h5path.itemText(0)

        self.wlab = {'U': 0, 'WORM': 1, 'WORMS': 2, 'BAD': 3, 'GOOD_SKE': 4}
        self.wlabC = {
            self.wlab['U']: Qt.white,
            self.wlab['WORM']: Qt.green,
            self.wlab['WORMS']: Qt.blue,
            self.wlab['BAD']: Qt.darkRed,
            self.wlab['GOOD_SKE']: Qt.darkCyan}

        self.videos_dir = r"/Volumes/behavgenom$/GeckoVideo/MaskedVideos/"
        self.results_dir = ''
        self.skeletons_file = ''
        self.worm_index_type = 'worm_index_manual'
        self.label_type = 'worm_label'

        self.ui.comboBox_ROI1.activated.connect(self.selectROI1)
        self.ui.comboBox_ROI2.activated.connect(self.selectROI2)
        self.ui.checkBox_ROI1.stateChanged.connect(
            partial(self.updateROIcanvasN, 1))
        self.ui.checkBox_ROI2.stateChanged.connect(
            partial(self.updateROIcanvasN, 2))

        self.ui.comboBox_labelType.currentIndexChanged.connect(
            self.selectWormIndexType)

        self.ui.pushButton_feats.clicked.connect(self.getManualFeatures)

        # flags for RW and FF
        self.RW, self.FF = 1, 2
        self.ui.pushButton_ROI1_RW.clicked.connect(
            partial(self.roiRWFF, 1, self.RW))
        self.ui.pushButton_ROI1_FF.clicked.connect(
            partial(self.roiRWFF, 1, self.FF))
        self.ui.pushButton_ROI2_RW.clicked.connect(
            partial(self.roiRWFF, 2, self.RW))
        self.ui.pushButton_ROI2_FF.clicked.connect(
            partial(self.roiRWFF, 2, self.FF))

        self.ui.pushButton_U.clicked.connect(
            partial(self.tagWorm, self.wlab['U']))
        self.ui.pushButton_W.clicked.connect(
            partial(self.tagWorm, self.wlab['WORM']))
        self.ui.pushButton_WS.clicked.connect(
            partial(self.tagWorm, self.wlab['WORMS']))
        self.ui.pushButton_B.clicked.connect(
            partial(self.tagWorm, self.wlab['BAD']))

        self.ui.pushButton_save.clicked.connect(self.saveData)

        self.ui.pushButton_join.clicked.connect(self.joinTraj)
        self.ui.pushButton_split.clicked.connect(self.splitTraj)

        self.showT = {x: self.ui.comboBox_showLabels.findText(x , flags=Qt.MatchContains) 
                                for x in ['hide', 'all', 'filter']}
        self.ui.comboBox_showLabels.setCurrentIndex(self.showT['all'])
        self.ui.comboBox_showLabels.currentIndexChanged.connect(self.updateImage)        
        
        self.drawT = {x: self.ui.comboBox_drawType.findText(x , flags=Qt.MatchContains) 
                                for x in ['boxes', 'traj']}
        self.ui.comboBox_drawType.currentIndexChanged.connect(self._purge_draw_traj)

        # select worm ROI when doubleclick a worm
        self.mainImage._canvas.mouseDoubleClickEvent = self.selectWorm

    def getManualFeatures(self):
        # save the user changes before recalculating anything
        self.saveData()

        #%%
        self.feat_manual_file = self.skeletons_file.replace(
            '_skeletons.hdf5', '_feat_manual.hdf5')

        point_parameters = {
            'func': getWormFeaturesFilt,
            'argkws': {
                'skeletons_file': self.skeletons_file,
                'features_file': self.feat_manual_file,
                'expected_fps': self.expected_fps, #if it is read as np.int64 can give errors in the json serializer
                'is_single_worm': False,
                'use_skel_filter': True,
                'use_manual_join': True,
                'feat_filt_param': self.feat_filt_param,
                'split_traj_time': self.param_default.feats_param['split_traj_time']
                },
                'provenance_file': self.feat_manual_file
            }


        def featManualFun(point_argvs):
            commit_hash = getGitCommitHash()
            execThisPoint('FEAT_MANUAL_CREATE', **point_argvs,
                          commit_hash=commit_hash, cmd_original='GUI')

        trackpoint_worker = WorkerFunQt(
            featManualFun, {
                'point_argvs': point_parameters})
        progress_dialog = AnalysisProgress(trackpoint_worker)
        progress_dialog.setAttribute(Qt.WA_DeleteOnClose)
        progress_dialog.exec_()

    def selectWormIndexType(self):
        # select between automatic and manual worm indexing and label
        if self.ui.comboBox_labelType.currentIndex() == 0:
            self.label_type = 'worm_label'
            self.worm_index_type = 'worm_index_manual'
            self.ui.pushButton_U.setEnabled(True)
            self.ui.pushButton_W.setEnabled(True)
            self.ui.pushButton_WS.setEnabled(True)
            self.ui.pushButton_B.setEnabled(True)
            self.ui.pushButton_join.setEnabled(True)
            self.ui.pushButton_split.setEnabled(True)

        else:
            self.label_type = 'auto_label'
            self.worm_index_type = 'worm_index_auto'
            self.ui.pushButton_U.setEnabled(False)
            self.ui.pushButton_W.setEnabled(False)
            self.ui.pushButton_WS.setEnabled(False)
            self.ui.pushButton_B.setEnabled(False)
            self.ui.pushButton_join.setEnabled(False)
            self.ui.pushButton_split.setEnabled(False)

        self.updateImage()

    def saveData(self):
        '''save data from manual labelling. pytables saving format is more convenient than pandas'''

        if os.name == 'nt':
            # I Windows the paths return by QFileDialog use / as the file
            # separation character. We need to correct it.
            for field_name in ['vfilename', 'skeletons_file']:
                setattr(
                    self, field_name, getattr(
                        self, field_name).replace(
                        '/', os.sep))

        # convert data into a rec array to save into pytables
        trajectories_recarray = self.trajectories_data.to_records(index=False)

        with tables.File(self.skeletons_file, "r+") as ske_file_id:
            # pytables filters.
            table_filters = tables.Filters(
                complevel=5, complib='zlib', shuffle=True, fletcher32=True)

            newT = ske_file_id.create_table(
                '/',
                'trajectories_data_d',
                obj=trajectories_recarray,
                filters=table_filters)

            ske_file_id.remove_node('/', 'trajectories_data')
            newT.rename('trajectories_data')

        self.updateSkelFile(self.skeletons_file)

    def updateSkelFile(self, skeletons_file):
        super().updateSkelFile(skeletons_file)
        
        if not self.skeletons_file or not isinstance(
                self.trajectories_data, pd.DataFrame):
            return

        #correct the index in case it was given before as worm_index_N
        if 'worm_index_N' in self.trajectories_data:
            self.trajectories_data = self.trajectories_data.rename(
                columns={'worm_index_N': 'worm_index_manual'})
        
        if not 'worm_index_manual' in self.trajectories_data:
            self.trajectories_data['worm_label'] = self.wlab['U']
            self.trajectories_data['worm_index_manual'] = self.trajectories_data[
                'worm_index_joined']
        
        #read filter skeletons parameters
        with tables.File(self.skeletons_file, 'r') as skel_fid:

            # if any of this fields is missing load the default parameters
            self.param_default = tracker_param()
            try:
                ss = skel_fid.get_node('/provenance_tracking/ske_filt').read()
                ss = json.loads(ss.decode("utf-8"))
                saved_func_args = json.loads(ss['func_arguments'])

                self.feat_filt_param = {
                x: saved_func_args[x] for x in [
                'min_num_skel',
                'bad_seg_thresh',
                'min_displacement']}
            except (KeyError, tables.exceptions.NoSuchNodeError):
                self.feat_filt_param = self.param_default.feat_filt_param

        try:
            #read expected frames per second
            with tables.File(self.vfilename, 'r') as mask_fid:
                self.expected_fps = int(mask_fid.get_node('/mask')._v_attrs['expected_fps'])  
        except (OSError, tables.exceptions.NoSuchNodeError, AttributeError, KeyError):
            self.expected_fps = self.param_default.expected_fps


        #TODO: THIS IS NOT REALLY THE INDEX I USE IN THE FEATURES FILES. I NEED A MORE CLEVER WAY TO SEE WHAT I AM REALLY FILTERING.
        dd = {x:self.feat_filt_param[x] for x in ['min_num_skel', 'bad_seg_thresh', 'min_displacement']}
        good_traj_index, _ = getValidIndexes(self.skeletons_file, **dd)
        self.trajectories_data['is_valid_index'] = self.trajectories_data[self.worm_index_type].isin(good_traj_index)
        
        self.traj_time_grouped = self.trajectories_data.groupby('frame_number')

        self.traj_for_plot = {} #delete previous plotted trajectories
        self.updateImage()

    # update image
    def updateImage(self):
        if self.image_group == -1:
            return

        super(TrackerViewerAux_GUI, self).readCurrentFrame()
        self.img_h_ratio = self.frame_qimg.height() / self.image_height
        self.img_w_ratio = self.frame_qimg.width() / self.image_width

        # read the data of the particles that exists in the frame
        self.frame_data = self.getFrameData(self.frame_number)

        #draw extra info only if the worm_index_type is valid
        if self.worm_index_type in self.frame_data: 
            # draw the boxes in each of the trajectories found
            if self.ui.comboBox_showLabels.currentIndex() != self.showT['hide'] and self.label_type in self.frame_data:
                self.drawROI(self.frame_qimg)
            
            self.updateROIcanvasN(1)
            self.updateROIcanvasN(2)
        
        # create the pixmap for the label
        self.mainImage.setPixmap(self.frame_qimg)

    def drawROI(self, image):
        '''
        Draw traj worm trajectory.
        '''

        #continue only if the frame_data is a pandas dataframe it is larger than 0 
        #and the selected label_type is a column in the frame_data.
        if len(self.frame_data) == 0 or not self.label_type in self.frame_data:
            return

        self.img_h_ratio = image.height() / self.image_height
        self.img_w_ratio = image.width() / self.image_width

        
        painter = QPainter()
        painter.begin(image)

        fontsize = max(1, max(image.height(), image.width()) // 120)
        penwidth = max(1, max(image.height(), image.width()) // 800)
        penwidth = penwidth if penwidth % 2 == 1 else penwidth + 1

        new_traj = {}
        for row_id, row_data in self.frame_data.iterrows():
            x = row_data['coord_x']
            y = row_data['coord_y']
            # check if the coordinates are nan
            if not (x == x) or not (y == y):
                continue

            #if select between showing filtered index or not
            if self.ui.comboBox_showLabels.currentIndex() == self.showT['filter'] and not row_data['is_valid_index']:
                continue

            traj_ind = int(row_data[self.worm_index_type])
            x = int(round(x * self.img_h_ratio))
            y = int(round(y * self.img_w_ratio))
            label_type = self.wlabC[int(row_data[self.label_type])]
            roi_size = row_data['roi_size']

            cb_ind = self.ui.comboBox_drawType.currentIndex()
            if cb_ind == self.drawT['boxes']:
                self._draw_boxes(painter, traj_ind, x, y, roi_size, label_type, penwidth, fontsize)
            elif cb_ind == self.drawT['traj']:
                self._draw_trajectories(painter, new_traj, traj_ind, x, y, penwidth)
            
        painter.end()
        self.traj_for_plot = new_traj

    def _purge_draw_traj(self):
        self.traj_for_plot = {}
        self.updateImage()
        

    def _draw_trajectories(self, painter, new_traj, traj_ind, x, y, penwidth):
        if not traj_ind in self.traj_for_plot:
            new_traj[traj_ind] = {'col':QColor(*np.random.randint(50, 230, 3)),
                        'p':QPolygonF()}
        else:
            new_traj[traj_ind] = self.traj_for_plot[traj_ind]

        new_traj[traj_ind]['p'].append(QPointF(x,y))
            
        col = new_traj[traj_ind]['col']
        pen = QPen()
        pen.setWidth(penwidth)
        pen.setColor(col)
        painter.setPen(pen)

        painter.drawPolyline(new_traj[traj_ind]['p'])
        painter.drawEllipse(x,y, penwidth, penwidth)

    def _draw_boxes(self, painter, traj_ind, x, y, roi_size, label_type, penwidth, fontsize):
        '''
        Draw traj worm trajectory.
        '''
        pen = QPen(label_type)
        pen.setWidth(penwidth)
        painter.setPen(pen)
        painter.setFont(QFont('Decorative', fontsize))

        painter.drawText(x, y, str(traj_ind))

        bb = roi_size * self.img_w_ratio
        painter.drawRect(x - bb / 2, y - bb / 2, bb, bb)


    # update zoomed ROI
    def selectROI1(self, index):
        try:
            self.worm_index_roi1 = int(self.ui.comboBox_ROI1.itemText(index))
        except ValueError:
            self.worm_index_roi1 = -1

        self.updateROIcanvasN(1)

    def selectROI2(self, index):
        try:
            self.worm_index_roi2 = int(self.ui.comboBox_ROI2.itemText(index))
        except ValueError:
            self.worm_index_roi2 = -1
        self.updateROIcanvasN(2)

    def updateROIcanvasN(self, n_canvas):
        if n_canvas == 1:
            self.updateROIcanvas(
                self.ui.wormCanvas1,
                self.worm_index_roi1,
                self.ui.comboBox_ROI1,
                self.ui.checkBox_ROI1.isChecked())
        elif n_canvas == 2:
            self.updateROIcanvas(
                self.ui.wormCanvas2,
                self.worm_index_roi2,
                self.ui.comboBox_ROI2,
                self.ui.checkBox_ROI2.isChecked())

    # function that generalized the updating of the ROI
    def updateROIcanvas(
            self,
            wormCanvas,
            worm_index_roi,
            comboBox_ROI,
            isDrawSkel):
        if not isinstance(self.frame_data, pd.DataFrame):
            # no trajectories data presented, nothing to do here
            wormCanvas.clear()
            return

        # update valid index for the comboBox
        comboBox_ROI.clear()
        comboBox_ROI.addItem(str(worm_index_roi))
        
        for ind in self.frame_data[self.worm_index_type].data:
            comboBox_ROI.addItem(str(ind))

        # extract individual worm ROI
        good = self.frame_data[self.worm_index_type] == worm_index_roi
        row_data = self.frame_data.loc[good].squeeze()

        if row_data.size == 0 or np.isnan(
                row_data['coord_x']) or np.isnan(
                row_data['coord_y']):
            # invalid data nothing to do here
            wormCanvas.clear()
            return

        worm_img, roi_corner = getWormROI(self.frame_img, row_data['coord_x'], row_data[
                                          'coord_y'], row_data['roi_size'])
        
        roi_ori_size = worm_img.shape

        worm_img = np.ascontiguousarray(worm_img)
        worm_qimg = self._convert2Qimg(worm_img)

        canvas_size = min(wormCanvas.height(), wormCanvas.width())
        worm_qimg = worm_qimg.scaled(
            canvas_size, canvas_size, Qt.KeepAspectRatio)

        worm_qimg = self.drawSkelResult(worm_img, worm_qimg, row_data, 
            isDrawSkel, roi_corner, read_center=False)
        
        pixmap = QPixmap.fromImage(worm_qimg)
        wormCanvas.setPixmap(pixmap)

    def selectWorm(self, event):

        x = event.pos().x()
        y = event.pos().y()

        if not isinstance(
                self.frame_data,
                pd.DataFrame) or len(
                self.frame_data) == 0:
            return

        x /= self.img_w_ratio
        y /= self.img_h_ratio
        R = (x - self.frame_data['coord_x'])**2 + \
            (y - self.frame_data['coord_y'])**2

        ind = R.idxmin()

        good_row = self.frame_data.loc[ind]
        if np.sqrt(R.loc[ind]) < good_row['roi_size']:
            worm_ind = int(good_row[self.worm_index_type])

            if self.ui.radioButton_ROI1.isChecked():
                self.worm_index_roi1 = worm_ind
                self.updateROIcanvasN(1)

            elif self.ui.radioButton_ROI2.isChecked():
                self.worm_index_roi2 = worm_ind
                self.updateROIcanvasN(2)

    def tagWorm(self, label_ind):
        if not self.worm_index_type == 'worm_index_manual':
            return
        if self.ui.radioButton_ROI1.isChecked():
            worm_ind = self.worm_index_roi1
        elif self.ui.radioButton_ROI2.isChecked():
            worm_ind = self.worm_index_roi2

        if not isinstance(self.frame_data, pd.DataFrame):
            return

        if not worm_ind in self.frame_data['worm_index_manual'].values:
            QMessageBox.critical(
                self,
                'The selected worm is not in this frame.',
                'Select a worm in the current frame to label.',
                QMessageBox.Ok)
            return

        good = self.trajectories_data['worm_index_manual'] == worm_ind
        self.trajectories_data.loc[good, 'worm_label'] = label_ind
        self.updateImage()

    # move to the first or the last frames of a trajectory
    def roiRWFF(self, n_roi, rwff):

        if not isinstance(self.frame_data, pd.DataFrame):
            return

        if n_roi == 1:
            worm_ind = self.worm_index_roi1
        else:
            worm_ind = self.worm_index_roi2

        # use 1 for rewind RW or 2 of fast forward
        good = self.trajectories_data[self.worm_index_type] == worm_ind
        frames = self.trajectories_data.loc[good, 'frame_number']

        if frames.size == 0:
            return

        if rwff == 1:
            self.frame_number = frames.min()
        elif rwff == 2:
            self.frame_number = frames.max()

        self.ui.spinBox_frame.setValue(self.frame_number)

    def joinTraj(self):
        if not self.worm_index_type == 'worm_index_manual':
            return

        worm_ind1 = self.worm_index_roi1
        worm_ind2 = self.worm_index_roi2

        if worm_ind1 == worm_ind2:
            QMessageBox.critical(
                self,
                'Cannot join the same trajectory with itself',
                'Cannot join the same trajectory with itself.',
                QMessageBox.Ok)
            return

        index1 = (self.trajectories_data[
                  'worm_index_manual'] == worm_ind1).values
        index2 = (self.trajectories_data[
                  'worm_index_manual'] == worm_ind2).values

        # if the trajectories do not overlap they shouldn't have frame_number
        # indexes in commun
        frame_number = self.trajectories_data.loc[
            index1 | index2, 'frame_number']

        if frame_number.size != np.unique(frame_number).size:
            QMessageBox.critical(
                self,
                'Cannot join overlaping trajectories',
                'Cannot join overlaping trajectories.',
                QMessageBox.Ok)
            return

        if not (worm_ind1 in self.frame_data[
                'worm_index_manual'].values or worm_ind2 in self.frame_data['worm_index_manual'].values):
            reply = QMessageBox.question(
                self,
                'Message',
                "The none of the selected worms to join is not in this frame. Are you sure to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)

            if reply == QMessageBox.No:
                return

        # get the first row for each segment to extract some data
        first_row1 = self.trajectories_data.loc[index1, :].iloc[0]
        first_row2 = self.trajectories_data.loc[index2, :].iloc[0]

        # join trajectories
        self.trajectories_data.loc[
            index2, 'worm_label'] = first_row1['worm_label']
        self.trajectories_data.loc[index2, 'worm_index_manual'] = worm_ind1

        self.worm_index_roi1 = worm_ind1
        self.worm_index_roi2 = worm_ind1
        self.updateImage()

        self.ui.spinBox_join1.setValue(worm_ind1)
        self.ui.spinBox_join2.setValue(worm_ind1)

    def splitTraj(self):
        if not self.worm_index_type == 'worm_index_manual':
            return

        if self.ui.radioButton_ROI1.isChecked():
            worm_ind = self.worm_index_roi1  # self.ui.spinBox_join1.value()
        elif self.ui.radioButton_ROI2.isChecked():
            worm_ind = self.worm_index_roi2

        if not worm_ind in self.frame_data['worm_index_manual'].data:
            QMessageBox.critical(
                self,
                'Worm index is not in the current frame.',
                'Worm index is not in the current frame. Select a valid index.',
                QMessageBox.Ok)
            return

        last_index = self.trajectories_data['worm_index_manual'].max()

        new_ind1 = last_index + 1
        new_ind2 = last_index + 2

        good = self.trajectories_data['worm_index_manual'] == worm_ind
        frames = self.trajectories_data.loc[good, 'frame_number']
        frames = frames.sort_values(inplace=False)

        good = frames < self.frame_number
        index1 = frames[good].index
        index2 = frames[~good].index
        self.trajectories_data.ix[index1, 'worm_index_manual'] = new_ind1
        self.trajectories_data.ix[index2, 'worm_index_manual'] = new_ind2

        self.worm_index_roi1 = new_ind1
        self.worm_index_roi2 = new_ind2
        self.updateImage()

        self.ui.spinBox_join1.setValue(new_ind1)
        self.ui.spinBox_join2.setValue(new_ind2)

    # change frame number using the keys
    def keyPressEvent(self, event):
        # select uchange the radio button pression the up and down keys
        if event.key() == Qt.Key_Up:
            self.ui.radioButton_ROI1.setChecked(True)
        elif event.key() == Qt.Key_Down:
            self.ui.radioButton_ROI2.setChecked(True)

        # undefined: u
        if event.key() == Qt.Key_U:
            self.tagWorm(self.wlab['U'])
        # worm: w
        elif event.key() == Qt.Key_W:
            self.tagWorm(self.wlab['WORM'])
        # worm cluster: c
        elif event.key() == Qt.Key_C:
            self.tagWorm(self.wlab['WORMS'])
        # bad: b
        elif event.key() == Qt.Key_B:
            self.tagWorm(self.wlab['BAD'])
        # s
        elif event.key() == Qt.Key_J:
            self.joinTraj()
        # j
        elif event.key() == Qt.Key_S:
            self.splitTraj()

        # go the the start of end of a trajectory
        elif event.key() == Qt.Key_BracketLeft:
            current_roi = 1 if self.ui.radioButton_ROI1.isChecked() else 2
            self.roiRWFF(current_roi, self.RW)
        #[ <<
        elif event.key() == Qt.Key_BracketRight:
            current_roi = 1 if self.ui.radioButton_ROI1.isChecked() else 2
            self.roiRWFF(current_roi, self.FF)

        super().keyPressEvent(event)

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    ui = MWTrackerViewer_GUI(argv=sys.argv)
    ui.show()
    sys.exit(app.exec_())
