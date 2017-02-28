function [frames, movesI, locations] = ...
    findStageMovement_ver2(frameDiffs, mediaTimes, locations, delayFrames, fps)

%MODIFIED FROM SEGWORM AEJ. This help is outdated, I'll modified later. AEJ

%FINDSTAGEMOVEMENT Find stage movements in a worm experiment.
%
% The algorithm is as follows:
%
% 4. If there are no stage movements, we're done.
%
% 5. The log file sometimes contains more than one entry at 0 media time.
% These represent stage movements that may have completed before the video
% begins. Therefore, we don't use them but, instead, store them in case we
% find their stage movement in the video frame differences.
%
% 6. The frame differences need to be aligned to the video frames.
% Therefore, we copy the first one and shift the rest over so that the
% frame differences are one-to-one with the video frames. Note that video
% indexing starts at 0 while Matlab indexing begins at 1. Also note, due
% to differentiation, large frame differences that occur at the beginning
% of a stage movement now represent the first frame of movement. Large
% frame differences that occur at the end of a stage movement now represent
% the first non-movement frame.
%
% 7. Compute the global Otsu threshold for the frame-differences to
% distinguish stage-movement peaks. Then compute a global non-movement
% threshold by taking all values less than the Otsu, and computing 3
% standard deviations from the median (approximately 99% of the small
% values). Please note, stage movements ramp up/down to
% accelerate/decelerate to/from the target speed. Therefore, the values
% below the Otsu threshold are contaminated with stage movement
% acceleration and decelaration. Fortunately, non-movement frames account
% for more than 50% of the frame differences. Therefore, to avoid the stage
% movement contamination, we use the median of the small values rather than
% their mean when computing the global non-movement (small) threshold. If
% this small threshold is greater than the Otsu, we've made a poor choice
% and ignore both thresholds. Otherwise, these 2 global thresholds serve as
% a backup to the local ones when distinguishing stage movements.
%
% 8. Ocasionally, computing the global Otsu threshold fails. This occurs
% when a long video has few stage movements. In this case, stage movements
% appear to be rare outliers and the Otsu method minimizes in-group
% variance by splitting the non-stage movement modality into two groups
% (most likely periods of worm activity and inactivity). Under these
% circumstances we attempt to use a global threshold at half the maximum
% frame-difference variance. As detailed above, we test this threshold to
% see whether it is sufficiently larger than 99% of the smaller movements.
%
% 9. When searching for stage movements, we use the same algorithm as the
% one above(see step 7), over a smaller well-defined, search window, to
% determine the local Otsu threshold. The local small threshold is computed
% slightly differently (we use the mean instead of the median -- see step
% 12 for an explanation). If the local Otsu threshold fails (it's smaller
% than 99% of the values below it and smaller than the global Otsu), we
% attempt to use the global one to see if it pulls out a peak.
%
% 10. A stage movement peak is defined as the largest value that exceeds
% the minimum of the global and local Otsu thresholds. To avoid a situation
% in which 2 stage movements occur within the same search window, we scan
% the window for the first value exceeding the Otsu threshold and, if any
% subsequent values drop below the minimum of global and local small
% thresholds, we cut off the remainder of the window and ignore it.
%
% 11. Once a stage-movement peak is identified, we search for a temporary
% back and front end to the movement. The stage movement must complete
% within one delay time window (see step 2). Therefore, we search for the
% minimum values, within one delay time window, before and after the peak.
% The locations of these minimum values are the temporary back and front
% ends for the stage movement. If the either value is below the small
% threshold, we may have overshot the movement and, therefore, attempt to
% find a location closer to the peak. Similarly, if either value is greater
% than the maximum of the global and local small thresholds and the
% remaining values till the end of the window are NaNs or, if either value
% is greater than the Otsu threshold, we may have undershot the movement
% and, therefore, attempt to find a location further from the peak.
%
% 12. Using one stage movement's temporary front end and the subsequent
% movement's temporary back end, we compute the small threshold. This
% interval is assumed to have no stage motion and, therefore, represents
% frame-difference variance from a non-movement interval. The local small
% threshold is defined as 3 deviations from the mean of this non-movement
% interval (99% confidence). With this small threshold, we start at the
% first peak and search forward for its real front end. Similarly, we start
% at the subsequent peak and search backward for its real back end.
%
% 13. Conservatively, the beginning and end of the video are treated as the
% end and begining of stage movements, respectively. We search for a
% temporary front end and a temporary back end, respectively, using the
% global small and Otsu thresholds.
%
% 14. After the final, logged stage motion is found in the frame
% differences, we look to see if there are any subsequent, extra peaks.
% An Otsu threshold is computed, as detailed earlier, using the interval
% spanning from the final stage movement's temporary front end till the
% final frame difference. If this threshold is unsuitable, we use the
% global Otsu threshold. If we find any extra peaks, the first peak's back
% end is located and its frame as well as the remainder of the frame
% differences (including any other extra peaks) are marked as a single
% large stage movement that extends till the end of the video. This is
% necessary since Worm Tracker users can terminate logging prior to
% terminating the video (e.g., this may occur automatically if the worm is
% lost).
%
% 15. To find a stage movement, we compute its offset media time. The first
% stage movement is offset by the delay time (see step 2). Subsequent media
% times are offset by the difference between the previous media time and
% its stage-movement peak. Therefore, each stage movement provides the
% offset for the next one. The longer the wait till the next stage
% movement, the less accurate this offset becomes. Therefore, we search for
% each stage movement using a window that begins at the last stage
% movement's temporary front end and ends at the offset media time plus
% this distance (a window with its center at the offset media time). If the
% window is too small (the offset media time is too close to the temporary
% front end of the previous stage movement), we extend its end to be the
% offset media time plus the delay time.
%
% 16. If a stage movement peak is absent, we attempt to shift the media
% times backward or forward, relative to the stage movement peaks,
% depending on whether the current peak is closer to the next or previous
% media time, respectively. When shifting the media times backward, we
% assume the first stage movement occurred prior to video recording and,
% therefore, throw away its media time and location. When shifting the
% media times forward, we look for a spare 0 media time and location (see
% step 5). If there are no spares, we swallow up all the frames prior to
% the end of the first stage movement and label them as an unusable
% movement that began prior to recording and bled into the beginning of the
% video.
% 
% 17. If we find a stage-movement peak closer to the previous offset media
% time than its own supposed offset media time, we assume we have a
% misalignment and attempt to shift the media times forward relative to the
% stage movement peaks. There are some restrictions to this check since
% small-scale, frame jitter can misrepresent the reported media time.
%
% 18. The final logged stage motion may occur after the video ends and, as
% a result, may have no representation in the frame-difference variance.
% Therefore, for the last stage movement, we check our threshold (see step
% 10) to ensure that it separates 99% of the smaller values and, thereby,
% picks up stage movement rather than splitting the non-movement modality.
%
%
%
%   FUNCTION [FRAMES INDICES LOCATIONS] = ...
%       FINDSTAGEMOVEMENT(INFOFILE, LOGFILE, DIFFFILE, VERBOSE)
%
%   FUNCTION [FRAMES INDICES LOCATIONS] = ...
%       FINDSTAGEMOVEMENT(INFOFILE, LOGFILE, DIFFFILE, VERBOSE, GUIHANDLE)
%
%   Input:
%       infoFile  - the XML file with the experiment information
%       logFile   - the CSV file with the stage locations
%       diffFile  - the MAT file with the video differentiation
%       verbose   - verbose mode 1 shows the results in a figure
%                   verbose mode 2 labels the stage movements in the figure
%       guiHandle - the GUI handle to use when showing the results;
%                   if empty, the results are shown in a new figure
%
%   Output:
%       frames    - a vector of frame status
%                   true  = the frame contains stage movement
%                   false = the frame does NOT contain stage movement
%                   NaN   = the original video frame was dropped
%                   Note: video frames are indexed from 0, Matlab indexes
%                   from 1, please adjust your calculations accordingly
%       movesI    - a 2-D matrix with, respectively, the start and end
%                   frame indices of stage movements
%       locations - the location of the stage after each stage movement
%
% See also VIDEO2DIFF
%
%
% © Medical Research Council 2012
% You will not remove any copyright or other notices from the Software; 
% you must reproduce all copyright notices and other proprietary 
% notices on any copies of the Software.
verbose = false;

