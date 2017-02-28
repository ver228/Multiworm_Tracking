import sys
import os
import pandas as pd
import tables
import h5py
import numpy as np
import cv2

from PyQt5.QtWidgets import QApplication, QWidget

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pylab as plt

import tierpsy
import open_worm_analysis_toolbox

if __name__ == '__main__':
    print(r"%%%%%%% INSTALLATION TESTS %%%%%%%%")
    print('python:', sys.executable)

    print(np.__name__, np.__version__)
    a = np.arange(10)
    print('test:', a)

    print(plt.__name__, plt.__version__)

    print(cv2.__name__, cv2.__version__)

    print(h5py.__name__, h5py.__version__)
    inputFiles = "test.h5"
    with h5py.File(inputFiles, 'w') as inputFileOpen:
        print('good h5py')

    print(tables.__name__, tables.__version__)
    with tables.File(inputFiles, 'w') as inputFileOpen:
        print('good tables')

    os.remove(inputFiles)

    print(pd.__name__, pd.__version__)

    print(tierpsy.__name__, tierpsy.__version__)
    print(open_worm_analysis_toolbox.__name__, open_worm_analysis_toolbox.__version__)

    if False:
        app = QApplication(sys.argv)
        w = QWidget()
        w.resize(250, 150)
        w.move(300, 300)
        w.setWindowTitle('Simple')
        w.show()
        sys.exit(app.exec_())
