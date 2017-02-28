import os
import sys


from tierpsy.gui.HDF5VideoPlayer import HDF5VideoPlayer_GUI
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)

    ui = HDF5VideoPlayer_GUI()
    ui.show()

    sys.exit(app.exec_())
