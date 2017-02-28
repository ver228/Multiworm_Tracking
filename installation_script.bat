:: Install additional python dependecies.
conda install -y anaconda-client conda-build numpy matplotlib pytables pandas h5py scipy scikit-learn scikit-image seaborn xlrd statsmodels
pip install gitpython pyqt5 keras tensorflow

conda install --channel https://conda.anaconda.org/ver228 opencv3
:: conda config --add channels menpo
:: conda build --no-anaconda-upload installation/menpo_conda-opencv3
:: conda install -y --use-local opencv3

:: Install packages
cd ..\open-worm-analysis-toolbox
python setup.py develop
rename .\open_worm_analysis_toolbox\user_config_example.txt user_config.py
cd ..\Multiworm_Tracking
python setup.py develop

:: Test installation
python -c "import cv2; import h5py; import MWTracker; import open_worm_analysis_toolbox"