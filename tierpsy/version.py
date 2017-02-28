# # -*- coding: utf-8 -*-
__version__ = '1.2.2'
'''
1.2.2

1.2.1
- Major changes in internal organization of TRAJ_CREATE TRAJ_JOIN
- _trajectories.hdf5 is deprecated. The results of this file are going to be saved in _skeletons.hdf5
- GUI Multi-worm tracker add the option of show trajectories.

1.2.0
- Major refactoring
- Add capability of identifying worms using a pre-trained neural network (not activated by default).
- Separated the creation of the control table in the skeletons file (trajectories_data) from the actually 
skeletons calculation. The point SKEL_INIT now preceds SKEL_CREATION.

1.1.1
- Cumulative changes and bug corrections.

1.1.0 
- Fish tracking and fluorescence tracking.
- major changes in the internal paralization, should make easier to add or remove steps on the tracking.
- correct several bugs.
'''