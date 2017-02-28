# Zebrafish Analysis


import math
import numpy as np
import cv2

from scipy.signal import savgol_filter


class ModelConfig:

	def __init__(self, num_segments, min_angle, max_angle, num_angles, tail_length, tail_detection, prune_retention, test_width, draw_width, auto_detect_tail_length):

		self.min_angle = min_angle # Minimum angle for each segment (relative to previous segment)
		self.max_angle = max_angle # Maximum angle for each segment
		self.num_models_per_segment = num_angles # Number of angles to try for each segment

		self.prune_freq = 1 # When constructing the model, segment interval at which the model pruning function is called. Lower numbers are faster
		self.max_num_models_to_keep = prune_retention # Number of models retained after each round of pruning

		segment_height = int(tail_length / num_segments)
		self.segment_heights = [segment_height] * num_segments # Length must match num_segments
		self.segment_widths = [test_width] * num_segments # Used for constructing and testing straight-line models. Length must match num_segment

		self.num_segments = num_segments

		self.smoothed_segment_width = draw_width # Used for drawing the final smoothed version of the tail curve

		self.tail_offset = 30 # Distance in pixels from the head point to the tail model start point

		self.rotated_img_size = 200 # Size of the internal image of the rotated fish

		self.tail_point_detection_algorithm = tail_detection

		# Auto-detect tail length settings
		self.auto_detect_tail_length = auto_detect_tail_length
		if auto_detect_tail_length:
			# Override number of segments with a high number
			# Tail end will be detected automatically before this is reached and model generation will be stopped at that point
			self.num_segments = 20
			self.segment_heights = [5] * self.num_segments
			self.segment_widths  = [2] * self.num_segments
			self.segment_score_improvement_threshold = 250 # Amount by which a segment must improve the model score to be considered valid. If 'num_fail_segments' segments in a row are considered invalid, no further segments are added to that model
			self.num_fail_segments = 2 # Number of continuous segments which fail to meet the threshold improvement score for model generation to stop
			self.min_segments = 5 # Minimum number of segments in the model - There will be at least this many segments, even if the failing criteria is reached


class MaskCanvas:

	def __init__(self, canvas_width, canvas_height):
		self.canvas = np.zeros((canvas_width, canvas_height), np.uint8)
		self.points = []
		self.scores = [0]
		self.angle_offset = 0


	def add_point(self, point):
		self.points.append(point)


	def last_point(self):
		return self.points[-1] if len(self.points) > 0 else None


	def last_score(self):
		return self.scores[-1]


	def score_improvement(self, n):
		if len(self.scores) < n + 1:
			return 0
		return self.scores[-1 * n] - self.scores[-1 * (n+1)]


def getOrientation(frame, config):

	th_val = 1

	ret, binary_img = cv2.threshold(frame, th_val, 255, cv2.THRESH_BINARY)

	im, contours, hierarchy = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

	# Sort contours by area
	contours.sort(key=lambda ar: cv2.contourArea(ar))

	largest_contour = contours[-1]

	[vx, vy, x, y] = cv2.fitLine(largest_contour, cv2.DIST_L2, 0, 0.01, 0.01)
	line_angle = math.atan2(vy, vx)
	line_angle_degrees = math.degrees(line_angle)

	angle = line_angle_degrees + 90

	x, y, w, h = cv2.boundingRect(largest_contour)

	img_cropped = frame[y:y+h, x:x+w]

	rotated_img, actual_angle = rotateFishImage(img_cropped, angle, config)

	return rotated_img, actual_angle


