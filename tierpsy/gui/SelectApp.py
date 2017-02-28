
from functools import partial
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt

from tierpsy.gui.SelectApp_ui import Ui_SelectApp
from tierpsy.gui.GetMaskParams import GetMaskParams_GUI
from tierpsy.gui.MWTrackerViewer import MWTrackerViewer_GUI
from tierpsy.gui.SWTrackerViewer import SWTrackerViewer_GUI
from tierpsy.gui.BatchProcessing import BatchProcessing_GUI


class SelectApp(QMainWindow):
    def __init__(self):
        super(SelectApp, self).__init__()
        self.ui = Ui_SelectApp()
        self.ui.setupUi(self)

        self.ui.pushButton_paramGUI.clicked.connect(
            partial(self.appCall, GetMaskParams_GUI))
        self.ui.pushButton_batchProcess.clicked.connect(
            partial(self.appCall, BatchProcessing_GUI))
        self.ui.pushButton_MWViewer.clicked.connect(
            partial(self.appCall, MWTrackerViewer_GUI))
        self.ui.pushButton_SWViewer.clicked.connect(
            partial(self.appCall, SWTrackerViewer_GUI))

    def appCall(self, appFun):
        ui = appFun()
        ui.show()
        ui.setAttribute(Qt.WA_DeleteOnClose)

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    ui = SelectApp()
    ui.show()
    sys.exit(app.exec_())
