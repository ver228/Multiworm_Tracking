import sys
from PyQt5.QtWidgets import QApplication, QWidget
import pandas as pd
import tables
import cv2

import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pylab as plt
import h5py

if getattr(sys, 'frozen', False):
    print('Frozen.')
    print(sys._MEIPASS)
else:
    print('Not frozen.')

if __name__ == '__main__':
    print('HOLA')

    a = np.arange(10)
    print(a)

    print(cv2.__version__)

    inputFiles = "test.h5"
    with h5py.File(inputFiles, 'w') as inputFileOpen:
        print('good h5py')

    with tables.File(inputFiles, 'w') as inputFileOpen:
        print('good tables')

    print(pd.__version__)

    app = QApplication(sys.argv)

    w = QWidget()
    w.resize(250, 150)
    w.move(300, 300)
    w.setWindowTitle('Simple')
    w.show()
    sys.exit(app.exec_())
