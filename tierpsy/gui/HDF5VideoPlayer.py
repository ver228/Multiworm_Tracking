import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from tierpsy.gui.HDF5VideoPlayer_ui import Ui_HDF5VideoPlayer

import tables
import os
import numpy as np
import copy


def setChildrenFocusPolicy(obj, policy):
    # recursively change the focus policy of all the objects in the widgets
    def recursiveSetChildFocusPolicy(parentQWidget):
        for childQWidget in parentQWidget.findChildren(QtWidgets.QWidget):
            childQWidget.setFocusPolicy(policy)
            recursiveSetChildFocusPolicy(childQWidget)
    recursiveSetChildFocusPolicy(obj)


class HDF5VideoPlayer_GUI(QtWidgets.QMainWindow):

    def __init__(self, ui=''):
        super().__init__()

        # Set up the user interface from Designer.
        if not ui:
            self.ui = Ui_HDF5VideoPlayer()
        else:
            self.ui = ui

        self.ui.setupUi(self)

        self.isPlay = False
        self.fid = -1
        self.image_group = -1
        self.videos_dir = ''

        self.h5path = self.ui.comboBox_h5path.itemText(0)

        self.ui.pushButton_video.clicked.connect(self.getVideoFile)

        self.ui.playButton.clicked.connect(self.playVideo)
        self.ui.imageSlider.sliderPressed.connect(self.imSldPressed)
        self.ui.imageSlider.sliderReleased.connect(self.imSldReleased)
        self.ui.imageSlider.valueChanged.connect(self.imSldChanged)

        self.ui.spinBox_frame.valueChanged.connect(self.updateFrameNumber)
        self.ui.doubleSpinBox_fps.valueChanged.connect(self.updateFPS)
        self.ui.spinBox_step.valueChanged.connect(self.updateFrameStep)

        self.ui.comboBox_h5path.activated.connect(self.getImGroup)
        self.ui.pushButton_h5groups.clicked.connect(self.updateGroupNames)

        self.updateFPS()
        self.updateFrameStep()

        # SET UP RECURRING EVENTS
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.getNextImage)

        # setup image view as a zoom
        self.mainImage = ViewsWithZoom(self.ui.mainGraphicsView)

        # let drag and drop a file into the video file line edit
        lineEditDragDrop(
            self.ui.lineEdit_video,
            self.updateVideoFile,
            os.path.isfile)

        # make sure the childrenfocus policy is none in order to be able to use
        # the arrow keys
        setChildrenFocusPolicy(self, QtCore.Qt.ClickFocus)

    # Scroller
    def imSldPressed(self):
        self.ui.imageSlider.setCursor(QtCore.Qt.ClosedHandCursor)

    def imSldReleased(self):
        self.ui.imageSlider.setCursor(QtCore.Qt.OpenHandCursor)

    def imSldChanged(self):
        if self.image_group != -1:
            prev_progress_bar = round(
                100 * self.frame_number / self.tot_frames)
            if prev_progress_bar != self.ui.imageSlider.value():
                self.frame_number = int(
                    round((self.tot_frames - 1) * self.ui.imageSlider.value() / 100))
            self.ui.spinBox_frame.setValue(self.frame_number)

    # frame spin box
    def updateFrameNumber(self):
        self.frame_number = self.ui.spinBox_frame.value()
        progress_bar = round(100 * self.frame_number / self.tot_frames)
        if progress_bar != self.ui.imageSlider.value():
            self.ui.imageSlider.setValue(progress_bar)

        self.updateImage()

    # fps spin box
    def updateFPS(self):
        self.fps = self.ui.doubleSpinBox_fps.value()

    # frame steps spin box
    def updateFrameStep(self):
        self.frame_step = self.ui.spinBox_step.value()

    # Play Button
    def playVideo(self):
        if self.image_group == -1:
            return
        if not self.isPlay:
            self.startPlay()
        else:
            self.stopPlay()

    def startPlay(self):
        self.timer.start(round(1000 / self.fps))
        self.isPlay = True
        self.ui.playButton.setText('Stop')
        self.ui.doubleSpinBox_fps.setEnabled(False)

    def stopPlay(self):
        self.timer.stop()
        self.isPlay = False
        self.ui.playButton.setText('Play')
        self.ui.doubleSpinBox_fps.setEnabled(True)

    # Function to get the new valid frame during video play
    def getNextImage(self):
        self.frame_number += self.frame_step
        if self.frame_number >= self.tot_frames:
            self.frame_number = self.tot_frames - 1
            self.stopPlay()

        self.ui.spinBox_frame.setValue(self.frame_number)

    # update image: get the next frame_number, and resize it to fix in the GUI
    # area
    def updateImage(self):
        self.readCurrentFrame()
        self.mainImage.setPixmap(self.frame_qimg)

    def readCurrentFrame(self):
        if self.image_group == -1:
            self.frame_qimg = -1
            return

        dd = self.ui.mainGraphicsView.size()
        self.label_height = dd.height()
        self.label_width = dd.width()

        self.frame_img = self.image_group[self.frame_number, :, :]

        # equalize and cast if it is not uint8
        if self.frame_img.dtype != np.uint8:
            top = np.max(self.frame_img)
            bot = np.min(self.frame_img)

            self.frame_img = (self.frame_img - bot) * 255. / (top - bot)
            self.frame_img = np.round(self.frame_img).astype(np.uint8)

        self.frame_qimg = self._convert2Qimg(self.frame_img)

    def _convert2Qimg(self, img):
        qimg = QtGui.QImage(
            img.data,
            img.shape[1],
            img.shape[0],
            img.strides[0],
            QtGui.QImage.Format_Indexed8)
        qimg = qimg.convertToFormat(
            QtGui.QImage.Format_RGB32, QtCore.Qt.AutoColor)

        return qimg

    # file dialog to the the hdf5 file
    def getVideoFile(self):
        vfilename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Find HDF5 video file", self.videos_dir, "HDF5 files (*.hdf5);; All files (*)")

        self.updateVideoFile(vfilename)

    def updateVideoFile(self, vfilename):
        # close the if there was another file opened before.
        if self.fid != -1:
            self.fid.close()
            self.mainImage.cleanCanvas()
            self.fid = -1
            self.image_group = -1

        self.vfilename = vfilename
        self.ui.lineEdit_video.setText(self.vfilename)
        self.videos_dir = self.vfilename.rpartition(os.sep)[0] + os.sep

        try:
            self.fid = tables.File(vfilename, 'r')
        except (IOError, tables.exceptions.HDF5ExtError):
            self.fid = -1
            self.image_group = -1
            QtWidgets.QMessageBox.critical(
                self,
                '',
                "The selected file is not a valid .hdf5. Please select a valid file",
                QtWidgets.QMessageBox.Ok)
            return

        self.updateImGroup()

    def updateGroupNames(self):
        valid_groups = []
        for group in self.fid.walk_groups("/"):
            for array in self.fid.list_nodes(group, classname='Array'):
                if array.ndim == 3:
                    valid_groups.append(array._v_pathname)

        if not valid_groups:
            QtWidgets.QMessageBox.critical(
                self,
                '',
                "No valid video groups were found. Dataset with three dimensions and uint8 data type. Closing file.",
                QtWidgets.QMessageBox.Ok)
            self.fid.close()
            self.image_group = -1
            self.mainImage.cleanCanvas()

            return

        self.ui.comboBox_h5path.clear()
        for kk in valid_groups:
            self.ui.comboBox_h5path.addItem(kk)
        self.getImGroup(0)
        self.updateImage()

    def getImGroup(self, index):
        self.h5path = self.ui.comboBox_h5path.itemText(index)
        self.updateImGroup()

    # read a valid groupset from the hdf5
    def updateImGroup(self):
        if self.fid == -1:
            self.image_group = -1
            return

        #self.h5path = self.ui.comboBox_h5path.text()
        if self.h5path not in self.fid:
            self.mainImage.cleanCanvas()
            QtWidgets.QMessageBox.critical(
                self,
                'The groupset path does not exist',
                "The groupset path does not exists. You must specify a valid groupset path",
                QtWidgets.QMessageBox.Ok)
            self.image_group == -1
            return

        self.image_group = self.fid.get_node(self.h5path)
        if len(self.image_group.shape) != 3:
            self.mainImage.cleanCanvas()
            QtWidgets.QMessageBox.critical(
                self,
                'Invalid groupset',
                "Invalid groupset. The groupset must have three dimensions",
                QtWidgets.QMessageBox.Ok)
            self.image_group == -1
            return 

        self.tot_frames = self.image_group.shape[0]
        self.image_height = self.image_group.shape[1]
        self.image_width = self.image_group.shape[2]

        self.ui.spinBox_frame.setMaximum(self.tot_frames - 1)

        self.frame_number = 0
        self.ui.spinBox_frame.setValue(self.frame_number)
        self.updateImage()
        self.mainImage.zoomFitInView()

    def setFileName(self, filename):
        self.filename = filename
        self.ui.lineEdit.setText(filename)

    def resizeEvent(self, event):
        if self.fid != -1:
            self.updateImage()
            self.mainImage.zoomFitInView()

    def keyPressEvent(self, event):
        if self.fid == -1:
            # break no file open, nothing to do here
            return

        key = event.key()

        # Duplicate the frame step size (speed) when pressed  > or .:
        if key == Qt.Key_Greater or key == Qt.Key_Period:
            self.frame_step *= 2
            self.ui.spinBox_step.setValue(self.frame_step)

        # Half the frame step size (speed) when pressed: < or ,
        elif key == Qt.Key_Less or key == Qt.Key_Comma:
            self.frame_step //= 2
            if self.frame_step < 1:
                self.frame_step = 1
            self.ui.spinBox_step.setValue(self.frame_step)

        # Move backwards when  are pressed
        elif key == Qt.Key_Left:
            self.frame_number -= self.frame_step
            if self.frame_number < 0:
                self.frame_number = 0
            self.ui.spinBox_frame.setValue(self.frame_number)

        # Move forward when  are pressed
        elif key == Qt.Key_Right:
            self.frame_number += self.frame_step
            if self.frame_number >= self.tot_frames:
                self.frame_number = self.tot_frames - 1
            self.ui.spinBox_frame.setValue(self.frame_number)

        elif key == Qt.Key_Minus:
            self.mainImage.zoom(-1)
        elif key == Qt.Key_Plus:
            self.mainImage.zoom(1)

        else:
            QtWidgets.QMainWindow.keyPressEvent(self, event)

    def closeEvent(self, event):
        if self.fid != -1:
            self.fid.close()
        super(HDF5VideoPlayer_GUI, self).closeEvent(event)