% Check the frame rate.
minFPS = .1;
maxFPS = 100;
if fps < minFPS || fps > maxFPS
    warning('video2Diff:WeirdFPS', [diffFile ' was recorded at ' ...
        num2str(fps) ' frames/second. An unusual frame rate']);
end


% The media time must be initialized.
if isempty(mediaTimes) || mediaTimes(1) ~= 0
    error('findStageMovement:NoInitialMediaTime', ...
        'The first media time must be 0');
end

% If there's more than one initial media time, use the latest one.
if length(mediaTimes) > 1
    i = 2;
    while i < length(mediaTimes) && mediaTimes(i) == 0
        i = i + 1;
    end
    
    % Save the spare 0 media time location in case the corresponding
    % stage-movement, frame difference occured after the video started.
    spareZeroTimeLocation = [];
    if i > 2
        spareZeroTimeLocation = locations(i - 2,:);
    end
    
    % Dump the extraneous 0 media times and locations.
    mediaTimes(1:(i - 2)) = [];
    locations(1:(i - 2),:) = [];
end

% No frame difference means the frame was dropped.
frameDiffs(frameDiffs == 0) = NaN;

% Normalize the frame differences and shift them over one to align them
% with the video frames.
frameDiffs(2:(length(frameDiffs) + 1)) = frameDiffs / max(frameDiffs);
frameDiffs(1) = frameDiffs(2);

% Compute the global Otsu and small frame-difference thresholds.
% Note 1: we use the Otsu to locate frame-difference peaks corresponding to
% stage movement.
% Note 2: we use the small threshold to locate the boundaries between
% frame differences corresponding to stage movement and frame differences
% corresponding to a non-movement interval.
gOtsuThr = graythresh(frameDiffs);
gSmallDiffs = frameDiffs(frameDiffs < gOtsuThr);
gSmallThr = median(gSmallDiffs) + 3 * std(gSmallDiffs);

% The log file doesn't contain any stage movements.
if length(mediaTimes) < 2
    warning('findStageMovements:NoStageMovements', 'The stage never moves');
    
    % Are there any large frame-difference peaks?
    if gOtsuThr >= gSmallThr
        [~, indices] = maxPeaksDistHeight(frameDiffs, delayFrames, gOtsuThr);
        warning('findStageMovements:UnexpectedPeaks', ['There are ' ...
            num2str(length(indices)) ' large frame-difference peaks ' ...
            'even though the stage never moves']);
    end
    
    % Finish.
    frames = false(length(frameDiffs), 1);
    movesI = [0 0];
    return;
end

% Does the Otsu threshold separate the 99% of the small frame differences
% from the large ones?
if isempty(gSmallDiffs) || gOtsuThr < gSmallThr
    warning('findStageMovements:NoGlobalOtsuThreshold', ...
        ['Using the Otsu method, as a whole, the frame differences ' ...
        'don''t appear to contain any distinguishably large peaks ' ...
        '(corresponding to stage movements). Trying half of the ' ...
        'maximum frame difference instead.']);
    
    % Try half the maximum frame difference as a threshold to distinguish
    % large peaks.
    gOtsuThr = .5;
    gSmallDiffs = frameDiffs(frameDiffs < gOtsuThr);
    gSmallThr = median(gSmallDiffs) + 3 * std(gSmallDiffs);
    
    % Does a threshold at half the maximum frame difference separate the
    % 99% of the small frame differences from the large ones?
    if isempty(gSmallDiffs) || gOtsuThr < gSmallThr
        warning('findStageMovements:NoGlobalThresholds', ...
            ['Cannot find a global threshold to distinguish the large ' ...
            'frame-difference peaks.']);
        gOtsuThr = NaN;
        gSmallThr = NaN;
    end
end

% Pre-allocate memory.
frames = false(length(frameDiffs), 1); % stage movement status for frames
movesI(1:length(mediaTimes), 1:2) = NaN; % stage movement indices
movesI(1,:) = 0;
if verbose
    peaksI(1:length(mediaTimes)) = NaN; % stage movement frame peaks
    endPeaksI = []; % peaks after the last stage movement
    otsuThrs = zeros(1, length(mediaTimes) + 1); % Otsu thresholds
    smallThrs = zeros(1, length(mediaTimes) - 1); % small thresholds
    timeOffs = [mediaTimes, length(frameDiffs) / fps]; % offset media times
    
    % Have we matched all the media times to frame-difference stage
    % movements?
    isMediaTimesMatched = true;
end

% Are there enough frames?
if sum(~isnan(frameDiffs)) < 2
    error('findStageMovement:IsufficientFrames', ...
        'The video must have at least 2, non-dropped frames');
end

% Compute the search boundary for the first frame-difference peak.
maxMoveFrames = delayFrames + 1; % maximum frames a movement takes
maxMoveTime = maxMoveFrames / fps; % maximum time a movement takes
timeOff = maxMoveTime; % the current media time offset
peakI = 1; % the current stage movement peak's index
prevPeakI = 1; % the previous stage-movement peak's index
prevPeakEndI = 1; % the previous stage-movement peak's end index
startI = 1; % the start index for our search
endI = 2 * maxMoveFrames; % the end index for our search
if endI > length(frameDiffs)
    endI = length(frameDiffs);
end
searchDiffs = frameDiffs(startI:endI);

