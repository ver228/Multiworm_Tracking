

from tierpsy.helper.params.docs_summarizer_param import summarizer_args_dflt, summarizer_args_info, summarizer_valid_options

from tierpsy.gui.AnalysisProgress import AnalysisProgress, WorkerFunQt
from tierpsy.gui.GetAllParameters import ParamWidgetMapper
from tierpsy.gui.HDF5VideoPlayer import LineEditDragDrop
from tierpsy.gui.Summarizer_ui import Ui_Summarizer

from tierpsy.summary.collect import calculate_summaries

import os
from PyQt5 import QtWidgets


class Summarizer_GUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Summarizer()
        self.ui.setupUi(self)
        self.mapper = ParamWidgetMapper(self.ui, 
                default_param=summarizer_args_dflt,
                info_param=summarizer_args_info, 
                valid_options=summarizer_valid_options
                )


        self.ui.pushButton_start.clicked.connect(self.startAnalysis)
        self.ui.pushButton_rootdir.clicked.connect(self.getRootDir)
        self.ui.p_summary_type.currentIndexChanged.connect(self.viewFoldArgs)
        self.ui.p_feature_type.currentIndexChanged.connect(self.viewTimeWindows)

        LineEditDragDrop(self.ui.p_root_dir, self.updateRootDir, os.path.isdir)

        self.viewFoldArgs()

    def getRootDir(self):
        root_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Selects the root directory where the features files are located.",
            self.mapper['root_dir'])
        if root_dir:
            self.updateRootDir(root_dir)

    def updateRootDir(self, x):
        self.mapper['root_dir'] = x

    def viewFoldArgs(self):
        if self.mapper['summary_type'] == 'plate_augmented':
            self.ui.FoldArgs.show()
        else:
            self.ui.FoldArgs.hide()

    def viewTimeWindows(self):
        if self.mapper['feature_type'] == 'tierpsy':
            self.ui.TimeWindows.show()
        else:
            self.ui.TimeWindows.hide()

    def startAnalysis(self):
        process_args = {k:self.mapper[k] for k in self.mapper}
        analysis_worker = WorkerFunQt(calculate_summaries, process_args)
        progress = AnalysisProgress(analysis_worker)
        progress.exec_()



if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication(sys.argv)
    ui = Summarizer_GUI()
    ui.show()
    sys.exit(app.exec_())