def rotateFishImage(img, angle_degrees, config):

	input_image = np.zeros((config.rotated_img_size, config.rotated_img_size), np.uint8)

	y_mid = config.rotated_img_size // 2
	def _get_range(l):
		bot = math.floor(y_mid - l/2)
		top = math.floor(y_mid + l/2)
		return bot, top

	h_ran, w_ran = list(map(_get_range, img.shape))
	input_image[h_ran[0]:h_ran[1], w_ran[0]:w_ran[1]] = img

	rows, cols = input_image.shape
	center = (rows//2, cols//2)

	M = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
	rotated_img = cv2.warpAffine(input_image, M, (cols, rows))

	

	img_top = rotated_img[0:y_mid, 0:config.rotated_img_size]
	img_bottom = rotated_img[y_mid:config.rotated_img_size, 0:config.rotated_img_size]

	# Use valid pixel count to determine which half contains the head

	top_area = len(img_top[img_top != 0])
	bottom_area = len(img_bottom[img_bottom != 0])

	head_half = img_top if bottom_area < top_area else img_bottom

	# Find rotation angle again, this time only using the head half

	im, contours, hierarchy = cv2.findContours(head_half.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
	contours.sort(key=lambda ar: ar.size)
	largest_contour = contours[-1]

	[vx, vy, x, y] = cv2.fitLine(largest_contour, cv2.DIST_L2, 0, 0.01, 0.01)
	line_angle = math.atan2(vy, vx)
	line_angle_degrees = (math.degrees(line_angle) + 90) % 360

	final_angle = (angle_degrees + line_angle_degrees) % 360

	rows, cols = input_image.shape[:2]
	center = (rows/2, cols/2)
	M = cv2.getRotationMatrix2D(center, final_angle, 1.0)
	rotated_output_img = cv2.warpAffine(input_image, M, (cols, rows))

	# Check again whether the image is rotated 180 degrees, and correct if necessary

	img_top = rotated_output_img[0:y_mid, 0:config.rotated_img_size]
	img_bottom = rotated_output_img[y_mid:config.rotated_img_size, 0:config.rotated_img_size]

	top_area = len(img_top[img_top != 0])
	bottom_area = len(img_bottom[img_bottom != 0])

	if bottom_area > top_area:
		correction_angle = 180
		M = cv2.getRotationMatrix2D(center, correction_angle, 1.0)
		rotated_output_img = cv2.warpAffine(rotated_output_img, M, (cols, rows))
		final_angle = (final_angle + correction_angle) % 360

	return rotated_output_img, final_angle


def getHeadMask(frame):

	th_val = 1

	ret, img_thresh = cv2.threshold(frame, th_val, 255, cv2.THRESH_BINARY)

	# Remove excess noise by drawing only the largest contour

	head_mask = np.zeros((img_thresh.shape[0], img_thresh.shape[1]), np.uint8)

	im, contours, hierarchy = cv2.findContours(img_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
	contours.sort(key=lambda ar: ar.size)
	head_contour = contours[-1]

	cv2.drawContours(head_mask, [head_contour], 0, 255, cv2.FILLED)

	return head_mask


def getHeadPoint(rotated_img, angle):

	theta = math.radians(- angle)

	img_binary = np.zeros(rotated_img.shape, np.uint8)
	im, contours, hierarchy = cv2.findContours(rotated_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
	contours.sort(key=lambda ar: ar.size)
	largest_contour = contours[-1]
	cv2.drawContours(img_binary, [largest_contour], 0, 255, cv2.FILLED)

	valid_pixels = np.nonzero(img_binary)

	x = valid_pixels[1]
	y = valid_pixels[0]

	head_x = x[np.argmin(y)]
	head_y = np.min(y)

	w, h = rotated_img.shape[:2]
	center_x = w / 2
	center_y = h / 2

	hypot = math.hypot(center_x - head_x, center_y - head_y)

	rotated_head_x = center_x - (hypot * math.sin(theta))
	rotated_head_y = center_y - (hypot * math.cos(theta))

	return rotated_head_x, rotated_head_y


def getTailStartPoint(head_mask, head_point, config):

	# Calculate the angle from the head point to the contour center
	# Then, 'walk' down the line from the head point to the contour center point a set length

	im, contours, hierarchy = cv2.findContours(head_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
	contour = contours[-1]

	# Get contour center
	contour_moments = cv2.moments(contour)
	contour_center_x = int(contour_moments['m10'] / contour_moments['m00'])
	contour_center_y = int(contour_moments['m01'] / contour_moments['m00'])

	head_x = head_point[0]
	head_y = head_point[1]

	head_contour_center_angle = math.atan2(contour_center_y - head_y, contour_center_x - head_x)

	head_x = head_point[0]
	head_y = head_point[1]

	# Calculate tail start point
	tail_start_x = head_x + config.tail_offset * math.cos(head_contour_center_angle)
	tail_start_y = head_y + config.tail_offset * math.sin(head_contour_center_angle)

	return (int(tail_start_x), int(tail_start_y))


def getModelMasks(head_mask, base_angle, frame, head_point, config):

	# Generate the test image used for scoring models
	test_image = getTestImage(frame, head_mask, head_point, base_angle, config)

	# Create starting object
	initial_canvas = MaskCanvas(head_mask.shape[0], head_mask.shape[1])

	# Add tail starting point
	initial_point = getTailStartPoint(head_mask, head_point, config)
	initial_canvas.add_point(initial_point)

	# Set base angle
	initial_canvas.angle_offset = -base_angle

	canvas_set = [initial_canvas]
	output_canvas_set = drawModelSegments(canvas_set, config.num_segments, test_image, config)

	return output_canvas_set


def getTestImage(frame, head_mask, head_point, angle, config):

	# Remove the head from the test image using a triangular mask, so it doesn't interfere with tail model scoring

	center_x, center_y = getTailStartPoint(head_mask, head_point, config)

	triangle_length = 100

	t0_angle_radians = math.radians(angle)
	t0_x = center_x + triangle_length * math.sin(t0_angle_radians)
	t0_y = center_y - triangle_length * math.cos(t0_angle_radians)

	t1_angle_radians = math.radians(angle - 90)
	t1_x = center_x + triangle_length * math.sin(t1_angle_radians)
	t1_y = center_y - triangle_length * math.cos(t1_angle_radians)

	t2_angle_radians = math.radians(angle + 90)
	t2_x = center_x + triangle_length * math.sin(t2_angle_radians)
	t2_y = center_y - triangle_length * math.cos(t2_angle_radians)

	triangle_points = np.array([(t0_x, t0_y), (t1_x, t1_y), (t2_x, t2_y)]).astype('int32')

	test_image = frame.copy()
	cv2.fillConvexPoly(test_image, triangle_points, 0)

	return test_image


def drawModelSegments(canvas_set, num_segments, test_image, config):

	angle_increment = (config.max_angle - config.min_angle) / config.num_models_per_segment

	output_set = []

	for canvas in canvas_set:

		for i in range(0, config.num_models_per_segment + 1):

			# Calculate segment rotation angle
			rotation_angle = config.min_angle + (i * angle_increment)

			# Draw line on canvas

			new_canvas = MaskCanvas(0, 0)
			new_canvas.canvas = canvas.canvas.copy()
			new_canvas.points = list(canvas.points)
			new_canvas.angle_offset = canvas.angle_offset
			new_canvas.scores = list(canvas.scores)

			segment_width = config.segment_widths[-num_segments]
			segment_height = config.segment_heights[-num_segments]

			canvas_with_segment = drawSegmentOnCanvas(new_canvas, rotation_angle, segment_width, segment_height)

			# Add canvas to output set
			output_set.append(canvas_with_segment)

	# Prune the models with the lowest scores
	if num_segments % config.prune_freq == 0:
		end_generation, output_set = pruneModels(test_image, output_set, config.max_num_models_to_keep, config)

	# If auto-detect tail length is enabled, check for 'end model generation' flag
	if config.auto_detect_tail_length:
		if end_generation is True and num_segments < config.num_segments - config.min_segments:
			i = len(output_set[0].points) - config.num_fail_segments # Remove the final failing segments
			output_set[0].points = output_set[0].points[0:i]
			return output_set

	# Call the function recursively until all segments have been drawn on the canvases
	if num_segments > 1:
		return drawModelSegments(output_set, num_segments - 1, test_image, config)
	else:
		return output_set


def drawSegmentOnCanvas(canvas, angle, segment_width, segment_height):

	# Take into account previous angles
	adjusted_angle = angle + canvas.angle_offset

	# Convert angle from degrees to radians
	angle_radians = math.radians(adjusted_angle)

	# Calculate position of next point
	pt_x = canvas.last_point()[0] + segment_height * math.sin(angle_radians)
	pt_y = canvas.last_point()[1] + segment_height * math.cos(angle_radians)
	pt = (int(pt_x), int(pt_y))

	# Draw line connecting points
	cv2.line(canvas.canvas, canvas.last_point(), pt, 255, thickness=segment_width, lineType=cv2.LINE_AA)

	# Add the new point to the MaskCanvas object's list of points
	canvas.add_point(pt)

	# Update 'angle_offset' on the MaskCanvas object
	canvas.angle_offset += angle

	return canvas


def pruneModels(test_image, canvas_set, max_num_models_to_keep, config):

	for canvas in canvas_set:
		score = scoreModel(canvas, test_image)
		canvas.scores.append(score)

	# Order canvas list by scores
	canvas_set.sort(key=lambda c: c.last_score())

	# Remove all masks except the ones with the top scores
	keep_num = max_num_models_to_keep if len(canvas_set) > max_num_models_to_keep else len(canvas_set)
	pruned_set = canvas_set[-keep_num:]

	# Return the pruned set of models if tail length auto-detection is off
	if config.auto_detect_tail_length == False:
		return False, pruned_set

	# Otherwise, decide whether to continue adding segments to the models or not

	best_canvas = canvas_set[-1]

	# If the set continuous number of segments fail to meet the threshold improvement score,
	# signal that the model should stop being generated (ie. no further segments should be added, and the final
	# failing x segments should be removed from the model)

	end_generation = False
	for x in range(1, config.num_fail_segments + 1):

		if best_canvas.score_improvement(x) > config.segment_score_improvement_threshold:
			break

		if x == config.num_fail_segments:
			end_generation = True

	return end_generation, pruned_set


def scoreModel(canvas, test_image):

	# Find pixels in the test image which overlap with the model
	masked_img = cv2.bitwise_and(test_image, test_image, mask=canvas.canvas)

	# Get non-zero pixels
	valid_pixels = masked_img[masked_img != 0]

	# Adjust pixel values so that darker pixels will score higher than lighter pixels (as fish is darker than the background)
	adjusted_vals = 256 - valid_pixels

	# Calculate score
	score = int(cv2.sumElems(adjusted_vals)[0])

	return score


def smoothMaskModel(mask_canvas, config):

	points = mask_canvas.points

	points = np.array(points)
	points = points.astype(int)

	x = points[:, 0]
	y = points[:, 1]

	window_length = len(y)

	if window_length % 2 == 0:
		window_length -= 1

	polyorder = 3
	yhat = savgol_filter(y, window_length, polyorder)

	output_points = []
	for a, b in zip(x, yhat):
		new_point = [a, b]
		output_points.append(new_point)
	output_points = np.array(output_points)
	output_points = output_points.astype(int)

	mask = np.zeros(mask_canvas.canvas.shape, np.uint8)
	cv2.polylines(mask, [output_points], False, 255, thickness=config.smoothed_segment_width)

	return mask, output_points


def getCombinationMask(head_mask, tail_mask):

	combination_mask = cv2.add(head_mask, tail_mask)

	return combination_mask


def cleanMask(mask):

	# Apply closing to smooth the edges of the mask

	kernel_size = 5
	kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))  # Circle

	mask_closing = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

	return mask_closing


def getZebrafishMask(frame, config):

	# Get orientated image and rotation angle
	rotated_img, angle = getOrientation(frame, config)

	# Get head mask
	head_mask = getHeadMask(frame)

	# Get head point
	head_point = getHeadPoint(rotated_img, angle)

	# Get model masks
	model_masks = getModelMasks(head_mask, angle, frame, head_point, config)

	# Get best mask
	test_image = getTestImage(frame, head_mask, head_point, angle, config)
	_, mask_set = pruneModels(test_image, model_masks, 1, config)
	best_mask = mask_set[0]

	# Smooth the best mask
	smoothed_mask, smoothed_points = smoothMaskModel(best_mask, config)

	# Get combination mask
	combination_mask = getCombinationMask(head_mask, smoothed_mask)

	# Clean mask
	cleaned_mask = cleanMask(combination_mask)

	worm_mask = cleaned_mask.copy()

	im, contours, hierarchy = cv2.findContours(cleaned_mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)


	if len(contours) == 0:
		output = None

	else:
		# Remove nesting from contour
		worm_cnt = contours[0]
		worm_cnt = np.vstack(worm_cnt).squeeze()

		# Return None values if contour too small
		if len(worm_cnt) < 3:
			output = None
		else:
			cnt_area = cv2.contourArea(worm_cnt)
			output = worm_mask, worm_cnt, cnt_area, \
				   cleaned_mask, head_point, smoothed_points
	
	if output is None:
		return [None]*6
	else:
		return output

