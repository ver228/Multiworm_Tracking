import json
import os
from functools import partial

import cv2
import numpy as np
from tierpsy.analysis.compress.compressVideo import getROIMask, selectVideoReader, reduceBuffer
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication, QMainWindow, \
QFileDialog, QMessageBox, QCheckBox, QButtonGroup, QLabel

from tierpsy.gui.AnalysisProgress import WorkerFunQt, AnalysisProgress
from tierpsy.gui.GetAllParameters import GetAllParameters, save_params_json
from tierpsy.gui.GetMaskParams_ui import Ui_GetMaskParams
from tierpsy.gui.HDF5VideoPlayer import lineEditDragDrop, ViewsWithZoom, setChildrenFocusPolicy

from tierpsy.analysis.compress.BackgroundSubtractor import BackgroundSubtractor
from tierpsy.processing.ProcessWormsWorker import ProcessWormsWorker
from tierpsy.processing.batchProcHelperFunc import getDefaultSequence
from tierpsy.helper.tracker_param import tracker_param


class GetMaskParams_GUI(QMainWindow):

    def __init__(self, default_videos_dir='', scripts_dir=''):
        self.mask_files_dir = ''
        self.results_dir = ''

        self.video_file = ''
        self.json_file = ''

        self.Ibuff = np.zeros(0)
        self.Ifull = np.zeros(0)
        self.IsubtrB = np.zeros(0)
        self.bgnd_subtractor = None
        self.vid = None
        self.frame_number = 0

        super(GetMaskParams_GUI, self).__init__()
        
        # Set up the user interface from Designer.
        self.ui = Ui_GetMaskParams()
        self.ui.setupUi(self)

        def _link_slider_spinbox(slider, spinbox, connect_func):
            slider.sliderReleased.connect(connect_func)
            spinbox.editingFinished.connect(connect_func)
            slider.valueChanged.connect(spinbox.setValue)
            spinbox.valueChanged.connect(slider.setValue)

        for field in ['min_area', 'max_area', 'block_size', 'thresh_C', 'dilation_size']:
            slider = getattr(self.ui, 'horizontalSlider_' + field)
            spinbox = getattr(self.ui, 'spinBox_' + field)
            _link_slider_spinbox(slider, spinbox, self.updateMask)

        self.ui.checkBox_keepBorderData.stateChanged.connect(self.updateMask)        
        self.ui.spinBox_buff_size.editingFinished.connect(self.updateBuffSize)
        self.ui.checkBox_isLightBgnd.stateChanged.connect(self.updateReducedBuff)

        self.ui.spinBox_bgnd_buff_size.editingFinished.connect(self.delBSubstractor)
        self.ui.spinBox_bgnd_frame_gap.editingFinished.connect(self.delBSubstractor)
        


        self.ui.pushButton_video.clicked.connect(self.getVideoFile)
        self.ui.pushButton_results.clicked.connect(self.getResultsDir)
        self.ui.pushButton_mask.clicked.connect(self.getMasksDir)
        self.ui.pushButton_paramFile.clicked.connect(self.getParamFile)
        self.ui.pushButton_saveParam.clicked.connect(self.saveParamFile)

        self.ui.pushButton_next.clicked.connect(self.getNextChunk)
        self.ui.pushButton_start.clicked.connect(self.startAnalysis)

        self.ui.pushButton_moreParams.clicked.connect(self.getMoreParams)
        
        #remove tabs for the moment. I need to fix this it later
        self.ui.tabWidget.setCurrentIndex(self.ui.tabWidget.indexOf(self.ui.tab_mask))
        self.tab_keys = dict(mask=self.ui.tabWidget.indexOf(self.ui.tab_mask),
                         bgnd=self.ui.tabWidget.indexOf(self.ui.tab_bgnd),
                         analysis=self.ui.tabWidget.indexOf(self.ui.tab_analysis))
        
        #self.ui.tabWidget.removeTab(self.ui.tabWidget.indexOf(self.ui.tab_analysis))
        self.ui.tab_analysis.setEnabled(False)

        #self.ui.checkBox_subtractBackground.clicked.connect(self.updateMask)
        self.ui.radioButton_analysisType_worm.clicked.connect(lambda: self.ui.groupBox_zebrafishOptions.hide())
        self.ui.radioButton_analysisType_zebrafish.clicked.connect(lambda: self.ui.groupBox_zebrafishOptions.show())
        self.ui.checkBox_autoDetectTailLength.clicked.connect(self.updateFishLengthOptions)

        self.ui.checkBox_is_bgnd_subtraction.stateChanged.connect(self.updateISubtrB)
        self.ui.tabWidget.currentChanged.connect(self.updateROIs)

        self.mapper = ParamWidgetMapper({
            'max_area': self.ui.spinBox_max_area,
            'min_area': self.ui.spinBox_min_area,
            'thresh_block_size': self.ui.spinBox_block_size,
            'thresh_C': self.ui.spinBox_thresh_C,
            'dilation_size': self.ui.spinBox_dilation_size,
            'keep_border_data': self.ui.checkBox_keepBorderData,
            'is_light_background': self.ui.checkBox_isLightBgnd,
            'fps': self.ui.spinBox_fps,
            'compression_buff': self.ui.spinBox_buff_size,
            'is_bgnd_subtraction': self.ui.checkBox_is_bgnd_subtraction,
            'bgnd_buff_size' : self.ui.spinBox_bgnd_buff_size,
            'bgnd_frame_gap' : self.ui.spinBox_bgnd_frame_gap,
            'analysis_type': self.ui.buttonGroup_analysisType,
            'zf_num_segments': self.ui.spinBox_zf_numberOfSegments,
            'zf_min_angle': self.ui.spinBox_zf_minAngle,
            'zf_max_angle': self.ui.spinBox_zf_maxAngle,
            'zf_num_angles': self.ui.spinBox_zf_anglesPerSegment,
            'zf_tail_length': self.ui.spinBox_zf_tailLength,
            'zf_tail_detection': self.ui.buttonGroup_zf_tailPointDetectionAlgorithm,
            'zf_prune_retention': self.ui.spinBox_zf_pruneRetention,
            'zf_test_width': self.ui.spinBox_zf_segmentTestWidth,
            'zf_draw_width': self.ui.spinBox_zf_segmentDrawWidth,
            'zf_auto_detect_tail_length': self.ui.checkBox_autoDetectTailLength
        })

        self.videos_dir = default_videos_dir
        if not os.path.exists(self.videos_dir):
            self.videos_dir = ''
        self.updateParamFile('')

        self.ui.lineEdit_mask.setText(self.mask_files_dir)
        self.ui.lineEdit_results.setText(self.results_dir)
        # self.updateBuffSize()

        # setup image view as a zoom
        self.twoViews = twoViewsWithZoom(
            self.ui.graphicsView_full,
            self.ui.graphicsView_mask)

        dd_args = [
            (self.ui.lineEdit_video, self.updateVideoFile, os.path.isfile),
            (self.ui.lineEdit_results, self.updateResultsDir, os.path.isdir),
            (self.ui.lineEdit_mask, self.updateMasksDir, os.path.isdir),
            (self.ui.lineEdit_paramFile, self.updateParamFile, os.path.isfile),
        ]
        for dd_arg in dd_args:
            # let drag and drop a file into the video file line edit
            lineEditDragDrop(*dd_arg)

        # make sure the childrenfocus policy is none in order to be able to use
        # the arrow keys
        setChildrenFocusPolicy(self, Qt.ClickFocus)

        # Hide zebrafish options if Analysis Type is set to 'Worm'
        if not self.ui.radioButton_analysisType_zebrafish.isChecked():
            self.ui.groupBox_zebrafishOptions.hide()
        
        self.is_play = False
        self.ui.pushButton_play.clicked.connect(self.playVideo)
        self.timer = QTimer()
        self.timer.timeout.connect(self.getNextChunk)


    def playVideo(self):
        if self.vid is None:
            return
        if not self.is_play:
            self.startPlay()
        else:
            self.stopPlay()

    def startPlay(self):
        fps = self.mapper['fps']
        compression_buff = self.mapper['compression_buff']
        fps_n = fps/compression_buff
        self.timer.start(round(1000 / fps_n))
        self.is_play = True
        self.ui.pushButton_play.setText('Stop')

    def stopPlay(self):
        self.timer.stop()
        self.is_play = False
        self.ui.pushButton_play.setText('Play')


    def closeEvent(self, event):
        if self.vid is not None:
            self.vid.release()
        super(GetMaskParams_GUI, self).closeEvent(event)

    # update image if the GUI is resized event
    def resizeEvent(self, event):
        self.updateROIs()
        self.twoViews.zoomFitInView()

    def updateBuffSize(self):
        self.buffer_size = int(np.round(self.ui.spinBox_buff_size.value()))

    def getResultsDir(self):
        results_dir = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the analysis results will be stored",
            self.results_dir)
        self.updateResultsDir(results_dir)

    def updateResultsDir(self, results_dir):
        if results_dir:
            self.results_dir = results_dir
            self.ui.lineEdit_results.setText(self.results_dir)

    def getMasksDir(self):
        mask_files_dir = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the hdf5 video will be stored",
            self.mask_files_dir)
        self.updateMasksDir(mask_files_dir)

    def updateMasksDir(self, mask_files_dir):
        if mask_files_dir:
            self.mask_files_dir = mask_files_dir
            self.ui.lineEdit_mask.setText(self.mask_files_dir)

    # file dialog to the the hdf5 file
    def getParamFile(self):
        json_file, _ = QFileDialog.getSaveFileName(
            self, "Find parameters file", self.videos_dir, "JSON files (*.json);; All (*)")
        if json_file:
            self.updateParamFile(json_file)

    # def readAllParam(self):
    def _setDefaultParam(self):
        param = tracker_param()
        widget_param = param.mask_param
        widget_param['fps'] = param.compress_vid_param['expected_fps']
        widget_param['compression_buff'] = param.compress_vid_param['buffer_size']

        if widget_param['compression_buff'] < 0:
            param.compress_vid_param['expected_fps']

        for param_name in widget_param:
            self.mapper.set(param_name, widget_param[param_name])

    def updateParamFile(self, json_file):
        # set the widgets with the default parameters, in case the parameters are not given
        # by the json file.
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as fid:
                    json_str = fid.read()
                    json_param = json.loads(json_str)

            except (OSError, UnicodeDecodeError, json.decoder.JSONDecodeError):
                QMessageBox.critical(
                    self,
                    'Cannot read parameters file.',
                    "Cannot read parameters file. Try another file",
                    QMessageBox.Ok)
                return
        else:
            json_param = {}

        # put reset to the default paramters in the main application. Any paramter not contain
        # in the json file will be keep with the default value.
        self._setDefaultParam()
        # set correct widgets to the values given in the json file
        for param_name in json_param:
            if param_name in self.mapper.param2widget:
                self.mapper.set(param_name, json_param[param_name])

        self.json_file = json_file
        self.ui.lineEdit_paramFile.setText(self.json_file)
        self.updateMask()

    def saveParamFile(self):
        if not self.json_file:
            QMessageBox.critical(
                self,
                'No parameter file name given.',
                'No parameter file name given. Please select name using the "Parameters File" button',
                QMessageBox.Ok)
            return

        if os.path.exists(self.json_file):

            reply = QMessageBox.question(
                self,
                'Message',
                '''The parameters file already exists. Do you want to overwrite it?
            If No the parameters in the existing file will be used instead of the values displayed.''',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No)

            if reply == QMessageBox.No:
                return

        # read all the values in the GUI
        json_param = {x:self.mapper[x] for x in self.mapper.param2widget}
        
        # save data into the json file
        save_params_json(self.json_file, json_param)

        # file dialog to the the hdf5 file
    def getVideoFile(self):
        video_file, _ = QFileDialog.getOpenFileName(
            self, "Find video file", self.videos_dir, "All files (*)")
        self.updateVideoFile(video_file)

    def updateVideoFile(self, video_file):
        if video_file and os.path.exists(video_file):
            try:
                vid = selectVideoReader(video_file)
                if vid.width == 0 or vid.height == 0:
                    raise ValueError
                else:
                    if self.vid is not None:
                        self.vid.release()
                    self.vid, self.im_width, self.im_height = vid, vid.width, vid.height
                    self.bgnd_subtractor = None #make sure this get restarted when a new file is initialized
                    self.frame_number = 0

            except (OSError, ValueError, IOError):
                QMessageBox.critical(
                    self,
                    'Cannot read video file.',
                    "Cannot read video file. Try another file",
                    QMessageBox.Ok)
                return

            self.video_file = video_file
            self.videos_dir = os.path.split(self.video_file)[0]
            self.ui.lineEdit_video.setText(self.video_file)

            # replace Worm_Videos or add a directory for the Results and
            # MaskedVideos directories
            if 'Worm_Videos' in self.videos_dir:
                mask_files_dir = self.videos_dir.replace(
                    'Worm_Videos', 'MaskedVideos')
                results_dir = self.videos_dir.replace('Worm_Videos', 'Results')
            else:
                mask_files_dir = os.path.join(self.videos_dir, 'MaskedVideos')
                results_dir = os.path.join(self.videos_dir, 'Results')

            self.updateResultsDir(results_dir)
            self.updateMasksDir(mask_files_dir)

            # read json file
            json_file = self.video_file.rpartition('.')[0] + '.json'
            self.updateParamFile(json_file)

            # Update interface
            if self.ui.radioButton_analysisType_zebrafish.isChecked():
                self.ui.groupBox_zebrafishOptions.show()
            else:
                self.ui.groupBox_zebrafishOptions.hide()

            # Update enabled/disabled state of fish length options
            self.updateFishLengthOptions()

            # get next chuck
            self.getNextChunk()

            # fit the image to the canvas size
            self.twoViews.zoomFitInView()


    def updateReducedBuff(self):
        if self.Ibuff.size > 0:
            is_light_background = self.mapper['is_light_background']
            
            #update IsubtB image
            if not self.mapper['is_bgnd_subtraction']:
                self.Imin = reduceBuffer(self.Ibuff, is_light_background)
            else:
                Ibuff_b = self.bgnd_subtractor.apply(self.Ibuff, self.frame_number)
                oposite_flag = not is_light_background
                self.Imin = 255-reduceBuffer(Ibuff_b, oposite_flag)
                
            self.updateMask()

    def getNextChunk(self):
        if self.vid is not None:
            # read the buffsize before getting the next chunk
            self.updateBuffSize()

            self.Ibuff = np.zeros(
                (self.buffer_size,
                 self.im_height,
                 self.im_width),
                dtype=np.uint8)

            tot = 0
            for ii in range(self.buffer_size):
                # get video frame, stop program when no frame is retrive (end
                # of file)
                ret, image = self.vid.read()
                if ret == 0:
                    if ii == 0:
                        self.updateVideoFile(self.video_file) #restart video
                        ret, image = self.vid.read() #try to read again, if you cannot again just quit
                        if ret == 0: 
                            break
                    else:
                        break
                
                
                if image.ndim == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

                self.Ibuff[ii] = image

                tot += 1
            if tot == 0:
                return
            elif tot < self.buffer_size:
                self.Ibuff = self.Ibuff[:tot]

            self.frame_number += tot
            self.ui.spinBox_frame_number.setValue(self.frame_number)
            self.Ifull = self.Ibuff[0].copy()
            
            
            self._updateISubtrB()
            #reduce buffer after background subtraction
            self.updateReducedBuff()
            

    def _numpy2qimage(self, im_ori):
        return QImage(im_ori.data, im_ori.shape[1], im_ori.shape[0],
                      im_ori.data.strides[0], QImage.Format_Indexed8)

    def updateROIs(self):
        #useful for resizing events
        if self.Ifull.size == 0:
            self.twoViews.cleanCanvas()
        else:
            cur = self.ui.tabWidget.currentIndex()
            if cur == self.tab_keys['mask']:
                I1, I2 = self.Ifull, self.Imask
            elif cur == self.tab_keys['bgnd']:
                I1 = self.Ifull
                I2 = np.zeros_like(self.IsubtrB)
                cv2.normalize(self.IsubtrB,I2,0,255,cv2.NORM_MINMAX)
            else:
                I1, I2 = self.Ifull, self.Ifull

            qimage_roi1 = self._numpy2qimage(I1)
            qimage_roi2 = self._numpy2qimage(I2)
            self.twoViews.setPixmap(qimage_roi1, qimage_roi2)

    def updateMask(self):
        if self.Ifull.size == 0:
            return
        # read parameters used to calculate the mask
        roi_mask_params_str = ['max_area', 'min_area', 'thresh_block_size', 'thresh_C', 
        'dilation_size', 'keep_border_data', 'is_light_background']
        mask_param = {x:self.mapper[x] for x in roi_mask_params_str}
        
        mask = getROIMask(self.Imin.copy(), **mask_param)
        self.Imask = mask * self.Ifull
        self.updateROIs()


    def delBSubstractor(self):
        self.bgnd_subtractor = None
        
    def _updateISubtrB(self):
        if self.vid is None:
            return 

        if self.mapper['is_bgnd_subtraction']:
            if self.bgnd_subtractor is None:
                keys = ['is_light_background', 'bgnd_buff_size', 'bgnd_frame_gap']
                kwargs = {x.replace('bgnd_', ''):self.mapper[x] for x in keys}

                self.bgnd_subtractor = BackgroundSubtractor(self.video_file, **kwargs)
            if self.Ifull.size > 0:
                self.IsubtrB = self.bgnd_subtractor.subtract_bgnd(self.Ifull)

        else:
            self.IsubtrB = self.Ifull

    def updateISubtrB(self):
        self._updateISubtrB()
        self.updateReducedBuff()

    def startAnalysis(self):
        if self.video_file == '' or self.Ifull.size == 0:
            QMessageBox.critical(
                self,
                'Message',
                "No valid video file selected.",
                QMessageBox.Ok)
            return

        self.saveParamFile()

        base_name = os.path.splitext(os.path.split(self.video_file)[-1])[0]
        self.masked_image_file = os.path.join(
            self.mask_files_dir, base_name + '.hdf5')

        if os.name == 'nt':
            # I Windows the paths return by QFileDialog use / as the file
            # separation character. We need to correct it.
            for field_name in [
                'video_file',
                'mask_files_dir',
                'masked_image_file',
                    'results_dir']:
                setattr(
                    self, field_name, getattr(
                        self, field_name).replace(
                        '/', os.sep))
                
        analysis_argvs = {
            'main_file': self.video_file,
            'masks_dir': self.mask_files_dir,
            'results_dir': self.results_dir,
            'analysis_checkpoints' : getDefaultSequence('All'),
            'json_file': self.json_file,
            'cmd_original': 'GUI'}
            
        analysis_worker = WorkerFunQt(
            ProcessWormsWorker, analysis_argvs)
        progress_dialog = AnalysisProgress(analysis_worker)
        progress_dialog.setAttribute(Qt.WA_DeleteOnClose)
        progress_dialog.exec_()

    def getMoreParams(self):
        json_file = self.ui.lineEdit_paramFile.text()
        allparamGUI = GetAllParameters(json_file)
        allparamGUI.file_saved.connect(self.updateParamFile)
        allparamGUI.exec_()

    def updateFishLengthOptions(self):

        val = not self.ui.checkBox_autoDetectTailLength.isChecked()

        self.ui.spinBox_zf_tailLength.setEnabled(val)
        self.ui.label_zf_tailLength.setEnabled(val)

        self.ui.spinBox_zf_numberOfSegments.setEnabled(val)
        self.ui.label_zf_numberOfSegments.setEnabled(val)

        self.ui.spinBox_zf_segmentTestWidth.setEnabled(val)
        self.ui.label_zf_segmentTestWidth.setEnabled(val)

    def keyPressEvent(self, event):
        if self.vid is not None:
            # break no file open, nothing to do here
            return
        key = event.key()
        if key == Qt.Key_Minus:
            self.twoViews.zoom(-1)
        elif key == Qt.Key_Plus:
            self.twoViews.zoom(1)

        else:
            QMainWindow.keyPressEvent(self, event)

