import json

import numpy as np
import tables

from MWTracker.analysis.ske_filt.getFilteredSkels import _h_calAreaSignedArray


def hasExpCntInfo(skeletons_file):
    # i'm reading this data twice (one more in switchCntSingleWorm), but I think this is cleaner
    # from a function organization point of view.
    with tables.File(skeletons_file, 'r') as fid:
        if not '/experiment_info' in fid:
            return False
        exp_info_b = fid.get_node('/experiment_info').read()
        exp_info = json.loads(exp_info_b.decode("utf-8"))

        # print('ventral_side:{}'.format(exp_info['ventral_side']))
        # only clockwise and anticlockwise are valid contour orientations
        return exp_info['ventral_side'] in ['clockwise', 'anticlockwise']

def isBadVentralOrient(skeletons_file):
    with tables.File(skeletons_file, 'r') as fid:
        exp_info_b = fid.get_node('/experiment_info').read()
        exp_info = json.loads(exp_info_b.decode("utf-8"))

        if not exp_info['ventral_side'] in ['clockwise', 'anticlockwise']:
            raise ValueError(
                '"{}" is not a valid value for '
                'ventral side orientation. Only "clockwise" or "anticlockwise" '
                'are accepted values'.format(
                    exp_info['ventral_side']))

        has_skeletons = fid.get_node('/trajectories_data').col('has_skeleton')

        # let's use the first valid skeleton, it seems like a waste to use all the other skeletons.
        # I checked earlier to make sure the have the same orientation.

        valid_ind = np.where(has_skeletons)[0]
        if valid_ind.size == 0:
            return

        cnt_side1 = fid.get_node('/contour_side1')[valid_ind[0], :, :]
        cnt_side2 = fid.get_node('/contour_side2')[valid_ind[0], :, :]
        A_sign = _h_calAreaSignedArray(cnt_side1, cnt_side2)

        # if not (np.all(A_sign > 0) or np.all(A_sign < 0)):
        #    raise ValueError('There is a problem. All the contours should have the same orientation.')

        return (exp_info['ventral_side'] == 'clockwise' and A_sign[0] < 0) or \
            (exp_info['ventral_side'] == 'anticlockwise' and A_sign[0] > 0)


def switchCntSingleWorm(skeletons_file):
        # change contours if they do not match the known orientation
    if isBadVentralOrient(skeletons_file):
        with tables.File(skeletons_file, 'r+') as fid:
            # since here we are changing all the contours, let's just change
            # the name of the datasets
            side1 = fid.get_node('/contour_side1')
            side2 = fid.get_node('/contour_side2')

            side1.rename('contour_side1_bkp')
            side2.rename('contour_side1')
            side1.rename('contour_side2')