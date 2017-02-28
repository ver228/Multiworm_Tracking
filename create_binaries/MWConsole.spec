# -*- mode: python -*-
import os
import sys
import MWTracker
import open_worm_analysis_toolbox


from MWTracker.helper.misc import FFMPEG_CMD, FFPROBE_CMD
from MWTracker.gui import SelectApp

IS_WIN =  (sys.platform == 'win32')
IS_MAC =  (sys.platform == 'darwin')
IS_LINUX =  (sys.platform == 'linux')

#get MWConsole main path
SRC_SCRIPT_PATH = SelectApp.__file__

DST_BUILD=os.path.abspath('.')
CREATE_CONSOLE= IS_WIN #make a separated console only in windows. I have to do this due to a problem with pyinstaller

DEBUG = False

#get additional files
#openworm additional files
open_worm_path = os.path.dirname(open_worm_analysis_toolbox.__file__)

ow_feat = os.path.join('features', 'feature_metadata', 'features_list.csv')
ow_feat_src = os.path.join(open_worm_path, ow_feat)
ow_feat_dst = os.path.join('open_worm_analysis_toolbox', ow_feat)

ow_eigen = os.path.join('features', 'master_eigen_worms_N2.mat')
ow_eigen_src = os.path.join(open_worm_path, ow_eigen)
ow_eigen_dst = os.path.join('open_worm_analysis_toolbox', ow_eigen)

#add ffmpeg and ffprobe
ffmpeg_src = FFMPEG_CMD
ffmpeg_dst = os.path.join('misc', os.path.basename(FFMPEG_CMD))
ffprobe_src = FFPROBE_CMD
ffprobe_dst = os.path.join('misc', os.path.basename(FFPROBE_CMD))

#add prev compiled binary (they should have been ran before)
proccess_bin_dst = 'ProcessWormsWorker'
if IS_WIN:
  proccess_bin_dst += '.exe'
proccess_bin_src = os.path.join(DST_BUILD, 'dist', 'ProcessWormsWorker', proccess_bin_dst)

#create added files
added_datas = [(ow_feat_dst, ow_feat_src, 'DATA'),
        (ow_eigen_dst, ow_eigen_src, 'DATA'),
        (proccess_bin_dst, proccess_bin_src, 'DATA'),
        (ffmpeg_dst, ffmpeg_src, 'DATA'),
        (ffprobe_dst, ffprobe_src, 'DATA')]

#I add the file separator at the end, it makes my life easier later on
MWTracker_path = os.path.dirname(MWTracker.__file__)
MWTracker_path += os.sep

#add all the files in misc
for (dirpath, dirnames, filenames) in os.walk(os.path.join(MWTracker_path, 'misc')):
  for fname in filenames:
    if not fname.startswith('.'):
      fname_src = os.path.join(dirpath, fname)
      fname_dst = fname_src.replace(MWTracker_path, '')
      added_datas.append((fname_dst, fname_src, 'DATA'))

#copy additional dll in windows
if IS_WIN:
  import glob
  conda_bin = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
  libopenh264_src = glob.glob(os.path.join(conda_bin, 'openh264*.dll'))
  libopencv_ffmpeg_src = glob.glob(os.path.join(conda_bin, 'opencv_ffmpeg*.dll'))
  
  for src in libopenh264_src + libopencv_ffmpeg_src:
    dst = os.path.basename(src)
    added_datas.append((dst, src, 'DATA'))
else:
  #copy some missing files from the library (at least in anaconda on OSX)
  for dst in ['libmkl_avx2.dylib', 'libmkl_mc.dylib']:
    src = os.path.realpath(os.path.join(os.path.dirname(sys.executable), '..', 'lib', dst))
    
    if os.path.exists(src):
      added_datas.append((dst, src, 'DATA'))
      print('<>><>>>>>>>>>>', dst)


block_cipher = None
a = Analysis([SRC_SCRIPT_PATH],
             pathex=[DST_BUILD],
             binaries=None,
             datas = None,
             hiddenimports=['h5py.defs', 'h5py.utils', 'h5py.h5ac', 'h5py._proxy',
             'cython', 'sklearn', 'sklearn.neighbors.typedefs'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt4', 'PyQt4.QtCore', 'PyQt4.QtGui'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
#i was having problems with adding datas using Analysis, i decided to add them directly to a.datas
a.datas += added_datas



pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)


if not DEBUG:

  exe = EXE(pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            name='MWConsole',
            debug=False,
            strip=False,
            upx=True,
            console=CREATE_CONSOLE )

  if IS_MAC:

    app = BUNDLE(exe,
                 name='MWConsole.app',
                 icon=None,
                 bundle_identifier=None,
                 info_plist={
                  'CFBundleShortVersionString' : MWTracker.__version__,
                  'NSHighResolutionCapable': 'True'
                  }
                )

else:
  print('DEGUG')
  #do not create a single file if is debug
  exe = EXE(pyz,
            a.scripts,
            exclude_binaries=True,
            name='MWConsole',
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
                 name='MWConsole')
