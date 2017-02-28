all : setup.py c_circCurvature.c c_curvspace.c circCurvature.pyx cleanWorm_cython.pyx curvspace.pyx linearSkeleton_cython.pyx segWorm_cython.pyx
	python3 setup.py build_ext --inplace -I`python3 -c "import numpy; print(numpy.get_include())"`
	

.PHONY : clean
clean :
	rm circCurvature.c cleanWorm_cython.c curvspace.c linearSkeleton_cython.c segWorm_cython.c
	rm -R build