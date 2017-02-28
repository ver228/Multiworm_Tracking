function  img_abs_diff = getFrameDiffVar(masked_image_file)
%% mask information
[~, base_name, ~]= fileparts(masked_image_file);
mask_info = h5info(masked_image_file, '/mask');


% size of each frame
frame_size = mask_info.Dataspace.Size(1:2);
frame_total = mask_info.Dataspace.Size(3);

%% Calculate the variance between consecutive images

img_abs_diff = zeros(frame_total-1,1);

frame_prev =  h5read(masked_image_file, '/mask', [1,1,1], [frame_size(1),frame_size(2), 1]);

fprintf('%s Calculating variance of the difference between frames %2.2f%%\n', base_name, 0)
for ii = 2:frame_total
    if mod(ii, 2000) == 0
        %progress
        fprintf('%s Calculating variance of the difference between frames %2.2f%%\n', base_name, (ii+1)/frame_total*100)
    end
    
    frame_current = h5read(masked_image_file, '/mask', [1,1,ii], [frame_size(1),frame_size(2), 1]);
    
    % calculate the absolute difference between frames
    %img_abs_diff(ii-timeDiff) = sum(sum(abs(double(frame_bef) - double(frame_aft))));
    
    
    img_abs_diff(ii-1) = imMaskDiffVar(frame_prev,frame_current);
    %good = (frame_prev>0) & (frame_current>0);
    %A = var(double(frame_prev(good))-double(frame_current(good)), 1);
    %assert(abs(A - img_abs_diff(ii-1)) < 1e-2);
    
    %buffer to the previous frame
    frame_prev = frame_current;
end
fprintf('%s Calculating variance of the difference between frames %2.2f%%\n', base_name, 100)