% Is the Otsu threshold large enough?
otsuThr = graythresh(searchDiffs);
isOtsu = otsuThr > gOtsuThr; % false if no global Otsu
if ~isOtsu
    
    % Does the Otsu threshold separate the 99% of the small frame
    % differences from the large ones? And, if there is a global small
    % threshold, is the Otsu threshold larger?
    smallDiffs = searchDiffs(searchDiffs < otsuThr);
    isOtsu = ~isempty(smallDiffs) && sum(~isnan(smallDiffs)) > 0 && ...
        (isnan(gSmallThr) || otsuThr > gSmallThr) && ...
        otsuThr >= median(smallDiffs) + 3 * std(smallDiffs);
    
    % Does the global Otsu threshold pull out any peaks?
    if ~isOtsu
        if ~isnan(gOtsuThr) && sum(searchDiffs > gOtsuThr) > 1
            otsuThr = gOtsuThr;
            isOtsu = true;
        end
    end
end

% Are there any distinguishably large, frame-difference peaks?
if (verbose)
    peaksI(1) = peakI;
    otsuThrs(1) = gOtsuThr;
end
if isOtsu
    
    % Do the frame differences begin with a stage movement?
    indices = find(searchDiffs > otsuThr);
    firstPeakI = indices(1);
    if firstPeakI <= maxMoveFrames
        
        % Find the largest frame-difference peak.
        [~, peakI] = max(frameDiffs(1:maxMoveFrames));
        prevPeakI = peakI;
        
        % Compute the media time offset.
        timeOff = peakI / fps;
        if verbose
            peaksI(1) = peakI;
            otsuThrs(1) = otsuThr;
            timeOffs(1) = timeOff;
        end
    end
    
    % Is there a still interval before the first stage movement?
    if peakI > 1
        i = peakI - 1;
        while i > 1
            if frameDiffs(i) < gSmallThr && frameDiffs(i - 1) < gSmallThr
                peakI = 1;
                break;
            end
            i = i - 1;
        end
    end
end

% We reached the end.
endI = peakI + maxMoveFrames;
if endI >= length(frameDiffs)
    prevPeakEndI = length(frameDiffs);
    
% Find a temporary front end for a potential initial stage movement.
else
    searchDiffs = frameDiffs(peakI:endI);
    
    % Does the search window contain multiple stage movements?
    if ~isnan(gOtsuThr) && ~isnan(gSmallThr)
        foundMove = false;
        for i = 1:length(searchDiffs)
            
            % We found a still interval.
            if ~foundMove && searchDiffs(i) < gSmallThr
                foundMove = true;
                
            % We found the end of the still interval, cut off the rest.
            elseif foundMove && searchDiffs(i) > gSmallThr
                searchDiffs = searchDiffs(1:(i - 1));
                break;
            end
        end
    end
    
    % Find a temporary front end for a potential initial stage movement.
    [minDiff i] = min(searchDiffs);
    peakFrontEndI = peakI + i - 1;
    
    % If the temporary front end's frame difference is small, try to push
    % the front end backwards (closer to the stage movement).
    if minDiff <= gSmallThr
        i = peakI;
        while i < peakFrontEndI
            if frameDiffs(i) <= gSmallThr
                peakFrontEndI = i;
                break;
            end
            i = i + 1;
        end
    
    % If the temporary front end's frame difference is large, try to
    % push the front end forwards (further from the stage movement).
    elseif minDiff >= gOtsuThr || (minDiff > gSmallThr && ...
            peakFrontEndI < endI && ...
            all(isnan(frameDiffs((peakFrontEndI + 1):endI))))
        peakFrontEndI = endI;
    end
    
    % Advance.
    prevPeakEndI = peakFrontEndI;
end