class ViewsWithZoom():

    def __init__(self, view):
        self._view = view
        self._scene = QtWidgets.QGraphicsScene(self._view)
        self._view.setScene(self._scene)
        self._canvas = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._canvas)

        self._zoom = 0
        self._view.wheelEvent = self.zoomWheelEvent

    # zoom wheel
    def zoomWheelEvent(self, event):
        if not self._canvas.pixmap().isNull():
            numPixels = event.pixelDelta()
            numDegrees = event.angleDelta() / 8

            delta = numPixels if not numPixels.isNull() else numDegrees
            self.zoom(delta.y())

    def zoom(self, zoom_direction):
        if zoom_direction > 0:
            factor = 1.25
            self._zoom += 1
        else:
            factor = 0.8
            self._zoom -= 1
        if self._zoom > 0:
            self._view.scale(factor, factor)
        elif self._zoom == 0:
            self.zoomFitInView()
        else:
            self._zoom = 0

    def zoomFitInView(self):
        rect = QtCore.QRectF(self._canvas.pixmap().rect())
        if not rect.isNull():
            unity = self._view.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
            self._view.scale(1 / unity.width(), 1 / unity.height())
            viewrect = self._view.viewport().rect()
            scenerect = self._view.transform().mapRect(rect)
            factor = min(viewrect.width() / scenerect.width(),
                         viewrect.height() / scenerect.height())
            self._view.scale(factor, factor)
            self._view.centerOn(rect.center())
            self._zoom = 0

    def cleanCanvas(self):
        self._canvas.setPixmap(QtGui.QPixmap())

    def setPixmap(self, frame_qimg):
        if frame_qimg == -1:
            return

        pixmap = QtGui.QPixmap.fromImage(frame_qimg)
        self._canvas.setPixmap(pixmap)


class lineEditDragDrop():

    def __init__(self, line_edit, updateFun, testFun):
        self.updateFun = updateFun
        self.testFun = testFun

        self.line_edit = line_edit
        self.line_edit.setAcceptDrops(True)
        self.line_edit.dragEnterEvent = self.dragEnterEvent
        self.line_edit.dropEvent = self.dropEvent

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            vfilename = url.toLocalFile()
            if self.testFun(vfilename):
                self.updateFun(vfilename)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    ui = HDF5VideoPlayer_GUI()
    ui.show()

    sys.exit(app.exec_())
