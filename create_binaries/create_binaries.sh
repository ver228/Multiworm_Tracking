function build {
pyinstaller --noconfirm  --clean ProcessWormsWorker.spec
pyinstaller --noconfirm  --clean MWConsole.spec
}

function build_spec {
pyinstaller --noconfirm  --clean \
--exclude-module PyQt4 \
--exclude-module PyQt4.QtCore \
--exclude-module PyQt4.QtGui \
--hidden-import=h5py.defs \
--hidden-import=h5py.utils \
--hidden-import=h5py.h5ac \
--hidden-import='h5py._proxy' \
../scripts/compressSingleWorker.py


pyinstaller --noconfirm  --onefile --windowed --clean\
--exclude-module PyQt4 \
--exclude-module PyQt4.QtCore \
--exclude-module PyQt4.QtGui \
--hidden-import=h5py.defs \
--hidden-import=h5py.utils \
--hidden-import=h5py.h5ac \
--hidden-import='h5py._proxy' \
../scripts/MWConsole.py
}

function clean {
	MWVER=`python3 -c "import MWTracker; print(MWTracker.__version__)"`
	OSXVER=`python3 -c "import platform; print(platform.platform().replace('Darwin', 'MacOSX'))"`
	mv ./dist/MWConsole.app "./MWConsole $MWVER - $OSXVER+.app"
	rm -Rf ./dist
	rm -Rf ./build	
}

build
clean