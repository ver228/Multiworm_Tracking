import os
import sys

from tierpsy.gui.SelectApp import SelectApp
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)

    ui = SelectApp()
    ui.show()

    sys.exit(app.exec_())
