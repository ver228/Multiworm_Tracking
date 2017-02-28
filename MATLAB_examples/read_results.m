%% TRAJECTORIES DATA FILE
trajectories_file = '/Volumes/behavgenom$/Kezhi/DataSet/Check_Align_samples/Results/npr-2 (ok419)IV on food R_2010_01_25__15_29_03___4___10_trajectories.hdf5';
plate_worms = h5read(trajectories_file, '/plate_worms');
timestamp = h5read(trajectories_file, '/timestamp/raw');
timestamp_time = h5read(trajectories_file, '/timestamp/time');


real_frame = timestamp(plate_worms.frame_number+1); %will match the indexes of segworm. Add one because the python indexing.
real_time = timestamp_time(plate_worms.frame_number+1);
%plot worm area vs frame number
figure
plot(timestamp_time, plate_worms.area)

%plot centroid x coordinate vs frame number
figure
plot(timestamp_time, plate_worms.coord_x)

%% SKELETONS FILE
skeletons_file = '/Volumes/behavgenom$/Kezhi/DataSet/Check_Align_samples/Results/npr-2 (ok419)IV on food R_2010_01_25__15_29_03___4___10_skeletons.hdf5';

skeletons = h5read(skeletons_file, '/skeleton');
trajectories_data = h5read(skeletons_file, '/trajectories_data');
%coord_x and coord_y are smoothed.

real_frame = trajectories_data.timestamp_raw(trajectories_data.frame_number+1); %will match the indexes of segworm. Add one because the python indexing.
real_time = trajectories_data.timestamp_time(trajectories_data.frame_number+1);

figure
%plot the first 1000 points of the mid skeleton
plot(squeeze(skeletons(1,25,1:1000)), squeeze(skeletons(2,25,1:1000)))

