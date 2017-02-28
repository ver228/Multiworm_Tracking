#!/bin/bash
set -e

MW_MAIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OPENWORM_DIR=$MW_MAIN_DIR/../open-worm-analysis-toolbox
OPENCV_DIR=$MW_MAIN_DIR/../opencv
OPENCV_VER="3.2.0"

EXAMPLES_LINK="https://imperiallondon-my.sharepoint.com/personal/ajaver_ic_ac_uk/_layouts/15/guestaccess.aspx?guestaccesstoken=ldZ18fLY%2bzlu7XuO9mbKVdyiKoH4naiesqiLXWU4vGQ%3d&docid=0cec4e52f4ccf4d5b8bb3a737020fc12f&rev=1"
EXAMPLES_DIR="$MW_MAIN_DIR/tests/data/"

OS=$(uname -s)

#############
function osx_dependencies {
	xcode-select --install
	#install homebrew and other software used
	ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
	
	#make the current user the owner of homebrew otherewise it can cause some problems
	#sudo chown -R `whoami`:admin /usr/local/bin
	#sudo chown -R `whoami`:admin /usr/local/share
	#brew update
	#brew upgrade

	brew install git
	
	#ffmpeg libraries, needed to install opencv
	brew install ffmpeg --verbose --with-fdk-aac --with-libass --with-libquvi \
	--with-libvorbis --with-libvpx --with-x265 --with-openh264 --with-tools --with-fdk-aac

	#image libraries for opencv
	brew install jpeg libpng libtiff openexr eigen tbb
}

function force_clean_osx {
	rm -Rf $OPENCV_DIR
	rm -Rf $OPENWORM_DIR
	brew uninstall --force cmake python3 git ffmpeg homebrew/science/hdf5 sip pyqt5
}

function brew_python {
	if [[ -z `brew ls --versions python3` ]]; then
		brew install python3
	fi

	if [[ -z `brew ls --versions hdf5` ]]; then
		#required for pytables
		brew install homebrew/science/hdf5
	fi

	#python dependencies
	pip3 install -U numpy tables pandas h5py scipy scikit-learn \
	scikit-image seaborn xlrd gitpython cython matplotlib pyqt5 \
	keras tensorflow
	
	#i prefer to install matplotlib and numpy with homebrew it gives less problems of compatilibity down the road
	#brew install homebrew/python/matplotlib --with-python3
	
	CURRENT_OPENCV_VER=`python3 -c "import cv2; print(cv2.__version__)" 2> /dev/null || true`
	if [[ $OPENCV_VER != $CURRENT_OPENCV_VER ]]; then
		opencv3_cmake
	fi
}

function opencv3_cmake {
	if [[ -z `brew ls --versions cmake` ]]; then
		brew install cmake 
	fi

	echo 'Installing opencv.'
	#there is a brew formula for this, but there are more changes this will work.
	if ! [[ -d $OPENCV_DIR ]] ; then
		cd $MW_MAIN_DIR/..
		git clone https://github.com/Itseez/opencv	
	fi
	
	cd $OPENCV_DIR
	git checkout -f HEAD #$OPENCV_VER
	
	#remove build directory if it existed before
	rm -rf build || : 
	mkdir build && cd build

	#for some weird reason i have to execute make twice or it does not find the python libraries directory
	for i in 1 2
	do
		cmake '"Unix Makefile"' -DBUILD_opencv_python3=ON \
		-DBUILD_opencv_python2=OFF \
		-DPYTHON_EXECUTABLE=`which python3` \
		-DPYTHON3_INCLUDE_DIR=`python3 -c "import sysconfig; print(sysconfig.get_path('platinclude'))"` \
		-DPYTHON3_LIBRARY=`python3 -c "import sysconfig; print(sysconfig.get_path('platstdlib'))"` \
		-DPYTHON3_PACKAGES_PATH=`python3 -c "import sysconfig; print(sysconfig.get_path('platlib'))"` \
		-DPYTHON3_NUMPY_INCLUDE_DIRS=`python3 -c "from numpy.distutils.misc_util import get_numpy_include_dirs; print(get_numpy_include_dirs()[0])"` \
		-DBUILD_TIFF=ON \
		-DWITH_IPP=ON \
		-DWITH_TBB=ON \
		-DWITH_EIGEN=ON \
		-DWITH_V4L=ON \
		-DBUILD_TESTS=OFF \
		-DBUILD_PERF_TESTS=OFF \
		-DWITH_QT=OFF \
		-DINSTALL_PYTHON_EXAMPLES=ON \
		-D INSTALL_C_EXAMPLES=OFF \
		-DCMAKE_BUILD_TYPE=RELEASE \
		..
	done
	make -j24
	make install
	make clean

	#make a dirty test
	python3 -c "import cv2; print(cv2.__version__)"
}

function linux_dependencies {
	case `lsb_release -si` in
		"Ubuntu")
		ubuntu_dependencies
		;;
		"RedHat*"|"CentOS")
		redhat_dependencies
		;;
	esac
}

function ubuntu_dependencies {
	sudo apt-get install -y curl git ffmpeg unzip
	#opencv3 dependencies http://docs.opencv.org/3.0-beta/doc/tutorials/introduction/linux_install/linux_install.html
	#[required]
	sudo apt-get install -y build-essential cmake libgtk2.0-dev pkg-config libavcodec-dev libavformat-dev libswscale-dev
	#[optional]
	sudo apt-get install -y libtbb2 libtbb-dev libjpeg-dev libpng-dev libtiff-dev libjasper-dev libdc1394-22-dev

}