% Match the media time-stage movements to the frame-difference peaks.
mediaTimeOff = 0; % the offset media time
prevOtsuThr = gOtsuThr; % the previous small threshold
prevSmallThr = gSmallThr; % the previous small threshold
isShifted = false; % have we shifted the data to try another alignment?
i = 1;
while i < length(mediaTimes)
    
    % Advance.
    i = i + 1;
    
    % Compute the offset media time.
    prevMediaTimeOff = mediaTimeOff;
    mediaTimeOff = mediaTimes(i) + timeOff;
    if verbose
        timeOffs(i) = mediaTimeOff;
    end
    
    % Compute the search boundary for matching frame-difference peaks.
    mediaTimeOffI = round(mediaTimeOff * fps);
    startI = prevPeakEndI;
    endI = max(startI + 2 * abs(mediaTimeOffI - startI), ...
        max(startI, mediaTimeOffI) + maxMoveFrames);
    if endI > length(frameDiffs)
        endI = length(frameDiffs);
    end
    searchDiffs = frameDiffs(startI:endI);
    
    % Is the Otsu threshold large enough?
    otsuThr = graythresh(searchDiffs);
    isOtsu = otsuThr > prevSmallThr || otsuThr > gOtsuThr;
    if ~isOtsu
        
        % Does the Otsu threshold separate the 99% of the small frame
        % differences from the large ones?
        if isnan(prevSmallThr) || otsuThr > prevSmallThr || ...
                otsuThr > gSmallThr
            smallDiffs = searchDiffs(searchDiffs < otsuThr);
            isOtsu = ~isempty(smallDiffs) && ...
                sum(~isnan(smallDiffs)) > 0 && ...
                otsuThr >= median(smallDiffs) + 3 * std(smallDiffs);
        end
        
        % Try the global Otsu threshold or, if there is none, attempt to
        % use half the search window's maximum frame difference.
        if ~isOtsu
            
            % Try using half the search window's maximum frame difference.
            if isnan(gOtsuThr)
                otsuThr = max(searchDiffs) / 2;
                
                % Does the half-maximum threshold separate the 99% of the
                % small frame differences from the large ones?
                smallDiffs = searchDiffs(searchDiffs < otsuThr);
                isOtsu = ~isempty(smallDiffs) && ...
                    sum(~isnan(smallDiffs)) > 0 && ...
                    otsuThr >= median(smallDiffs) + 3 * std(smallDiffs);
                
            % Does the global Otsu threshold pull out any peaks?
            elseif sum(searchDiffs > gOtsuThr) > 0
                otsuThr = gOtsuThr;
                isOtsu = true;
                
            % Does the global Otsu threshold pull out any peaks?
            elseif sum(searchDiffs > prevOtsuThr) > 0
                otsuThr = prevOtsuThr;
                isOtsu = true;
            end
        end
    end
    if (verbose)
        otsuThrs(i) = otsuThr;
    end
    
    % If we're at the end, make sure we're using an appropriate threshold.
    if i == length(mediaTimes)
        
        % Does the threshold separate the 99% of the small frame
        % differences from the large ones?
        smallDiffs = searchDiffs(searchDiffs < otsuThr);
        isOtsu = ~isempty(smallDiffs) && sum(~isnan(smallDiffs)) > 0 && ...
            otsuThr >= median(smallDiffs) + 3 * std(smallDiffs);
    end
    
    % Match the media time stage movement to a peak.
    indices = [];
    if isOtsu
        
        % Compute and set the global thresholds.
        if isnan(gOtsuThr)
            
            % Use a small threshold at 99% of the small frame differences.
            smallDiffs = searchDiffs(searchDiffs < otsuThr);
            smallThr = median(smallDiffs) + 3 * std(smallDiffs);
            
            % Set the global thresholds.
            if otsuThr >= smallThr
                gOtsuThr = otsuThr;
                gSmallThr = smallThr;
                
                % Set the previous small threshold.
                if isnan(prevOtsuThr)
                    prevOtsuThr = otsuThr;
                    prevSmallThr = smallThr;
                end
                
            % Use the previous small threshold.
            elseif ~isnan(prevSmallThr)
                smallThr = prevSmallThr;
            end
            
        % Compute the local thresholds.
        else
            otsuThr = min(otsuThr, gOtsuThr);
            smallThr = max(prevSmallThr, gSmallThr);
            if smallThr > otsuThr
                smallThr = min(prevSmallThr, gSmallThr);
            end
        end
        
        % Does the search window contain multiple stage movements?
        foundMove = false;
        for j = 1:length(searchDiffs)
            
            % We found a stage movement.
            if ~foundMove && searchDiffs(j) > otsuThr
                foundMove = true;
                
            % We found the end of the stage movement, cut off the rest.
            elseif foundMove && searchDiffs(j) < smallThr
                searchDiffs = searchDiffs(1:(j - 1));
                break;
            end
        end
        
        % Find at least one distinguishably large peak.
        [~, indices] = ...
            maxPeaksDistHeight(searchDiffs, maxMoveFrames, otsuThr);
    end
    
    % We can't find any distinguishably large peaks.
    peakI = [];
    if isempty(indices)
        
        % Does the last stage movement occur after the video ends?
        if i == length(mediaTimes) && endI >= length(frameDiffs)
            
            % Does the last offset media time occur before the video ends?
            if mediaTimeOff < (length(frameDiffs) - 1) / fps
                warning('findStageMovement:LastPeak', ...
                    ['The search window for the last stage movement (' ...
                    num2str(i) ') at media time ' ...
                    num2str(mediaTimes(i), '%.3f') ...
                    ' seconds (frame ' ...
                    num2str(round(mediaTimes(i) * fps)) ...
                    ') offset to ' num2str(mediaTimeOff, '%.3f') ...
                    ' seconds (frame ' num2str(round(mediaTimeOff * fps)) ...
                    '), spanning from ' ...
                    num2str((startI - 1) / fps, '%.3f') ...
                    ' seconds (frame ' num2str(startI - 1) ...
                    ') to the last frame ' ...
                    num2str((endI - 1) / fps, '%.3f') ' seconds (frame ' ...
                    num2str(endI - 1) '), doesn''t have any'...
                    ' distinguishably large peaks. The peak probably' ...
                    ' occured after the video ended and, therefore,' ...
                    ' the last stage movement will be ignored.']);
            end
            
            % Ignore the last stage movement.
            mediaTimes(end) = [];
            locations(end,:) = [];
            movesI(end,:) = [];
            if verbose
                peaksI(end) = [];
                otsuThrs(end) = [];
                smallThrs(end) = [];
                timeOffs(end) = [];
            end
            break;
        end
        
        % Report the warning.
        warning('findStageMovement:NoPeaks', ...
            ['The search window for stage movement ' num2str(i) ...
            ' at media time ' num2str(mediaTimes(i), '%.3f') ...
            ' seconds (frame ' num2str(round(mediaTimes(i) * fps)) ...
            ') offset to ' num2str(mediaTimeOff, '%.3f') ...
            ' seconds (frame ' num2str(round(mediaTimeOff * fps)) ...
            '), spanning from ' num2str((startI - 1) / fps, '%.3f') ...
            ' seconds (frame ' num2str(startI - 1) ') to ' ...
            num2str((endI - 1) / fps, '%.3f') ' seconds (frame ' ...
            num2str(endI - 1) '), doesn''t have any distinguishably' ...
            ' large peaks']);
        
    % Use the first peak.
    else
        peakI = indices(1) + startI - 1;
        if verbose
            peaksI(i) = peakI;
        end
        
        % Is the current offset media time further from the frame-
        % difference stage movement than the previous offset media time?
        peakTime = (peakI - 1) / fps;
        timeDiff = mediaTimeOff - peakTime;
        prevTimeDiff = prevMediaTimeOff - peakTime;
        if i > 2 && (abs(prevTimeDiff) > maxMoveTime || ...
                abs(timeDiff) > maxMoveTime) && ...
                mediaTimeOff > prevMediaTimeOff && ...
                abs(timeDiff / prevTimeDiff) > 2
            warning('findStageMovement:FarPeak', ...
                ['Stage movement ' num2str(i) ' (at media time ' ...
                num2str(mediaTimes(i), '%.3f') ' seconds) offset to ' ...
                num2str(mediaTimeOff, '%.3f') ...
                ' seconds, has its frame-difference peak at ' ...
                num2str(peakTime, '%.3f') ' seconds (frame ' ...
                num2str(peakI - 1) '), an error of ' ...
                num2str(timeDiff, '%.3f') ' seconds.' ...
                ' The previous media time, offset to ' ...
                num2str(prevMediaTimeOff, '%.3f') ' seconds, is closer' ...
                ' with an error of only ' num2str(prevTimeDiff, '%.3f') ...
                ' seconds (less than half the current media time''s' ...
                ' error). Therefore, we probably have either a false' ...
                ' peak, a shifted misalignment, or an abnormally long delay']);
            
            % Ignore this wrong peak.
            peakI = [];
        end
    end
    
    % Can we realign (shift) the stage movements and media times?
    if isempty(peakI)
        lastMoveTime = movesI(i - 1,1) / fps;
        isShiftable = true;
        if isShifted
            isShiftable = false;
            
        % Shift the media times forward.
        elseif i > 2 && abs(mediaTimes(i - 2) - lastMoveTime) < ...
                abs(mediaTimes(i) - lastMoveTime)
            
            % Would a time shift align the media times with the
            % frame-difference stage movements?
            for j = 2:(i - 2)
                
                % Compute the error from the predicted time.
                offset =  movesI(j,1) / fps - mediaTimes(j - 1);
                predictedTime = mediaTimes(j) + offset;
                moveTime =  movesI(j + 1,1) / fps;
                timeDiff = abs(predictedTime - moveTime);
                
                % Compute the interval between the media times.
                mediaDiff = mediaTimes(j) - mediaTimes(j - 1);
                
                % Is the error in the predicted time greater than
                % the interval between media times?
                if timeDiff > mediaDiff
                    isShiftable = false;
                    break;
                end
            end
            
            % Time cannot be shifted due to misalignment between the media
            % times and frame-difference stage movements.
            if ~isShiftable
                warning('findStageMovement:TimeShiftAlignment', ...
                    ['Time cannot be shifted forward because the' ...
                    ' frame-difference stage movement at ' ...
                    num2str(moveTime, '%.3f') ' seconds would have a' ...
                    ' predicted time of ' num2str(predictedTime, '%.3f') ...
                    ' seconds (an error of ' num2str(timeDiff, '%.3f') ...
                    ' seconds) whereas the interval between its media' ...
                    ' time and the previous media time is only ' ...
                    num2str(mediaDiff, '%.3f') ' seconds and,' ...
                    ' therefore, smaller than the error from shifting']);
                
            % Shift everything forward using the spare 0 media time location.
            elseif ~isempty(spareZeroTimeLocation)
                mediaTimes = [0 mediaTimes];
                locations = [spareZeroTimeLocation; locations];
                movesI(end + 1,:) = [0 0];
                timeOff = prevPeakI / fps - mediaTimes(i - 1);
                if verbose
                    peaksI = [1 peaksI];
                    otsuThrs = [gOtsuThr otsuThrs];
                    smallThrs = [gSmallThr smallThrs];
                    timeOffs(1:(end + 1)) = [0 timeOffs(1:end)];
                    timeDiffs =  movesI(2:(i - 2),1)' / fps - ...
                        mediaTimes(2:(i - 2));
                    timeOffs(3:(i - 1)) = mediaTimes(3:(i - 1)) + timeDiffs;
                end
                
                % Redo the match.
                i = i - 1;
                
                % Warn about the time shift.
                warning('findStageMovement:TimeShiftForward', ...
                    ['Shifting the media times forward relative to the ' ...
                    'frame-difference stage movements (using a spare ' ...
                    'location at media time 0:0:0.000) in an attempt ' ...
                    'to realign them']);
                
            % Shift everything forward by assuming a missing 0 media time
            % location and swallowing earlier frames into the the first
            % stage movement.
            else
                frames(1:movesI(2,1)) = true;
                movesI(1:(i - 2),:) = movesI(2:(i - 1),:);
                movesI(1,1) = 0;
                timeOff = prevPeakI / fps - mediaTimes(i - 2);
                if verbose
                    peaksI(1:(i - 2)) = peaksI(2:(i - 1));
                    otsuThrs(1:(i - 2)) = otsuThrs(2:(i - 1));
                    smallThrs(1:(i - 2)) = smallThrs(2:(i - 1));
                    timeDiffs =  movesI(1:(i - 3),1)' / fps - ...
                        mediaTimes(1:(i - 3));
                    timeOffs(2:(i - 2)) = mediaTimes(2:(i - 2)) + timeDiffs;
                end
                
                % Redo the match.
                i = i - 2;
                
                % Warn about the time shift.
                warning('findStageMovement:TimeShiftForward', ...
                    ['Shifting the media times forward relative to the ' ...
                    'frame-difference stage movements (by swallowing ' ...
                    'earlier frames into the first stage movement) in ' ...
                    'an attempt to realign them']);
            end
            
        % Shift the media times backward.
        else
            
            % Would a time shift align the media times with the
            % frame-difference stage movements?
            for j = 3:(i - 1)
                
                % Compute the error from the predicted time.
                offset =  movesI(j - 1,1) / fps - mediaTimes(j);
                predictedTime = mediaTimes(j + 1) + offset;
                moveTime =  movesI(j,1) / fps;
                timeDiff = abs(predictedTime - moveTime);
                
                % Compute the interval between the media times.
                mediaDiff = mediaTimes(j + 1) - mediaTimes(j);
                
                % Is the error in the predicted time greater than the
                % interval between media times?
                if timeDiff > mediaDiff
                    isShiftable = false;
                    break;
                end
            end
            
            % Time cannot be shifted due to misalignment between the media
            % times and frame-difference stage movements.
            if ~isShiftable
                warning('findStageMovement:TimeShiftAlignment', ...
                    ['Time cannot be shifted backward because the' ...
                    ' frame-difference stage movement at ' ...
                    num2str(moveTime, '%.3f') ' seconds would have a' ...
                    ' predicted time of ' num2str(predictedTime, '%.3f') ...
                    ' seconds (an error of ' num2str(timeDiff, '%.3f') ...
                    ' seconds) whereas the interval between its media' ...
                    ' time and the previous one is only ' ...
                    num2str(mediaDiff, '%.3f') ' seconds and,' ...
                    ' therefore, smaller than the error from shifting']);
                
            % Shift everything backward.
            else
                mediaTimes(1) = [];
                locations(1,:) = [];
                movesI(end,:) = [];
                timeOff = prevPeakI / fps - mediaTimes(i - 1);
                if verbose
                    peaksI(end) = [];
                    otsuThrs(end) = [];
                    smallThrs(end) = [];
                    timeOffs(1) = [];
                    timeDiffs =  movesI(1:(i - 2),1)' / fps - ...
                        mediaTimes(1:(i - 2));
                    timeOffs(1:(i - 1)) = [mediaTimes(1), ...
                        mediaTimes(2:(i - 1)) + timeDiffs];
                end
                
                % Redo the match.
                i = i - 1;
                
                % Warn about the time shift.
                warning('findStageMovement:TimeShiftBackward', ...
                    ['Shifting the media times backward relative to ' ...
                    'the frame-difference stage movements in an ' ...
                    'attempt to realign them']);
            end
        end
        
        % Record the shift and continue.
        if isShiftable
            isShifted = true;
            continue;
            
        % We cannot realign (shift) the stage movements and media times.
        else
            
            % Compute the stage movement sizes.
            movesI(i:end,:) = [];
            moveSizes = zeros(size(movesI, 1),1);
            for j = 2:(size(movesI, 1) - 1)
                moveDiffs = frameDiffs(movesI(j,1):movesI(j,2));
                moveSizes(j) = sum(moveDiffs(~isnan(moveDiffs)));
            end
            
            % Compute the statistics for stage movement sizes.
            meanMoveSize = mean(moveSizes(2:end));
            stdMoveSize = std(moveSizes(2:end));
            smallMoveThr = meanMoveSize - 2.5 * stdMoveSize;
            largeMoveThr = meanMoveSize + 2.5 * stdMoveSize;
            
            % Are any of the stage movements considerably small or large?
            for j = 2:(size(movesI, 1) - 1)
                
                % Is the stage movement small?
                if moveSizes(j) < smallMoveThr
                    
                    % Report the warning.
                    warning('findStageMovement:ShortMove', ...
                        ['Stage movement ' num2str(j) ...
                        ' at media time ' num2str(mediaTimes(j), '%.3f') ...
                        ' seconds (frame ' ...
                        num2str(round(mediaTimes(j) * fps)) ...
                        '), spanning from ' ...
                        num2str((movesI(j,1) - 1) / fps, '%.3f') ...
                        ' seconds (frame ' num2str(movesI(j,1) - 1) ...
                        ') to ' num2str((movesI(j,2) - 1) / fps, '%.3f') ...
                        ' seconds (frame ' ...
                        num2str(movesI(j,2) - 1) '), is considerably small']);
                    
                % Is the stage movement large?
                elseif moveSizes(j) > largeMoveThr
                    
                    % Report the warning.
                    warning('findStageMovement:LongMove', ...
                        ['Stage movement ' num2str(j) ...
                        ' at media time ' num2str(mediaTimes(j), '%.3f') ...
                        ' seconds (frame ' ...
                        num2str(round(mediaTimes(j) * fps)) ...
                        '), spanning from ' ...
                        num2str((movesI(j,1) - 1) / fps, '%.3f') ...
                        ' seconds (frame ' num2str(movesI(j,1) - 1) ...
                        ') to ' num2str((movesI(j,2) - 1) / fps, '%.3f') ...
                        ' seconds (frame ' ...
                        num2str(movesI(j,2) - 1) '), is considerably large']);
                end
            end
                    
            % Construct the report.
            id = 'findStageMovement:NoShift';
            msg = ['We cannot find a matching peak nor shift the time ' ...
                'for stage movement ' num2str(i) ' at media time ' ...
                num2str(mediaTimes(i), '%.3f') ' seconds (frame ' ...
                num2str(round(mediaTimes(i) * fps)) ')'];
        
            % Report the error.
            if ~verbose
                error(id, msg);
                
            % Report the warning.
            else
                warning(id, msg);
                
                % Finish.
                isMediaTimesMatched = false;
                peaksI(i:end) = [];
                otsuThrs(i:end) = [];
                smallThrs((i - 1):end) = [];
                timeOffs(i:end) = [];
                break;
            end
        end
    end
        
    % Find a temporary back end for this stage movement.
    % Note: this peak may serve as its own temporary back end.
    startI = max(peakI - maxMoveFrames, prevPeakEndI);
    [minDiff j] = min(fliplr(frameDiffs(startI:peakI)));
    peakBackEndI = peakI - j + 1; % we flipped to choose the last min
    j = peakI - 1;
    
    % If the temporary back end's frame difference is small, try to push
    % the back end forwards (closer to the stage movement).
    if minDiff <= prevSmallThr
        while j > startI
            if frameDiffs(j) <= prevSmallThr
                peakBackEndI = j;
                break;
            end
            j = j - 1;
        end
        
    % If the temporary back end's frame difference is large, try to push
    % the back end backwards (further from the stage movement).
    elseif minDiff >= min(otsuThr, gOtsuThr) || ...
            (minDiff > gSmallThr && peakBackEndI > startI && ...
            all(isnan(frameDiffs(startI:(peakBackEndI - 1)))))
        peakBackEndI = startI;
    end
    
    % Compute a threshold for stage movement.
    smallDiffs = frameDiffs(prevPeakEndI:peakBackEndI);
    smallThr = nanmean(smallDiffs) + 3 * nanstd(smallDiffs);
    if isnan(smallThr)
        smallThr = prevSmallThr;
    end
    if (verbose)
        smallThrs(i - 1) = smallThr;
    end
    
    % Find the front end for the previous stage movement.
    j = prevPeakI;
    while j < peakI && (isnan(frameDiffs(j)) || ...
            frameDiffs(j) > smallThr) && (isnan(frameDiffs(j + 1)) || ...
            frameDiffs(j + 1) > smallThr)
        j = j + 1;
    end
    movesI(i - 1,2) = j - 1;
    prevPeakEndI = j - 1;
    
    % Mark the previous stage movement.
    if movesI(i - 1,1) < 1
        frames(1:movesI(i - 1,2)) = true;
    else
        frames(movesI(i - 1,1):movesI(i - 1,2)) = true;
    end
    
    % Find the back end for this stage movement.
    j = peakI;
    while j > prevPeakEndI && (isnan(frameDiffs(j)) || ...
            frameDiffs(j) > smallThr)
        j = j - 1;
    end
    movesI(i, 1) = j + 1;
    
    % Is the non-movement frame-differences threshold too large?
    if smallThr <= otsuThr && (isnan(gOtsuThr) || smallThr <= gOtsuThr)
        prevOtsuThr = otsuThr;
        prevSmallThr = smallThr;
    else
        warning('findStageMovement:LargeNonMovementThreshold', ...
            ['The non-movement window between stage movement ' ...
            num2str(i - 1) ' and stage movement ' num2str(i) ...
            ', from ' num2str((movesI(i - 1,2) - 1) / fps, '%.3f') ...
            ' seconds (frame ' num2str(movesI(i - 1,2) - 1) ...
            ') to ' num2str((movesI(i,1) - 1) / fps, '%.3f') ...
            ' seconds (frame ' num2str(movesI(i,1) - 1) '),' ...
            ' contains considerably large frame-difference variance']);
    end
    
    % Compute the media time offset.
    timeOff = peakTime - mediaTimes(i);
    
    % We reached the end.
    endI = peakI + maxMoveFrames;
    if endI >= length(frameDiffs)
        peakFrontEndI = length(frameDiffs);
        
    % Find a temporary front end for this stage movement.
    else
        [minDiff j] = min(frameDiffs((peakI + 1):endI));
        peakFrontEndI = peakI + j;
        
        % If the temporary front end's frame difference is large, try to
        % push the front end forwards (further from the stage movement).
        if minDiff >= min(otsuThr, gOtsuThr) || ...
                (minDiff > max(smallThr, gSmallThr) && ...
                peakFrontEndI < endI && ...
                all(isnan(frameDiffs((peakFrontEndI + 1):endI))))
            peakFrontEndI = endI;
        end
    end
    
    % Try to push the temporary front end backwards (closer to the stage
    % movement).
    j = peakI + 1;
    while j < peakFrontEndI
        if frameDiffs(j) <= smallThr
            peakFrontEndI = j;
            break;
        end
        j = j + 1;
    end
    
    % Advance.
    prevPeakI = peakI;
    prevPeakEndI = peakFrontEndI;
