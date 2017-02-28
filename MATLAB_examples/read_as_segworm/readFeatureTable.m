function [features, features_means, experiment_info] = readFeatureTable(features_file)
%features structure - with all the individual worm tracks and their
%                       respective features. Each field corresponds to the
%                       worm variable produced by segworm.
%features means - structures with the means of all the features for each worm.
%                 Use the field worm_index to find the corresponding worm.
%experiment info - for the moment it is only a text string with json format
%                   I should convert it into a more useful format.

% try to read expermient_info if it doesn't exist return an empty string
try
    experiment_info = h5read(features_file, '/experiment_info');
catch err
    experiment_info = '';
end
%/features_means was deprecated
features_means = h5read(features_file, '/features_summary/means');

%% now let's read the features data
features = struct();

%% add timeseries features and skeletons
features_timeseries = h5read(features_file, '/features_timeseries');
skeletons = h5read(features_file, '/coordinates/skeletons');

u_worms = unique(features_timeseries.worm_index);

timeseries_fields = fieldnames(features_timeseries);

for worm_ind = u_worms'
    worm_name = sprintf('worm_%i', worm_ind);
    good_ind = features_timeseries.worm_index == worm_ind;
    for fn = 1:numel(timeseries_fields)
        field_name = timeseries_fields{fn};
        features.(worm_name).(field_name) = features_timeseries.(field_name)(good_ind);
    
        if strcmp(field_name, 'timestamp')
            field_data = features.(worm_name).(field_name);
            field_data = double(field_data); 
            field_data(field_data<0) = nan;
            features.(worm_name).(field_name) = field_data;
        end
        
    end
    
    features.(worm_name).skeletons_x = squeeze(skeletons(1, :, good_ind));
    features.(worm_name).skeletons_y = squeeze(skeletons(2, :, good_ind));
end

%% read events features
events_groups = h5info(features_file, '/features_events');
for ig = 1:numel(events_groups.Groups)
    path = events_groups.Groups(ig).Name;
    path_parts = strsplit(path, '/');
    worm_name = path_parts{end};
    
    for fn = 1:numel(events_groups.Groups(ig).Datasets);
        field_name = events_groups.Groups(ig).Datasets(fn).Name;
        field_data = h5read(features_file, [path, '/' field_name]);
        
        
        
        
        features.(worm_name).(field_name) = field_data;
        
    end
        
end