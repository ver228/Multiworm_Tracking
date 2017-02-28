function alignStageMotionSegwormFun(masked_image_file,skeletons_file)
    %% delete data from previous analysis if any
    fid = H5F.open(skeletons_file,'H5F_ACC_RDWR','H5P_DEFAULT');
    if H5L.exists(fid,'/stage_movement','H5P_DEFAULT')
        gid = H5G.open(fid, '/stage_movement');
        if H5L.exists(gid,'stage_vec','H5P_DEFAULT')
            H5L.delete(gid,'stage_vec','H5P_DEFAULT');
        end
        
        if H5L.exists(gid,'is_stage_move','H5P_DEFAULT')
            H5L.delete(gid,'is_stage_move','H5P_DEFAULT');
        end
        
        if H5L.exists(gid,'frame_diffs','H5P_DEFAULT')
            H5L.delete(gid,'frame_diffs','H5P_DEFAULT');
        end
        H5L.delete(gid,'/stage_movement','H5P_DEFAULT');
        
        
    end
    %create an empty new group we will uset his group to store the has_finished flag
    plist = 'H5P_DEFAULT';
    gid = H5G.create(fid,'/stage_movement',plist,plist,plist);
    H5G.close(gid);
    H5F.close(fid);
    
    %create a has_finished flag to record the progress of the function
    h5writeatt(skeletons_file, '/stage_movement', 'has_finished', uint8(0))
    
    
    %% read time stamps. I probably should put this data into the masked files dir
    video_timestamp_ind = h5read(skeletons_file, '/timestamp/raw');
    video_timestamp_ind = video_timestamp_ind + 1; %correct for python indexing
    
    if any(isnan(video_timestamp_ind))
        exit_flag = 80;
        warning('The timestamp is corrupt or do not exist.\n No stage correction processed. Exiting with has_finished flag %i.' , exit_flag)
        %turn on the has_finished flag and exit
        h5writeatt(skeletons_file, '/stage_movement', 'has_finished', uint8(exit_flag))
        return
    end
    
    video_timestamp_time = h5read(skeletons_file, '/timestamp/time');
    fps = 1/median(diff(video_timestamp_time));
    
    %% Open the information file and read the tracking delay time.
    % (help from segworm findStageMovement)
    % 2. The info file contains the tracking delay. This delay represents the
    % minimum time between stage movements and, conversely, the maximum time it
    % takes for a stage movement to complete. If the delay is too small, the
    % stage movements become chaotic. We load the value for the delay.
    
    xml_info = h5read(masked_image_file, '/xml_info');
    %this is not the cleaneast but matlab does not have a xml parser from
    %text string
    dd = strsplit(xml_info, '<delay>');
    dd = strsplit(dd{2}, '</delay>');
    delay_str = dd{1};
    delay_time = str2double(delay_str) / 1000;
    delay_frames = ceil(delay_time * fps);
    
    %% Read the scale conversions, we would need this when we want to convert the pixels into microns
    pixelPerMicronX = 1/h5readatt(masked_image_file, '/mask', 'pixels2microns_x');
    pixelPerMicronY = 1/h5readatt(masked_image_file, '/mask', 'pixels2microns_y');
    
    normScale = sqrt((pixelPerMicronX ^ 2 + pixelPerMicronX ^ 2) / 2);
    pixelPerMicronScale =  normScale * [sign(pixelPerMicronX) sign(pixelPerMicronY)];
    
    % Compute the rotation matrix.
    %rotation = 1;
    angle = atan(pixelPerMicronY / pixelPerMicronX);
    if angle > 0
        angle = pi / 4 - angle;
    else
        angle = pi / 4 + angle;
    end
    cosAngle = cos(angle);
    sinAngle = sin(angle);
    rotation_matrix = [cosAngle, -sinAngle; sinAngle, cosAngle];
    
    %% save appropiated attributes into the hdf5
    h5writeatt(skeletons_file, '/stage_movement', 'fps', fps)
    h5writeatt(skeletons_file, '/stage_movement', 'delay_frames', delay_frames)
    h5writeatt(skeletons_file , '/stage_movement',  'microns_per_pixel_scale',  pixelPerMicronScale)
    h5writeatt(skeletons_file , '/stage_movement',  'rotation_matrix',  rotation_matrix)
    
    %% calculate the variance of the difference between frames
    % Ev's code uses the full vectors without dropping frames
    % 1. video2Diff differentiates a video frame by frame and outputs the
    % differential variance. We load these frame differences.
    frame_diffs_d = getFrameDiffVar(masked_image_file)';
    
    %Save data
    h5create(skeletons_file, '/stage_movement/frame_diffs', size(frame_diffs_d), 'Datatype', 'double', ...
        'Chunksize', size(frame_diffs_d), 'Deflate', 5, 'Fletcher32', true, 'Shuffle', true)
    h5write(skeletons_file, '/stage_movement/frame_diffs', frame_diffs_d);
    
    %% Read the media times and locations from the log file.
    % (help from segworm findStageMovement)
    % 3. The log file contains the initial stage location at media time 0 as
    % well as the subsequent media times and locations per stage movement. Our
    % algorithm attempts to match the frame differences in the video (see step
    % 1) to the media times in this log file. Therefore, we load these media
    % times and stage locations.
    %from the .log.csv file
    stage_log = h5read(masked_image_file, '/stage_log');
    mediaTimes = stage_log.stage_time';
    locations = [stage_log.stage_x , stage_log.stage_y];
    
    %% The shift makes everything a bit more complicated. I have to remove the first frame, before resizing the array considering the dropping frames.
    
    if numel(video_timestamp_ind) > numel(frame_diffs_d) + 1
        %i can tolerate one frame (two with respect to the frame_diff)
        %extra at the end of the timestamp
        video_timestamp_ind = video_timestamp_ind(1:numel(frame_diffs_d)+1);
    end
    
    frame_diffs = nan(1, max(video_timestamp_ind)-1);
    dd = video_timestamp_ind - min(video_timestamp_ind);
    dd = dd(dd>0);
    
    if numel(frame_diffs_d) ~= numel(dd)
        exit_flag = 81;
        warning('Number of timestamps do not match the number read movie frames.\n No stage correction processed. Exiting with has_finished flag %i.', exit_flag)
        %turn on the has_finished flag and exit
        h5writeatt(skeletons_file, '/stage_movement', 'has_finished', uint8(exit_flag))
        return
    end
    frame_diffs(dd) = frame_diffs_d;
    
    %% try to run the aligment and return empty data if it fails 
    try
        clear is_stage_move movesI stage_locations
        [is_stage_move, movesI, stage_locations] = findStageMovement_ver2(frame_diffs, mediaTimes, locations, delay_frames, fps);
        exit_flag = 1;
    catch ME
        warning(ME.getReport)
        exit_flag = 82;
        warning('Returning all nan stage vector. Exiting with has_finished flag %i', exit_flag)
        h5writeatt(skeletons_file, '/stage_movement', 'has_finished', uint8(exit_flag))
        
        %remove the if we want to create an empty 
        is_stage_move = ones(numel(frame_diffs)+1, 1);
        stage_locations = [];
        movesI = [];
    end
    %%
    stage_vec = nan(numel(is_stage_move),2);
    if numel(movesI) == 2 && all(movesI==0)
        %there was no movements
        stage_vec(:,1) = stage_locations(1);
        stage_vec(:,2) = stage_locations(2);
        
    else
        %convert output into a vector that can be added to the skeletons file to obtain the real worm displacements
        
        for kk = 1:size(stage_locations,1)
            bot = max(1, movesI(kk,2)+1);
            top = min(numel(is_stage_move), movesI(kk+1,1)-1);
            stage_vec(bot:top, 1) = stage_locations(kk,1);
            stage_vec(bot:top, 2) = stage_locations(kk,2);
        end
    end
    
    %the nan values must match the spected video motions
    assert(all(isnan(stage_vec(:,1)) == is_stage_move))
    
    %% prepare vectors to save into the hdf5 file.
    %Go back to the original movie indexing. I do not want to include the missing frames at this point.
    is_stage_move_d = int8(is_stage_move(video_timestamp_ind))';
    
    
    stage_vec_d = stage_vec(video_timestamp_ind, :)';
    
    %% save stage vector
    
    h5create(skeletons_file, '/stage_movement/stage_vec', size(stage_vec_d), 'Datatype', 'double', ...
        'Chunksize', size(stage_vec_d), 'Deflate', 5, 'Fletcher32', true, 'Shuffle', true)
    h5write(skeletons_file, '/stage_movement/stage_vec', stage_vec_d);
    
    h5create(skeletons_file, '/stage_movement/is_stage_move', size(is_stage_move_d), 'Datatype', 'int8', ...
        'Chunksize', size(is_stage_move_d), 'Deflate', 5, 'Fletcher32', true, 'Shuffle', true)
    h5write(skeletons_file, '/stage_movement/is_stage_move', is_stage_move_d);
    
    
    h5writeatt(skeletons_file, '/stage_movement', 'has_finished', uint8(exit_flag))
    disp('Finished.')
end