function redhat_dependencies {
	sudo yum -y install git

	# opencv3 dependencies (http://docs.opencv.org/3.0-beta/doc/py_tutorials/py_setup/py_setup_in_fedora/py_setup_in_fedora.html)
	sudo yum -y install gcc gcc-c++ cmake gtk2-devel libdc1394-devel libv4l-devel ffmpeg-devel \
	gstreamer-plugins-base-devel libpng-devel libjpeg-turbo-devel jasper-devel openexr-devel \
	libtiff-devel libwebp-devel tbb-devel eigen3-devel
}

function anaconda_pkgs {
	echo "Installing get_anaconda extra packages..."
	conda install -y python=3.5.2 pip
	conda install -y anaconda-client conda-build numpy matplotlib pytables pandas \
	h5py scipy scikit-learn scikit-image seaborn xlrd cython statsmodels
	pip install gitpython pyqt5 keras 
	conda install -y -c conda-forge tensorflow
}

function build_opencv3_anaconda {
	echo "Installing openCV..."
	conda install -y conda-build
	conda config --add channels menpo
	conda build --no-anaconda-upload installation/menpo_conda-opencv3
	conda install -y --use-local opencv3
	python3 -c "import cv2; print(cv2.__version__)"
}

function opencv_anaconda {
	read -r -p "Would you like to compile openCV? Otherwise I will try to download it. [y/N] " response
	case "$response" in [yY][eE][sS]|[yY])
		OPENCV_CUR_VER=`python3 -c "import cv2; print(cv2.__version__)" 2>/dev/null` || true
		if [[ ! -z "$OPENCV_CUR_VER" ]]; then
			read -r -p "A previous installation of openCV ($OPENCV_CUR_VER) exists. Do you wish to replace it? [y/N] " response
			case "$response" in [yY][eE][sS]|[yY]) 
		    	build_opencv3_anaconda
		    	;;
		    esac
		else
		    build_opencv3_anaconda
		fi
		;;
		*)
	    conda install -y --channel https://conda.anaconda.org/ver228 opencv3
	    ;;
	esac
}

function _anaconda {
	case "${OS}" in
		"Darwin")
		MINICONDA_LINK="https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
		BASH_PROFILE_FILE=$HOME/.bash_profile
		;;
		
		"Linux"*)
		MINICONDA_LINK="https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh"
		BASH_PROFILE_FILE=$HOME/.bashrc
		;;
	esac

	curl -L "$MINICONDA_LINK" -o miniconda_installer.sh
	bash miniconda_installer.sh -b -f -p $HOME/miniconda
	rm -f miniconda_installer.sh
	
	CONDA_PATH="$HOME/miniconda/bin"
	#add the path to the bash profile only if it is not presented on the path
	if [[ ":$PATH:" != "*:$CONDA_PATH:*" ]]; then
        echo "export PATH=$CONDA_PATH:\$PATH" >> $BASH_PROFILE_FILE
        source $BASH_PROFILE_FILE
        export PATH=$CONDA_PATH:$PATH
        hash -r
    fi
}

function get_anaconda {
	if hash conda 2>/dev/null; then
		CONDA_VER=`conda -V`
        read -r -p "A previous installation of Anaconda ($CONDA_VER) exists. Do you wish to overwrite it? [y/N] " response
		case "$response" in [yY][eE][sS]|[yY]) 
        	_anaconda
        	;;
        esac
    else
        _anaconda
    fi

    anaconda_pkgs
    opencv_anaconda
}

function compile_cython {
	cd $MW_MAIN_DIR
	python3 setup.py build_ext --inplace
	python3 setup.py clean --all
}

function setup_modules {
	git clone https://github.com/openworm/open-worm-analysis-toolbox $OPENWORM_DIR || :
	cd $OPENWORM_DIR
	git pull origin HEAD || :
	
	cd $MW_MAIN_DIR
	chmod -R ugo+rx $MW_MAIN_DIR/../open-worm-analysis-toolbox

	USER_CONFIG=$OPENWORM_DIR/open_worm_analysis_toolbox/user_config.py
	if [ ! -f $USER_CONFIG ]; then
	mv $OPENWORM_DIR/open_worm_analysis_toolbox/user_config_example.txt $USER_CONFIG
	fi
	
	cd $OPENWORM_DIR
	python3 setup.py develop
	
	cd $MW_MAIN_DIR
	python3 setup.py develop
}

function download_examples {
	curl -L $EXAMPLES_LINK -o test_data.zip
	rm -rf $EXAMPLES_DIR || : 
	mkdir $EXAMPLES_DIR
	unzip test_data.zip -d $EXAMPLES_DIR
	rm test_data.zip
}

function link_desktop {
	DESKTOLINK="$HOME/Desktop/TierpsyTracker.command"
	echo "python3 $MW_MAIN_DIR/MWTracker_GUI/MWConsole.py; exit" > $DESKTOLINK
	chmod 744 $DESKTOLINK
} 


function exec_all {
	##########
	case "${OS}" in
		"Darwin")
		osx_dependencies || :
		;;
		
		"Linux"*)
		linux_dependencies || :
		;;
	esac

	if [[ $1 == 'brew' ]]; then
		brew_python
	else
		get_anaconda
	fi

	compile_cython
	setup_modules
	download_examples
	link_desktop
}


case $1 in
	""|"--all")
	"exec_all"
	;;
	"--compile_cython")
	compile_cython
	;;
	"--setup_modules")
	setup_modules
	;;
	"--download_examples")
	download_examples
	;;
	"--anaconda")
	get_anaconda
	;;
	"--link_desktop")
	link_desktop
	;;
	*)
	echo "Exiting... Unrecognized argument: $1"
	exit 1
	;;
esac





