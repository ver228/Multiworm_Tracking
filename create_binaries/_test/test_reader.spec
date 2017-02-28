# -*- mode: python -*-

import os
import MWTracker
import open_worm_analysis_toolbox

MWTracker_path = os.path.dirname(MWTracker.__file__)
open_worm_path = os.path.dirname(open_worm_analysis_toolbox.__file__)

added_files = [
(os.path.join(open_worm_path, 'features\\feature_metadata\\features_list.csv'), 
'open_worm_analysis_toolbox\\features\\feature_metadata'),
(os.path.join(open_worm_path, 'features\\master_eigen_worms_n2.mat'), 
'open_worm_analysis_toolbox\\features'),
(os.path.join(MWTracker_path, 'auxFiles\\features_names.csv'), 'auxFiles'),
('C:\\Anaconda3\\Scripts\\ffmpeg.exe', 'auxFiles'),
('C:\\Anaconda3\\Scripts\\ffprobe.exe', 'auxFiles')
]

block_cipher = None

a = Analysis(['test_pyinstaller_reader.py'],
             pathex=['C:\\Users\\Avelino.Avelino_VM\\Documents\\GitHub\\Multiworm_Tracking\\create_binaries\\test'],
             binaries=None,
             datas=None,
             hiddenimports=['h5py._errors', 'h5py.defs', 'h5py.utils', 'h5py.h5ac', 'h5py._proxy'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt4', 'PyQt4.QtCore', 'PyQt4.QtGui'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

if True:
  exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='test_reader_file',
          debug=False,
          strip=False,
          upx=True,
          console=True )
else:
  exe = EXE(pyz,
            a.scripts,
            exclude_binaries=True,
            name='test_reader',
            debug=False,
            strip=False,
            upx=True,
            console=True )
  coll = COLLECT(exe,
                 a.binaries,
                 a.zipfiles,
                 a.datas,
                 strip=False,
                 upx=True,
                 name='test_reader')