class twoViewsWithZoom():

    def __init__(self, view_full, view_mask):
        self.view_full = ViewsWithZoom(view_full)
        self.view_mask = ViewsWithZoom(view_mask)

        self.view_full._view.wheelEvent = self.zoomWheelEvent
        self.view_mask._view.wheelEvent = self.zoomWheelEvent

        # link scrollbars in the graphics view so if one changes the other
        # changes too
        self.hscroll_full = self.view_full._view.horizontalScrollBar()
        self.vscroll_full = self.view_full._view.verticalScrollBar()
        self.hscroll_mask = self.view_mask._view.horizontalScrollBar()
        self.vscroll_mask = self.view_mask._view.verticalScrollBar()
        dd = partial(self.chgScroll, self.hscroll_mask, self.hscroll_full)
        self.hscroll_mask.valueChanged.connect(dd)
        dd = partial(self.chgScroll, self.vscroll_mask, self.vscroll_full)
        self.vscroll_mask.valueChanged.connect(dd)
        dd = partial(self.chgScroll, self.hscroll_full, self.hscroll_mask)
        self.hscroll_full.valueChanged.connect(dd)
        dd = partial(self.chgScroll, self.vscroll_full, self.vscroll_mask)
        self.vscroll_full.valueChanged.connect(dd)

    def chgScroll(self, scroll_changed, scroll2change):
        scroll2change.setValue(scroll_changed.value())

    def zoomWheelEvent(self, event):
        self.view_full.zoomWheelEvent(event)
        self.view_mask.zoomWheelEvent(event)

    def zoom(self, zoom_direction):
        self.view_full.zoom(zoom_direction)
        self.view_mask.zoom(zoom_direction)

    def zoomFitInView(self):
        self.view_full.zoomFitInView()
        self.view_mask.zoomFitInView()

    def setPixmap(self, qimage_full, qimage_mask):
        # for both maps to have the same size
        v_height = min(
            self.view_full._view.height(),
            self.view_mask._view.height())
        v_width = min(
            self.view_full._view.width(),
            self.view_mask._view.width())

        self.view_full._view.resize(v_width, v_height)
        self.view_mask._view.resize(v_width, v_height)

        self.view_full.setPixmap(qimage_full)
        self.view_mask.setPixmap(qimage_mask)

    def cleanCanvas(self):
        self.view_full.cleanCanvas()
        self.view_mask.cleanCanvas()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mousePressed = True
            self._dragPos = event.pos()
            event.accept()

            self.view_full._view.setCursor(Qt.ClosedHandCursor)
            self.view_mask._view.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._mousePressed:
            newPos = event.pos()
            diff = newPos - self._dragPos
            self._dragPos = newPos

            dx = self.view_full._view.horizontalScrollBar().value() - diff.x()
            dy = self.view_full._view.verticalScrollBar().value() - diff.y()
            self.view_full._view.horizontalScrollBar().setValue(dx)
            self.view_full._view.verticalScrollBar().setValue(dy)

            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.view_full._view.setCursor(Qt.OpenHandCursor)
            self.view_mask._view.setCursor(Qt.OpenHandCursor)
            self._mousePressed = False


class ParamWidgetMapper():
    # alows map a parameter name into a widget that allows to recieve user inputs

    def __init__(self, param2widget_dict):
        self.param2widget = param2widget_dict

    def set(self, param_name, value):
        widget = self.param2widget[param_name]
        if isinstance(widget, QCheckBox):
            return widget.setChecked(value)
        elif isinstance(widget, QButtonGroup):
            for button in widget.buttons():
                if button.text().replace(" ", "_").upper() == value:
                    return button.setChecked(True)
        elif isinstance(widget, QLabel):
            return widget.setText(value)
        else:
            return widget.setValue(value)

    def get(self, param_name):
        widget = self.param2widget[param_name]
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QButtonGroup):
            return widget.checkedButton().text().replace(" ", "_").upper()
        elif isinstance(widget, QLabel):
            return widget.text()
        else:
            return widget.value()


    def __getitem__(self, key):
        return self.get(key)

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)

    ui = GetMaskParams_GUI()
    ui.show()

    sys.exit(app.exec_())
