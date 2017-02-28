
@setlocal enableextensions enabledelayedexpansion
@echo off

rem call:build_spec
call:build
call:clean

endlocal
goto:eof


:build
pyinstaller --noconfirm  --clean ProcessWormsWorker.spec
pyinstaller --noconfirm --clean MWConsole.spec
goto:eof

:build_spec
pyinstaller --noconfirm  --clean ^
--log-level DEBUG ^
--exclude-module PyQt4 ^
--exclude-module PyQt4.QtCore ^
--exclude-module PyQt4.QtGui ^
--hidden-import=h5py._errors ^
--hidden-import=h5py.defs ^
--hidden-import=h5py.utils ^
--hidden-import=h5py.h5ac ^
--hidden-import=h5py._proxy ^
../scripts/compressSingleWorker.py

pyinstaller --noconfirm  --clean ^
--exclude-module PyQt4 ^
--exclude-module PyQt4.QtCore ^
--exclude-module PyQt4.QtGui ^
--hidden-import=h5py.defs ^
--hidden-import=h5py.utils ^
--hidden-import=h5py.h5ac ^
--hidden-import=h5py._proxy ^
../scripts/trackSingleWorker.py

pyinstaller --noconfirm  --clean --onefile ^
--exclude-module PyQt4 ^
--exclude-module PyQt4.QtCore ^
--exclude-module PyQt4.QtGui ^
--hidden-import=h5py.defs ^
--hidden-import=h5py.utils ^
--hidden-import=h5py.h5ac ^
--hidden-import=h5py._proxy ^
../scripts/MWConsole.py

goto:eof

:clean
for /f %%w in ('python -c "import MWTracker; print(MWTracker.__version__)"') do set MWVER=%%w
for /f %%w in ('python -c "import platform; print(platform.platform())"') do set WINVER=%%w

MOVE .\dist\MWConsole.exe ".\MWConsole %MWVER% - %WINVER%.exe"
RMDIR /S /Q .\dist
RMDIR /S /Q .\build	

goto:eof


