# -*- mode: python -*-

block_cipher = None


a = Analysis(['test_pyinstaller.py'],
             pathex=['/Users/ajaver/Documents/GitHub/Multiworm_Tracking/create_binaries/test'],
             binaries=[],
             datas=[],
             hiddenimports=['h5py.defs', 'h5py.utils', 'h5py.h5ac', 'h5py._proxy'],
             hookspath=[],
             runtime_hooks=[],
             excludes=['PyQt4', 'PyQt4.QtCore', 'PyQt4.QtGui'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='test_pyinstaller',
          debug=False,
          strip=False,
          upx=True,
          console=True )