end

% Do the frame differences end with a stage movement?
if prevPeakEndI > length(frameDiffs)
    movesI(end,2) = length(frameDiffs);
    frames(movesI(end,1):end) = true;
    movesI(end + 1,:) = [length(frameDiffs) length(frameDiffs)] + 1;
    if verbose
        smallThrs(end + 1) = gSmallThr;
    end
    
% Find the front end for the last stage movement.
else
    
    % Is the Otsu threshold large enough?
    searchDiffs = frameDiffs(prevPeakEndI:end);
    otsuThr = graythresh(searchDiffs);
    isOtsu = otsuThr > gOtsuThr; % false if no global Otsu
    if ~isOtsu
        
        % Does the Otsu threshold separate the 99% of the small frame
        % differences from the large ones? And, if there is a global small
        % threshold, is the Otsu threshold larger?
        smallDiffs = searchDiffs(searchDiffs < otsuThr);
        isOtsu = ~isempty(smallDiffs) && sum(~isnan(smallDiffs)) > 0 && ...
            (isnan(gSmallThr) || otsuThr > gSmallThr) && ...
            otsuThr >= median(smallDiffs) + 3 * std(smallDiffs);
        
        % Does the global Otsu threshold pull out any peaks?
        if ~isOtsu
            if ~isnan(gOtsuThr) && sum(searchDiffs > gOtsuThr) > 1
                otsuThr = gOtsuThr;
                isOtsu = true;
            end
        end
    end
    
    % Are there any large frame difference past the last stage movement?
    isExtraPeaks = false;
    if ~isOtsu
        peakI = length(frameDiffs) + 1;
        peakBackEndI = length(frameDiffs);
        
    % There are too many large frame-difference peaks.
    else
        [~, indices] = ...
            maxPeaksDistHeight(searchDiffs, maxMoveFrames, otsuThr);
        isExtraPeaks = ~isempty(indices);
        if verbose
            endPeaksI = indices + prevPeakEndI - 1;
        end
        
        % Find the first large peak past the last stage movement.
        i = prevPeakEndI;
        while i < length(frameDiffs) && (isnan(frameDiffs(i)) || ...
                frameDiffs(i) < otsuThr)
            i = i + 1;
        end
        peakI = i;
        
        % Find a temporary back end for this large peak.
        % Note: this peak may serve as its own temporary back end.
        startI = max(peakI - maxMoveFrames, prevPeakEndI);
        [minDiff i] = min(fliplr(frameDiffs(startI:peakI)));
        peakBackEndI = peakI - i + 1; % we flipped to choose the last min
        
        % If the temporary back end's frame difference is small, try to
        % push the back end forwards (closer to the stage movement).
        if minDiff <= prevSmallThr
            i = peakI - 1;
            while i > startI
                if frameDiffs(i) <= prevSmallThr
                    peakBackEndI = i;
                    break;
                end
                i = i - 1;
            end
            
        % If the temporary back end's frame difference is large, try to
        % push the back end backwards (further from the stage movement).
        elseif minDiff >= min(otsuThr, gOtsuThr) || ...
                (minDiff > gSmallThr && peakBackEndI > startI && ...
                all(isnan(frameDiffs(startI:(peakBackEndI - 1)))))
            peakBackEndI = startI;
        end
    end
            
    % Compute a threshold for stage movement.
    smallDiffs = frameDiffs(prevPeakEndI:peakBackEndI);
    smallThr = nanmean(smallDiffs) + 3 * nanstd(smallDiffs);
    if isnan(smallThr)
        smallThr = prevSmallThr;
    end
    if (verbose)
        smallThrs(end + 1) = smallThr;
    end
    
    % Find the front end for the last logged stage movement.
    i = prevPeakI;
    while i < peakI && ((isnan(frameDiffs(i)) || ...
            frameDiffs(i) > smallThr) && ...
            (isnan(frameDiffs(i + 1)) || ...
            frameDiffs(i + 1) > smallThr))
        i = i + 1;
    end
    movesI(end,2) = i - 1;
    prevPeakEndI = i - 1;
    
    % Mark the last logged stage movement.
    if size(movesI, 1) == 1
        frames(1:movesI(end,2)) = true;
    else
        frames(movesI(end,1):movesI(end,2)) = true;
    end
    
    % Are there any large frame-difference peaks after the last logged
    % stage movement?
    if isExtraPeaks
        warning('findStageMovement:TooManyPeaks', ...
            ['There are, approximately, ' num2str(length(indices)) ...
            ' large frame-difference peaks after the last stage' ...
            ' movement ends at ' num2str((movesI(end,2) - 1)/ fps, '%.3f') ...
            ' seconds (frame ' num2str(movesI(end,2) - 1) ')']);
    end
    
    % Find the back end for logged stage movements.
    i = peakI - 1;
    while i > prevPeakEndI && (isnan(frameDiffs(i)) || ...
            frameDiffs(i) > smallThr)
        i = i - 1;
    end
    movesI(end + 1,:) = [i + 1, length(frameDiffs) + 1];
    frames(movesI(end,1):end) = true;
