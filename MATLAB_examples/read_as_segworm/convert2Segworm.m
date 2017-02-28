function [features_segworm, conversions] = convert2Segworm(features)
%read an hdf5 features file produced by MWTracker
%features  - structure with all the individual worm tracks and their
%                       respective features in the MWTracker format (see readFeatureTable).
%features_segworm - structure with individual worm tracks features formated
%                   as the segworm worm struct. 

%NOTE - The conversions to segworm will not be one to one since the fields
% are based on the openworm definitions. This is not too dificult
% to correct by modifying the file conversion_table.csv. I want to be sure
% that this function would be useful before doing those modifications.

conversion_table = 'conversion_table.csv';
dat = getFileData(conversion_table);
conversions = struct();
for nn = 1:numel(dat.feat_name_table)
    feat_table = dat.feat_name_table{nn};
    feat_segworm = dat.feat_name_segworm{nn};
    conversions.(feat_table) = feat_segworm;
end

%% convert the structure of MWTracker to segworm.
%i create a new worm for each worm. Probably it is a bit wastefull in memory but it is safer
worm_names = fieldnames(features);
features_segworm = struct();

%fields that are just going to be copy. For the moment I do not have a good
%conversions to the segworm structure.
JUST_COPY_FIELDS =  {'worm_index', 'timestamp', 'motion_modes'};

for iw = 1:numel(worm_names)
    worm_name = worm_names{iw};
    old_worm = features.(worm_name);
    
    new_worm = struct();
    
    %add skeletons fields
    new_worm.posture.skeleton.x = old_worm.skeletons_x;
    new_worm.posture.skeleton.y = old_worm.skeletons_y;
    old_worm = rmfield(old_worm, {'skeletons_x'; 'skeletons_y'});
    
    worm_fields = fieldnames(old_worm);
    for fn = 1:numel(worm_fields)
        old_field = worm_fields{fn};
        if any(strcmp(old_field, JUST_COPY_FIELDS))
            segworm_field_str = ['extra.', old_field];
        else
            segworm_field_str = conversions.(old_field);
        end
        
        segworm_fields = strsplit(segworm_field_str, '.');
        data = old_worm.(old_field);
        new_worm = addField(new_worm, segworm_fields, data);
        
        old_worm = rmfield(old_worm, old_field); %just to check that all the fields were really removed
    end
    assert(isempty(fieldnames(old_worm)))
    
    
    new_postures = new_worm.posture;
    eigenProjection = zeros(6, length(new_worm.posture.eigen_projection0));
    for ei = 1:6
        eigen_str = sprintf('eigen_projection%i', ei-1);
        eigenProjection(ei, :) = new_postures.(eigen_str);
        new_postures = rmfield(new_postures, eigen_str);
    end
    new_postures.eigenProjection = eigenProjection;
    new_worm.posture = new_postures;

    %add to the main worm
    features_segworm.(worm_name) = new_worm;
end
end

function root = addField(root, field_names, data)
        
    if length(field_names) == 1
        field_names = field_names{1};
    end
    if ~iscell(field_names)
        %null condition return root
        root.(field_names) = data;
    else
        current_field = field_names{1};
        if ~isfield(root, current_field)
            root.(current_field) = struct();
        end
        root.(current_field) = addField(root.(current_field), field_names(2:end), data);
    end
end

