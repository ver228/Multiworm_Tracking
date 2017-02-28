"""
# -*- coding: utf-8 -*-
Created on Thu Dec 17 10:10:35 2015

@author: ajaver
"""
import os
import stat
import xml.etree.ElementTree as ET
import tables
import numpy as np
import csv
from collections import OrderedDict

#%% Read/Store the XML file with the pixel size and fps info


def storeXMLInfo(info_file, masked_image_file):
    with open(info_file, 'r') as fid:
        xml_info = fid.read()

    # if it is empty the xml create a node and exit
    if not xml_info:
        with tables.File(masked_image_file, 'r+') as fid:
            fid.create_array('/', 'xml_info', obj=bytes('', 'utf-8'))
            return

    # read the xml and exit
    root = ET.fromstring(xml_info)

    x_microns = float(root.findall(
        './info/stage/steps/equivalent/microns/x')[0].text)
    y_microns = float(root.findall(
        './info/stage/steps/equivalent/microns/y')[0].text)

    x_pixels = float(root.findall(
        './info/stage/steps/equivalent/pixels/x')[0].text)
    y_pixels = float(root.findall(
        './info/stage/steps/equivalent/pixels/y')[0].text)

    fps = float(root.findall('./info/camera/display/frame/rate')[0].text)

    pixels2microns_x = x_microns / x_pixels
    pixels2microns_y = y_microns / y_pixels

    with tables.File(masked_image_file, 'r+') as fid:
        if '/xml_info' in fid:
            fid.remove_node('/', 'xml_info')
        xml_node = fid.create_array(
            '/',
            'xml_info',
            obj=bytes(
                xml_info,
                'utf-8'))

        masks_node = fid.get_node('/', 'mask')
        masks_node.attrs['fps'] = fps
        masks_node.attrs['pixels2microns_x'] = pixels2microns_x
        masks_node.attrs['pixels2microns_y'] = pixels2microns_y


#%% Read/Store the CSV file with the stage positions
def storeStageData(stage_file, masked_image_file):
    # read motor data from csv
    with open(stage_file) as fid:
        reader = csv.reader(fid)
        data = [line for line in reader]

    # if the csv lines must be larger than one (a header), othewise it is an
    # empty file
    if len(data) <= 1:
        with tables.File(masked_image_file, 'r+') as fid:
            dtype = [('real_time', int), ('stage_time', int),
                     ('stage_x', float), ('stage_y', float)]
            fid.create_table('/', 'stage_log', obj=np.recarray(0, dtype))
            return

    #import pdb
    # pdb.set_trace()

    # filter, check and store the data into a recarray
    header, data = _getHeader(data)
    csv_dict = _data2dict(header, data)
    stage_recarray = _dict2recarray(csv_dict)

    with tables.File(masked_image_file, 'r+') as mask_fid:
        if '/stage_log' in mask_fid:
            mask_fid.remove_node('/', 'stage_log')
        mask_fid.create_table('/', 'stage_log', obj=stage_recarray)

    return csv_dict


def _timestr2sec(timestr):
    time_parts = [float(x) for x in timestr.split(':')]
    return sum((60**ii) * part for ii, part in enumerate(time_parts[::-1]))


def _getHeader(data):
    assert data
    # find header (it is not always the first line)
    for ii, line in enumerate(data):
        if line[0] == 'Real Time':
            break
    assert(ii < len(line) - 1)
    header = data.pop(ii)

    # check that the expected columns are in header
    expected_header = [
        'Real Time',
        'Media Time',
        'Location Type',
        'Centroid/Stage/Speed X (microns[/second])',
        'Centroid/Stage/Speed Y (microns[/second])',
        'MER Min X (microns)',
        'MER Min Y (microns)',
        'MER Width (microns)',
        'MER Height (microns)']
    assert all(col in expected_header for col in header)

    return header, data


def _data2dict(header, data):
    # read the csv data into a dictionary where each field is the data from a
    # column

    assert data
    # filter any possible croped data
    data = [x for x in data if len(x) == len(header)]
    # save data into a dictionary
    csv_dict = {}
    for ii, col_data in enumerate(zip(*data)):
        csv_dict[header[ii]] = col_data

    # Check the data is correct
    # This is not really a necessary assertion this STAGE flag does not seem useuful.
    #assert all(x == 'STAGE' for x in csv_dict['Location Type'])
    del csv_dict['Location Type']

    # delete this columns
    # for col_name in ['MER Min X (microns)', 'MER Min Y (microns)', \
    #'MER Width (microns)', 'MER Height (microns)']:
    #    if col_name in csv_dict
    #assert all(not x for x in csv_dict[col_name])
    #del csv_dict[col_name]
    return csv_dict


def _dict2recarray(csv_dict):
    # convert the csv data into a recarray compatible with pytables
    dat = OrderedDict()

    dat['real_time'] = np.array([bytes(x, 'utf-8')
                                 for x in csv_dict['Real Time']])
    dat['stage_time'] = np.array([_timestr2sec(x)
                                  for x in csv_dict['Media Time']])

    dat['stage_x'] = np.array(
        [float(d) for d in csv_dict['Centroid/Stage/Speed X (microns[/second])']])

    dat['stage_y'] = np.array(
        [float(d) for d in csv_dict['Centroid/Stage/Speed Y (microns[/second])']])

    # convert into recarray (pytables friendly)
    dtype = [(kk, dat[kk].dtype) for kk in dat]
    N = len(dat['stage_x'])
    stage_recarray = np.recarray(N, dtype)
    for kk in dat:
        stage_recarray[kk] = dat[kk]

    return stage_recarray


def getAdditionalFiles(video_file):
    if not (os.path.exists(video_file)):
        raise FileNotFoundError(video_file)
    
    base_name = os.path.splitext(video_file)[0]
    info_file = base_name + '.info.xml'
    stage_file = base_name + '.log.csv'

    info_file = _getValidFile(info_file)
    stage_file = _getValidFile(stage_file)

    return info_file, stage_file

def hasAdditionalFiles(video_file):
    try:
        getAdditionalFiles(video_file)
        return True
    except FileNotFoundError:
        return False

def _insertDirectory(original_file, dir2add):
    dd = os.path.split(original_file)
    return os.path.join(dd[0], dir2add, dd[1])


def _getValidFile(file_name):
    if not os.path.exists(file_name):
        file_name = _insertDirectory(file_name, '.data')
        if not os.path.exists(file_name):
            raise FileNotFoundError(
                'Additional %s file do not exists.' %
                file_name)

    # if (os.stat(file_name).st_size == 0):
    #    raise IOError('%s is empty' % file_name)

    return file_name

#%% main function to store the additional data


def storeAdditionalDataSW(video_file, masked_image_file):
    assert(os.path.exists(video_file))
    assert(os.path.exists(masked_image_file))

    info_file, stage_file = getAdditionalFiles(video_file)

    assert(os.path.exists(video_file))
    assert(os.path.exists(stage_file))

    # store data
    storeXMLInfo(info_file, masked_image_file)
    storeStageData(stage_file, masked_image_file)

    with tables.File(masked_image_file, 'r+') as mask_fid:
        mask_fid.get_node('/mask').attrs['has_finished'] = 2


# DEPRECATED
def walkXML(curr_node, params=[], curr_path=''):
    '''
    Return the structure of a ElementTree into a directory list.
    I am not really using this function but it is cool.
    '''
    curr_path += '/' + curr_node.tag
    if len(curr_node) == 0:
        param.append((curr_path, curr_node.text))
        return params

    for node in curr_node:
        walkXML(node, params, curr_path)
