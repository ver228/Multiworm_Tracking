import os
import json

from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt

from MWTracker.processing.processMultipleFilesFun import processMultipleFilesFun, getResultsDir
from MWTracker.processing.batchProcHelperFunc import getDefaultSequence

from MWTracker.gui.AnalysisProgress import AnalysisProgress, WorkerFunQt
from MWTracker.gui.HDF5VideoPlayer import lineEditDragDrop
from MWTracker.gui.BatchProcessing_ui import Ui_BatchProcessing

from MWTracker.processing.ProcessMultipleFilesParser import CompressMultipleFilesParser, TrackMultipleFilesParser
DFLT_COMPRESS_VALS = CompressMultipleFilesParser.dflt_vals
DFLT_TRACK_VALS = TrackMultipleFilesParser.dflt_vals

from MWTracker.helper.tracker_param import tracker_param

#get default parameters files
from MWTracker import DFLT_PARAMS_PATH, DFLT_PARAMS_FILES

class BatchProcessing_GUI(QMainWindow):

    def __init__(self):
        super(BatchProcessing_GUI, self).__init__()
        self.ui = Ui_BatchProcessing()
        self.ui.setupUi(self)

        self.ui.checkBox_txtFileList.stateChanged.connect(
            self.enableTxtFileListButton)
        self.ui.checkBox_tmpDir.stateChanged.connect(self.enableTmpDirButton)
        self.ui.checkBox_isCompress.stateChanged.connect(
            self.enableCompressInput)
        self.ui.checkBox_isTrack.stateChanged.connect(self.enableTrackInput)

        self.ui.pushButton_txtFileList.clicked.connect(self.getTxtFileList)
        self.ui.pushButton_paramFile.clicked.connect(self.getParamFile)
        self.ui.pushButton_videosDir.clicked.connect(self.getVideosDir)
        self.ui.pushButton_masksDir.clicked.connect(self.getMasksDir)
        self.ui.pushButton_resultsDir.clicked.connect(self.getResultsDir)
        self.ui.pushButton_tmpDir.clicked.connect(self.getTmpDir)
        self.ui.pushButton_start.clicked.connect(self.startAnalysis)

        # print(DFLT_COMPRESS_VALS)
        # print(DFLT_TRACK_VALS)

        self.mask_files_dir = ''
        self.results_dir = ''
        self.videos_dir = ''

        self.ui.checkBox_tmpDir.setChecked(False)
        self.enableTxtFileListButton()
        self.ui.checkBox_tmpDir.setChecked(True)
        self.enableTmpDirButton()

        self.ui.checkBox_isCompress.setChecked(True)
        self.enableCompressInput()
        self.ui.checkBox_isTrack.setChecked(True)
        self.enableTrackInput()

        self.ui.spinBox_numMaxProc.setValue(DFLT_TRACK_VALS['max_num_process'])
        self.ui.lineEdit_patternIn.setText(
            DFLT_COMPRESS_VALS['pattern_include'])
        self.ui.lineEdit_patternExc.setText(
            DFLT_COMPRESS_VALS['pattern_exclude'])


        assert DFLT_COMPRESS_VALS[
            'max_num_process'] == DFLT_TRACK_VALS['max_num_process']
        assert DFLT_COMPRESS_VALS[
            'tmp_dir_root'] == DFLT_TRACK_VALS['tmp_dir_root']
        lineEditDragDrop(
            self.ui.lineEdit_txtFileList,
            self.updateTxtFileList,
            os.path.isfile)
        lineEditDragDrop(
            self.ui.lineEdit_videosDir,
            self.updateVideosDir,
            os.path.isdir)
        lineEditDragDrop(
            self.ui.lineEdit_masksDir,
            self.updateMasksDir,
            os.path.isdir)
        lineEditDragDrop(
            self.ui.lineEdit_resultsDir,
            self.updateResultsDir,
            os.path.isdir)
        lineEditDragDrop(
            self.ui.lineEdit_tmpDir,
            self.updateTmpDir,
            os.path.isdir)

        lineEditDragDrop(
            self.ui.comboBox_paramFile,
            self.updateParamFile,
            os.path.isfile)

        #add default parameters options. Empty list so no json file is select by default
        self.ui.comboBox_paramFile.addItems([''] + DFLT_PARAMS_FILES)

    def enableTxtFileListButton(self):
        is_enable = self.ui.checkBox_txtFileList.isChecked()
        self.ui.pushButton_txtFileList.setEnabled(is_enable)
        self.ui.lineEdit_txtFileList.setEnabled(is_enable)
        self.ui.label_patternIn.setEnabled(not is_enable)
        self.ui.label_patternExc.setEnabled(not is_enable)
        self.ui.lineEdit_patternExc.setEnabled(not is_enable)
        self.ui.lineEdit_patternIn.setEnabled(not is_enable)

        if not is_enable:
            self.updateTxtFileList('')

    def getTxtFileList(self):
        videos_list, _ = QFileDialog.getOpenFileName(
            self, "Select a text file with a list of files to be analyzed.", '', "Text file (*.txt);;All files (*)")
        if os.path.isfile(videos_list):
            self.updateTxtFileList(videos_list)

    def updateTxtFileList(self, videos_list):
        self.videos_list = videos_list
        self.ui.lineEdit_txtFileList.setText(videos_list)

    def enableTmpDirButton(self):
        is_enable = self.ui.checkBox_tmpDir.isChecked()
        self.ui.pushButton_tmpDir.setEnabled(is_enable)
        self.ui.lineEdit_tmpDir.setEnabled(is_enable)

        tmp_dir_root = DFLT_TRACK_VALS['tmp_dir_root'] if is_enable else ''
        self.updateTmpDir(tmp_dir_root)

    def getTmpDir(self):
        tmp_dir_root = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the hdf5 masked videos will be stored",
            self.tmp_dir_root)
        if tmp_dir_root:
            self.updateTmpDir(tmp_dir_root)

    def updateTmpDir(self, tmp_dir_root):
        self.tmp_dir_root = tmp_dir_root
        self.ui.lineEdit_tmpDir.setText(self.tmp_dir_root)

    def enableCompressInput(self):
        is_enable = self.ui.checkBox_isCompress.isChecked()
        self.ui.pushButton_videosDir.setEnabled(is_enable)
        self.ui.lineEdit_videosDir.setEnabled(is_enable)
        if is_enable:
            self.ui.lineEdit_patternIn.setText(
            DFLT_COMPRESS_VALS['pattern_include'])
            self.ui.lineEdit_patternExc.setText(
            DFLT_COMPRESS_VALS['pattern_exclude'])
        elif self.ui.checkBox_isTrack.isChecked():
            self.ui.lineEdit_patternIn.setText(
            DFLT_TRACK_VALS['pattern_include'])
            self.ui.lineEdit_patternExc.setText(
            DFLT_TRACK_VALS['pattern_exclude'])
        

    def enableTrackInput(self):
        is_enable = self.ui.checkBox_isTrack.isChecked()
        self.ui.pushButton_resultsDir.setEnabled(is_enable)
        self.ui.lineEdit_resultsDir.setEnabled(is_enable)
        if is_enable and not self.ui.checkBox_isCompress.isChecked():
            self.ui.lineEdit_patternIn.setText(
            DFLT_TRACK_VALS['pattern_include'])
            self.ui.lineEdit_patternExc.setText(
            DFLT_TRACK_VALS['pattern_exclude'])
        
    def getVideosDir(self):
        videos_dir = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the original video files are stored.",
            self.videos_dir)
        if videos_dir:
            self.updateVideosDir(videos_dir)


    def updateVideosDir(self, videos_dir):
        self.videos_dir = videos_dir
        self.ui.lineEdit_videosDir.setText(self.videos_dir)

        if 'Worm_Videos' in videos_dir:
            mask_files_dir = videos_dir.replace('Worm_Videos', 'MaskedVideos')
        elif 'RawVideos' in videos_dir:
            mask_files_dir = videos_dir.replace('RawVideos', 'MaskedVideos')
        else:
            mask_files_dir = os.path.join(videos_dir, 'MaskedVideos')

        self.updateMasksDir(mask_files_dir)

    def getResultsDir(self):
        results_dir = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the analysis results will be stored",
            self.results_dir)
        if results_dir:
            self.updateResultsDir(results_dir)

    def updateResultsDir(self, results_dir):
        self.results_dir = results_dir
        self.ui.lineEdit_resultsDir.setText(self.results_dir)

    def getMasksDir(self):
        mask_files_dir = QFileDialog.getExistingDirectory(
            self,
            "Selects the directory where the hdf5 masked videos will be stored",
            self.mask_files_dir)
        if mask_files_dir:
            self.updateMasksDir(mask_files_dir)

    def updateMasksDir(self, mask_files_dir):
        if 'MaskedVideos' in mask_files_dir:
            results_dir = mask_files_dir.replace('MaskedVideos', 'Results')
        else:
            results_dir = os.path.join(mask_files_dir, 'Results')


        self.mask_files_dir = mask_files_dir
        self.ui.lineEdit_masksDir.setText(self.mask_files_dir)
        
        self.updateResultsDir(results_dir)

    def getParamFile(self):
        param_file, _ = QFileDialog.getOpenFileName(
            self, "Find parameters file", '', "JSON files (*.json);; All (*)")
        if param_file:
            self.updateParamFile(param_file)

    def updateParamFile(self, param_file):
        # i accept a file if it is empty (the program will call default parameters),
        # but if not I want to check if it is a valid file.
        if param_file:
            try:
                with open(param_file, 'r') as fid:
                    json_str = fid.read()
                    json_param = json.loads(json_str)

                    #find the current index in the combobox, if it preappend it.
                    ind_comb = self.ui.comboBox_paramFile.findText(param_file)
                    if ind_comb == -1:
                        self.ui.comboBox_paramFile.insertItem(-1, param_file)
                        ind_comb = 0

                    self.ui.comboBox_paramFile.setCurrentIndex(ind_comb)


            except (IOError, OSError, UnicodeDecodeError, json.decoder.JSONDecodeError):
                QMessageBox.critical(
                    self,
                    'Cannot read parameters file.',
                    "Cannot read parameters file. Try another file",
                    QMessageBox.Ok)
                return

        self.param_file = param_file

    def startAnalysis(self):
        is_compress = self.ui.checkBox_isCompress.isChecked()
        is_track = self.ui.checkBox_isTrack.isChecked()

        #check before continue
        if not is_compress and not is_track:
            QMessageBox.critical(
                self,
                'Error',
                "Neither compression or selection is selected. No analysis to be done.",
                QMessageBox.Ok)

        video_dir_root = self.ui.lineEdit_videosDir.text()
        mask_dir_root = self.ui.lineEdit_masksDir.text()
        results_dir_root = self.ui.lineEdit_resultsDir.text()
        max_num_process = self.ui.spinBox_numMaxProc.value()
        tmp_dir_root = self.ui.lineEdit_tmpDir.text()
        is_copy_video = self.ui.checkBox_isCopyVideo.isChecked()
        
        
        
        if self.ui.checkBox_txtFileList.isChecked():
            videos_list = self.ui.lineEdit_txtFileList.text()
            pattern_include = ''
            pattern_exclude = ''
        else:
            videos_list = ''
            pattern_include = self.ui.lineEdit_patternIn.text()
            pattern_exclude = self.ui.lineEdit_patternExc.text()

        
        if is_compress:
            if not os.path.exists(video_dir_root):
                QMessageBox.critical(
                    self,
                    'Error',
                    "The videos directory does not exist. Please select a valid directory.",
                    QMessageBox.Ok)
                return
        
        if is_track:
            if not is_compress and not os.path.exists(mask_dir_root):
                QMessageBox.critical(
                    self,
                    'Error',
                    "The masks directory does not exist. Please select a valid directory.",
                    QMessageBox.Ok)
                return
        
        if is_compress and is_track:
            sequence_str = 'all'
        elif is_compress:
            sequence_str = 'compress'
            results_dir_root = mask_dir_root #overwrite the results_dir_root since it will not be used
        elif is_track:
            is_copy_video = True
            sequence_str = 'track'
            video_dir_root = mask_dir_root  #overwrite the video_dir_root in order to copy the mask file to tmp

        #append the root dir if we are using any of the default parameters files. I didn't add the dir before because it is easy to read them in this way.
        json_file = self.ui.comboBox_paramFile.currentText()
        param = tracker_param(json_file)
        analysis_checkpoints = getDefaultSequence(sequence_str, is_single_worm=param.is_single_worm)
        
        process_args = {
          'video_dir_root': video_dir_root,
          'mask_dir_root': mask_dir_root,
          'results_dir_root' : results_dir_root,
          'tmp_dir_root' : tmp_dir_root,
          'json_file' : json_file,
          'videos_list' : videos_list,
          'analysis_checkpoints': analysis_checkpoints,
          'is_copy_video': is_copy_video,
          'pattern_include' : pattern_include,
          'pattern_exclude' : pattern_exclude,
          'max_num_process' : max_num_process,
          'refresh_time' : DFLT_TRACK_VALS['refresh_time'],
          'only_summary' : False,
          'analysis_checkpoints' : analysis_checkpoints
        }

        analysis_worker = WorkerFunQt(processMultipleFilesFun, process_args)
        progress = AnalysisProgress(analysis_worker)
        progress.exec_()

    


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    ui = BatchProcessing_GUI()
    ui.show()
    sys.exit(app.exec_())