end

% Are any of the stage movements considerably small or large?
if (~verbose || isMediaTimesMatched) && isExtraPeaks
    
    % Compute the stage movement sizes.
    movesI(i:end,:) = [];
    moveSizes = zeros(size(movesI, 1),1);
    for j = 2:(size(movesI, 1) - 1)
        
        moveDiffs = frameDiffs(movesI(j,1):movesI(j,2));
        moveSizes(j) = sum(moveDiffs(~isnan(moveDiffs)));
        
%         % Interpolate over NaNs.
%         moveDiffs = frameDiffs((movesI(j,1) - 1):(movesI(j,2) + 1));
%         moveDiffs(isnan(moveDiffs)) = ...
%             interp1(find(~isnan(moveDiffs)), ...
%             moveDiffs(~isnan(moveDiffs)), find(isnan(moveDiffs)), ...
%             'linear');
%         moveSizes(j) = sum(moveDiffs(~isnan(moveDiffs(2:end-1))));
    end
    
    % Compute the statistics for stage movement sizes.
    meanMoveSize = mean(moveSizes(2:end));
    stdMoveSize = std(moveSizes(2:end));
    smallMoveThr = meanMoveSize - 2.5 * stdMoveSize;
    largeMoveThr = meanMoveSize + 2.5 * stdMoveSize;
    
    % Are any of the stage movements considerably small or large?
    for i = 2:(size(movesI, 1) - 1)
        
        % Is the stage movement small?
        if moveSizes(i) < smallMoveThr
            
            % Report the warning.
            warning('findStageMovement:ShortMove', ...
                ['Stage movement ' num2str(i) ...
                ' at media time ' num2str(mediaTimes(i), '%.3f') ...
                ' seconds (frame ' ...
                num2str(round(mediaTimes(i) * fps)) ...
                '), spanning from ' ...
                num2str((movesI(i,1) - 1) / fps, '%.3f') ...
                ' seconds (frame ' num2str(movesI(i,1) - 1) ...
                ') to ' num2str((movesI(i,2) - 1) / fps, '%.3f') ...
                ' seconds (frame ' ...
                num2str(movesI(i,2) - 1) '), is considerably small']);
            
        % Is the stage movement large?
        elseif moveSizes(i) > largeMoveThr
            
            % Report the warning.
            warning('findStageMovement:LongMove', ...
                ['Stage movement ' num2str(i) ...
                ' at media time ' num2str(mediaTimes(i), '%.3f') ...
                ' seconds (frame ' ...
                num2str(round(mediaTimes(i) * fps)) ...
                '), spanning from ' ...
                num2str((movesI(i,1) - 1) / fps, '%.3f') ...
                ' seconds (frame ' num2str(movesI(i,1) - 1) ...
                ') to ' num2str((movesI(i,2) - 1) / fps, '%.3f') ...
                ' seconds (frame ' ...
                num2str(movesI(i,2) - 1) '), is considerably large']);
        end
    end
