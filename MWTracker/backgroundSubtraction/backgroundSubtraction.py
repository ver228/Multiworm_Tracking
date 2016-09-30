# Background Subtraction


import numpy as np
import cv2


def getBackground(vid, video_file, current_frame, frame_advance=500, generation_function='MAXIMUM'):

	current_frame_num = vid.get(cv2.CAP_PROP_POS_FRAMES)
	future_frame_num = current_frame_num + frame_advance

	original_vid_total_frames = vid.get(cv2.CAP_PROP_FRAME_COUNT)

	if future_frame_num >= original_vid_total_frames:
		future_frame_num = current_frame_num - frame_advance

	source_vid = cv2.VideoCapture(video_file)
	source_vid.set(cv2.CAP_PROP_POS_FRAMES, future_frame_num)

	result, future_frame = source_vid.read()

	if future_frame.ndim == 3:
		future_frame = cv2.cvtColor(future_frame, cv2.COLOR_RGB2GRAY)

	if current_frame.ndim == 3:
		current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2GRAY)

	if generation_function == 'MINIMUM':
		return np.minimum(current_frame, future_frame)
	elif generation_function == 'MAXIMUM':
		return np.maximum(current_frame, future_frame)
	else:
		return None


def applyBackgroundSubtraction(frame, background_img, th):

	# Subtract background image from frame

	if frame.ndim == 3:
		frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

	if background_img.ndim == 3:
		background_img = cv2.cvtColor(background_img, cv2.COLOR_RGB2GRAY)

	subtracted_img = cv2.subtract(background_img, frame)

	# Use the subtracted image to generate a mask and apply it to the original frame

	ret, mask = cv2.threshold(subtracted_img, th, 255, cv2.THRESH_BINARY)
	img_masked = cv2.bitwise_and(frame, frame, mask=mask)

	return img_masked