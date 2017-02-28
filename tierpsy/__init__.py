# # -*- coding: utf-8 -*-
# """
# Created on Tue Jul  7 11:29:01 2015

# @author: ajaver
# """
import os
import sys

from .version import __version__

#print(os.environ['PATH'])

try:
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = sys._MEIPASS
except Exception:
    base_path = os.path.dirname(__file__)

AUX_FILES_DIR = os.path.abspath(os.path.join(base_path, 'misc'))
DFLT_PARAMS_PATH = os.path.join(AUX_FILES_DIR, 'param_files')
DFLT_PARAMS_FILES = [x for x in os.listdir(DFLT_PARAMS_PATH) if x.endswith('.json')]


if getattr(sys, 'frozen', False):
    # force qt5 to be the backend of matplotlib.
    # otherwise the pyinstaller packages might have some problems in the
    # binaries.
    import matplotlib
    matplotlib.use('Qt5Agg')

    if os.name == 'nt':
        # load dll for numpy in windows
        import ctypes

        # Override dll search path.
        python_dir = os.path.split(sys.executable)[0]
        ctypes.windll.kernel32.SetDllDirectoryW(
            os.path.join(python_dir, 'Library', 'bin'))

        # Init code to load external dll
        ctypes.CDLL('mkl_avx2.dll')
        ctypes.CDLL('mkl_def.dll')
        ctypes.CDLL('mkl_vml_avx2.dll')
        ctypes.CDLL('mkl_vml_def.dll')

        # Restore dll search path.
        ctypes.windll.kernel32.SetDllDirectoryW(sys._MEIPASS)
else:
    if sys.platform == 'darwin':
        # add homebrew directory to the path
        os.environ["PATH"] += os.pathsep + '/usr/local/bin'
