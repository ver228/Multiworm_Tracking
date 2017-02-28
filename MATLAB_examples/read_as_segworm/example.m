features_file = '/Volumes/behavgenom_archive$/Avelino/DEMO/Results/double_pick_200117/N2_N10_F1-3_Set2_Pos5_Ch5_20012017_153643_features.hdf5';
%% read data from the features hdf5 file.
[features, features_means, experiment_info] = readFeatureTable(features_file);
[features, conversions] = convert2Segworm(features);

delta_t = 10;
good = ~isnan(features.worm_1.posture.skeleton.x(1,:));
xx = features.worm_1.posture.skeleton.x(:, good);
yy = features.worm_1.posture.skeleton.y(:, good);

figure()
plot(xx, yy)

%%
figure()
xx = features.worm_1.extra.timestamp;
yy = features.worm_1.locomotion.velocity.midbody.speed;
plot(xx, yy)
xlabel('time (s)')
ylabel('velocity (um/s)')