end

% Show the stage movements.
if verbose
    
    % Open up a big figure.
    isGUI = true;
    if isempty(guiHandle)
        figure('OuterPosition', [50 50 1280 960]);
        guiHandle = axes;
        isGUI = false;
    end
    hold on;
    
    % Plot the video frame differences. Then plot the offset stage movement
    % times and their otsu thresholds on the same axes.
    [ax h1 h2] = plotyy(guiHandle, 0:(length(frameDiffs) - 1), ...
        frameDiffs, timeOffs, otsuThrs);
    set(ax(2), 'XAxisLocation', 'top');
    set(h1, 'Color', 'r');
    set(h2, 'Color', 'b', 'LineStyle', 'none', 'Marker', '.');
    
    % Setup the axes colors.
    set(ax(1), 'XColor', 'r', 'YColor', 'r');
    set(ax(2), 'XColor', 'k', 'YColor', 'k');
    
    % Setup the axes numbering.
    linkaxes(ax, 'y');
    xlim(ax(1), [0 (length(frameDiffs) - 1)]);
    xlim(ax(2), [0 ((length(frameDiffs) - 1) / fps)]);
    set(ax(2), 'YTick', []);
    set(zoom(guiHandle), 'Motion', 'horizontal', 'Enable', 'on');
    
    % Setup the axes labels.
    xlabel(ax(1), 'Frame');
    ylabel(ax(1), 'Subsequent Frame-Difference Variance');
    xlabel(ax(2), 'Time (seconds)');
    if ~isGUI % underscores confuse TeX
        title(ax(2), strrep(logFile, '_', '\_'));
    end
    
    % Setup the legends.
    legends1{1} = 'Variance of Subsequent Frame Differences';
    legends2 = [];
    if ~isempty(timeOffs)
        legends2{end + 1} = ...
            'Offset Movement Times at Otsu Threshold Height';
    end
    
    % Hold on.
    hold(ax(1), 'on');
    hold(ax(2), 'on');
    
    % Plot the offset stage movement times and their otsu thresholds.
    if verbose > 1
        text(timeOffs, otsuThrs, num2str((1:length(timeOffs))'), ...
            'Color', 'b', 'Parent', ax(2));
    end
    
    % Pretty plot the stage movements.
    % Note: earlier, we shifted the frame differences over one to align
    % them with the video frames. Due to differentiation and this shift,
    % the large differences at the end of stage movements represent a drop
    % in variance and, therefore, a non-movement frame. Visually, it's much
    % easier to recognize correct stage movement detection by aligning the
    % start and end of large differences with frame status. Therefore, we
    % extend the end of detected stage movements by one in order to achieve
    % visual alignment of large frame differences and stage movement intervals.
    plotFrames = frames;
    if movesI(1,2) > 0
        plotFrames(movesI(1,2) + 1) = true;
    end
    plotFrames(movesI(2:(end - 1),2) + 1) = true;
    plot(ax(1), 0:(length(plotFrames) - 1), plotFrames, 'k');
    if ~isempty(plotFrames)
        legends1{end + 1} = ...
            'Stage Movements (Shifted for Variance Alignment)';
    end
    
    % Plot the small thresholds.
    plotThrs(1:length(frames)) = NaN;
    startI = 1;
    if movesI(1,2) > 0
        startI = movesI(1,2) + 2;
    end
    plotThrs(startI:(movesI(2,1) - 1)) = smallThrs(1);
    for i = 2:(size(movesI, 1) - 1)
        plotThrs((movesI(i,2) + 2):(movesI(i + 1,1)) - 1) = smallThrs(i);
    end
    plot(ax(1), 0:(length(plotThrs) - 1), plotThrs, 'c');
    if ~isempty(plotThrs)
        legends1{end + 1} = 'Non-movement Thresholds';
    end
    
    % Plot the matched video frame difference peaks.
    brown = [.5 .3 .1];
    plot(ax(1), peaksI - 1, frameDiffs(peaksI), '.', 'Color', brown);
    if ~isempty(peaksI)
        legends1{end + 1} = 'Movement Peaks';
    end
    if verbose > 1
        matchedPeaksStr = num2str((1:length(peaksI))');
        text(peaksI - 1, frameDiffs(peaksI), matchedPeaksStr, ...
            'Color', brown, 'Parent', ax(1));
    end
    
    % Plot the unmatched video frame difference peaks.
    yellow = [1 .8 .2];
    plot(ax(1), endPeaksI - 1, frameDiffs(endPeaksI), '.', ...
        'Color', yellow);
    if ~isempty(endPeaksI)
        legends1{end + 1} = 'Unmatched Peaks';
    end
       
    % Plot the matched stage movement times and their small thresholds.
    matchedMediaTimes = mediaTimes(1:length(peaksI));
    matchedSmallThrs = [gSmallThr smallThrs(1:(length(peaksI) - 1))];
    plot(ax(2), matchedMediaTimes, matchedSmallThrs, 'g.');
    if ~isempty(matchedMediaTimes)
        legends2{end + 1} = ...
            'Movement Times at Non-Movement Threshold Height';
    end
    if verbose > 1
        text(matchedMediaTimes, matchedSmallThrs, matchedPeaksStr, ...
            'Color', 'g', 'Parent',ax(2));
    end
    
    % Plot the unmatched stage movement times.
    unmatchedMediaTimes = ...
        mediaTimes((length(peaksI) + 1):length(mediaTimes));
    unmatchedMediaTimesY = zeros(length(unmatchedMediaTimes), 1);
    plot(ax(2), unmatchedMediaTimes, unmatchedMediaTimesY, 'm.');
    if ~isempty(unmatchedMediaTimes)
        legends2{end + 1} = 'Unmatched Stage Movements';
    end
    if verbose > 1
        text(unmatchedMediaTimes, unmatchedMediaTimesY, ...
            num2str(((length(peaksI) + 1):length(mediaTimes))'), ...
            'Color', 'm', 'Parent', ax(2));
    end
    
    % Show the legend.
    legends1((end + 1):(end + length(legends2))) = legends2;
    legend(ax(1), legends1, 'Location', 'NorthEast');
    
    % Hold off.
    hold(ax(1), 'off');
    hold(ax(2), 'off');
    
    % Report the unmatched stage movements.
    if ~isempty(unmatchedMediaTimes)
        error('findStageMovement:UnmatchedStageMovements', ...
            ['There are ' num2str(length(unmatchedMediaTimes)) ...
            ' stage movements that couldn''t be matched to ' ...
            'large, appropriately-timed frame differences']);
    end
end
%end
