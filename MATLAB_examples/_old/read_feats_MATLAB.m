filename = '/Volumes/behavgenom$/Pratheeban/Results/L1_early/15_07_07/15_07_07_C1_overnt_Ch1_07072015_160917_features.hdf5';
info = h5info(filename);

%% mean values of each features, it is the easier way to get the list of valid worm ids

feat_avg = h5read(filename, '/Features_means');
worm_ids = feat_avg.worm_index;

%% read motion data
feat_motion = h5read(filename, '/Features_motion');
%% plot midbody_speed over time for all the valid trajectories
figure, hold on
min_frame = min(feat_motion.frame_number);
max_frame = max(feat_motion.frame_number);

for ii = 1:numel(worm_ids)
    title( sprintf('worm %i', worm_id))
    worm_id = worm_ids(ii);
    good = feat_motion.worm_index==worm_id;
    frame = feat_motion.frame_number(good);
    speed = feat_motion.Midbody_Speed(good);
    subplot(4,4,ii)
    plot(frame, speed)
    xlim([min_frame, max_frame])
end
%% read event data (Backward Distance)

figure, hold on
for ii = 1:numel(worm_ids)
    worm_id = worm_ids(ii);
    Midbody_Dwelling = h5read(filename, sprintf('/Features_events/worm_%i/Midbody_Dwelling', worm_id));
    subplot(4,4,ii)
    plot(Midbody_Dwelling)
    title( sprintf('worm %i', worm_id))
end


