# Zebrafish Skeleton


import cv2
import numpy as np
from scipy.spatial import KDTree

from MWTracker.analysis.ske_create.segWormPython.cythonFiles.segWorm_cython import circComputeChainCodeLengths
from MWTracker.analysis.ske_create.segWormPython.cythonFiles.circCurvature import circCurvature
from MWTracker.analysis.ske_create.segWormPython.cleanWorm import extremaPeaksCircDist


def getFishContour(mask):

	im, contours, hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

	return contours[0]


def getTailPointViaModelEndPoints(smoothed_points, fish_contour):

	last_point = smoothed_points[-1]

	tail_x = last_point[0]
	tail_y = last_point[1]

	point = (tail_x, tail_y)

	contour_point = closestPoint(fish_contour, point)

	return contour_point


def getTailPointViaMaximumCurvature(contour):

	# Experimental - Adapted from worm code

	contour = np.vstack(contour).squeeze()

	contour = contour.astype(np.float32)

	if contour.dtype != np.double:
		contour = contour.astype(np.double)

	ske_worm_segments = 24
	cnt_worm_segments = 2. * ske_worm_segments

	signed_area = np.sum(contour[:-1, 0] * contour[1:, 1] - contour[1:, 0] * contour[:-1, 1]) / 2

	if signed_area > 0:
		contour = np.ascontiguousarray(contour[::-1, :])

	# make sure the array is C_continguous. Several functions required this.
	if not contour.flags['C_CONTIGUOUS']:
		contour = np.ascontiguousarray(contour)

	cnt_chain_code_len = circComputeChainCodeLengths(contour)
	worm_seg_length = (cnt_chain_code_len[0] + cnt_chain_code_len[-1]) / cnt_worm_segments

	edge_len_hi_freq = worm_seg_length
	cnt_ang_hi_freq = circCurvature(contour, edge_len_hi_freq, cnt_chain_code_len)

	edge_len_low_freq = 2 * edge_len_hi_freq
	cnt_ang_low_freq = circCurvature(contour, edge_len_low_freq, cnt_chain_code_len)

	maxima_hi_freq, maxima_hi_freq_ind = extremaPeaksCircDist(1, cnt_ang_hi_freq, edge_len_hi_freq, cnt_chain_code_len)

	maxima_low_freq, maxima_low_freq_ind = extremaPeaksCircDist(1, cnt_ang_low_freq, edge_len_low_freq, cnt_chain_code_len)

	threshold = 100
	indices_to_delete = []
	for i, val in np.ndenumerate(maxima_low_freq):
		if val < threshold:
			indices_to_delete.append(i)

	maxima_low_freq = np.delete(maxima_low_freq, indices_to_delete)
	maxima_low_freq_ind = np.delete(maxima_low_freq_ind, indices_to_delete)

	tail_freq_index = maxima_hi_freq.argmax()
	tail_ind = maxima_hi_freq_ind[tail_freq_index]

	return tail_ind


def closestPoint(contour, point):

	# Return the index of the point on the contour closest to 'point' using a k-d tree

	# Remove nesting in contour
	contour = np.vstack(contour).squeeze()

	point = np.array(point)

	d, i = KDTree(contour).query(point)

	return i


def rollSkeletonContour(contour, head_index, tail_index):

	# Roll contour to make tail at index 0

	contour_size = contour.shape[0]

	shift_val = contour_size - tail_index

	rolled_contour = np.roll(contour, shift_val, axis=0)

	# Calculate new head index

	rolled_head_index = abs(head_index + shift_val)

	if rolled_head_index >= contour_size:
		rolled_head_index = rolled_head_index - contour_size

	# Calculate new tail index

	rolled_tail_index = abs(tail_index + shift_val)

	if rolled_tail_index >= contour_size:
		rolled_tail_index = rolled_tail_index - contour_size

	return rolled_contour, rolled_head_index, rolled_tail_index


def getSideContours(rolled_contour, head_index):

	# Note: Assumes the contour has already been rolled, ie. the tail point is at index 0

	# Remove nesting
	rolled_contour = np.vstack(rolled_contour).squeeze()

	side_contour_1 = rolled_contour[:head_index + 1]

	side_contour_2 = rolled_contour[head_index:][::-1]
	np.insert(side_contour_2, 0, rolled_contour[0])

	return side_contour_1, side_contour_2


def getSkeleton(contour_side_1, contour_side_2):

	skel = []

	if len(contour_side_1) > len(contour_side_2):
		larger_side = contour_side_1
		smaller_side = contour_side_2
	else:
		larger_side = contour_side_2
		smaller_side = contour_side_1

	smaller_side_increment =  len(smaller_side) / len(larger_side)

	i = 0

	for point in larger_side:
		x1 = point[0]
		y1 = point[1]

		smaller_contour_index = int( i * smaller_side_increment )

		x2 = smaller_side[smaller_contour_index, 0]
		y2 = smaller_side[smaller_contour_index, 1]

		midpoint_x = int( x1 + np.ceil((x2 - x1) / 2) )
		midpoint_y = int( y1 + np.ceil((y2 - y1) / 2) )

		midpoint = (midpoint_x, midpoint_y)

		skel.append(midpoint)

		i += 1


	return skel


def getZebrafishSkeleton(cleaned_mask, head_point, smoothed_points, config):

	# Get fish contour
	fish_contour = getFishContour(cleaned_mask)

	# Get head point index
	head_point_index = closestPoint(fish_contour, head_point)

	# Get tail point index

	# 'Model End Point' method
	if config.tail_point_detection_algorithm == "MAXIMUM_CURVATURE":
		tail_point_index = getTailPointViaMaximumCurvature(fish_contour)
	else: # Default == 'MODEL_END_POINT'
		tail_point_index = getTailPointViaModelEndPoints(smoothed_points, fish_contour)

	# Roll skeleton contour so tail point is at index 0
	rolled_contour, new_head_point_index, new_tail_point_index = rollSkeletonContour(fish_contour, head_point_index, tail_point_index)

	# Get side contours
	cnt_side1, cnt_side2 = getSideContours(rolled_contour, new_head_point_index)

	# Get skeleton
	skeleton = getSkeleton(cnt_side1, cnt_side2)
	skeleton = np.array(skeleton) # Convert to Numpy array

	# Get other variables to return
	ske_len = len(skeleton)
	cnt_widths = np.zeros(len(skeleton)) # TODO
	cnt_area = cv2.contourArea(fish_contour)

	return skeleton, ske_len, cnt_side1, cnt_side2, cnt_widths, cnt_area