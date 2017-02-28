# -*- coding: utf-8 -*-
"""
Created on Mon Aug  8 17:24:27 2016

@author: ajaver
"""

import os
from functools import partial

from tierpsy.analysis.compress.processVideo import processVideo, isGoodVideo
from tierpsy.analysis.compress_add_data.getAdditionalData import storeAdditionalDataSW, hasAdditionalFiles
from tierpsy.analysis.vid_subsample.createSampleVideo import createSampleVideo, getSubSampleVidName

from tierpsy.analysis.traj_create.getBlobTrajectories import getBlobsTable
from tierpsy.analysis.traj_join.joinBlobsTrajectories import joinBlobsTrajectories

from tierpsy.analysis.ske_init.processTrajectoryData import processTrajectoryData
from tierpsy.analysis.ske_create.getSkeletonsTables import trajectories2Skeletons
from tierpsy.analysis.ske_filt.getFilteredSkels import getFilteredSkels
from tierpsy.analysis.ske_orient.checkHeadOrientation import correctHeadTail

from tierpsy.analysis.blob_feats.getBlobsFeats import getBlobsFeats


from tierpsy.analysis.stage_aligment.alignStageMotion import alignStageMotion, isGoodStageAligment

from tierpsy.analysis.int_profile.getIntensityProfile import getIntensityProfile
from tierpsy.analysis.int_ske_orient.correctHeadTailIntensity import correctHeadTailIntensity

from tierpsy.analysis.feat_create.obtainFeatures import getWormFeaturesFilt, hasManualJoin

from tierpsy.analysis.contour_orient.correctVentralDorsal import switchCntSingleWorm, hasExpCntInfo, isGoodVentralOrient

from tierpsy.analysis.wcon_export.exportWCON import getWCOName, exportWCON

from tierpsy.processing.CheckFinished import CheckFinished
from tierpsy.helper.tracker_param import tracker_param




class AnalysisPoints(object):
    def __init__(self, video_file, masks_dir, results_dir, json_file = ''):
        
        self.getFileNames(video_file, masks_dir, results_dir)
        
        self.video_file = video_file
        self.masks_dir = masks_dir
        self.results_dir = results_dir
        
        self.param = tracker_param(json_file)
        self.is_single_worm = self.param.is_single_worm
        self.use_skel_filter = self.param.use_skel_filter
        
        self.buildPoints()
        self.checker = CheckFinished(output_files = self.getField('output_files'))
        
    def getFileNames(self, video_file, masks_dir, results_dir):
        base_name = video_file.rpartition('.')[0].rpartition(os.sep)[-1]
        results_dir = os.path.abspath(results_dir)
        
        output = {'base_name' : base_name, 'original_video' : video_file}
        output['masked_image'] = os.path.join(masks_dir, base_name + '.hdf5')
    
        ext2add = [
            'trajectories',
            'skeletons',
            'features',
            'feat_manual',
            'intensities']

        for ext in ext2add:
            output[ext] = os.path.join(results_dir, base_name + '_' + ext + '.hdf5')
        
        output['subsample'] = getSubSampleVidName(output['masked_image'])
        output['wcon'] = getWCOName(output['features'])

        self.file_names =  output
        self.file2dir_dict = {fname:dname for dname, fname in map(os.path.split, self.file_names.values())}
    
    def getField(self, key, points2get = None):
        if points2get is None:
            points2get = self.checkpoints

        #return None if the field is not in point
        return {x : self.checkpoints[x][key] for x in points2get}
        
    def getArgs(self, point):
        return {x:self.checkpoints[point][x] for x in ['func', 'argkws', 'provenance_file']}
    
    def buildPoints(self):
         #simple alias to reduce the writing
        fn = self.file_names
        param = self.param
        is_single_worm = self.is_single_worm
        use_skel_filter = self.use_skel_filter
        
        #THE FIRST ELEMENT IN OUTPUT_FILES MUST BE AND HDF5 AND WILL BE USED AS FLAG TO 
        #STORE THE PROVENANCE TRACKING
        
        self.checkpoints = {
            'COMPRESS' : {
                'func':processVideo,
                'argkws' : {'video_file': fn['original_video'], 
                            'masked_image_file' : fn['masked_image'],
                            'compress_vid_param' : param.compress_vid_param},
                'input_files' : [fn['original_video']],
                'output_files': [fn['masked_image']],
                'requirements' : [('can_read_video', partial(isGoodVideo, fn['original_video']))],
            },
            'VID_SUBSAMPLE': {
                'func':createSampleVideo,
                'argkws' : {**{'masked_image_file': fn['masked_image'], 'sample_video_name':fn['subsample']}, 
                            **param.subsample_vid_param},
                'input_files' : [fn['masked_image']],
                'output_files': [fn['masked_image'], fn['subsample']],
                'requirements' : ['COMPRESS'],
            },
            'TRAJ_CREATE': {
                'func': getBlobsTable,
                'argkws': {**{'masked_image_file': fn['masked_image'], 'trajectories_file': fn['skeletons']},
                           **param.trajectories_param},
                'input_files' : [fn['masked_image']],
                'output_files': [fn['skeletons']],
                'requirements' : ['COMPRESS'],
            },
            'TRAJ_JOIN': {
                'func': joinBlobsTrajectories,
                'argkws': {**{'trajectories_file': fn['skeletons']},
                            **param.join_traj_param},
                'input_files' : [fn['skeletons']],
                'output_files': [fn['skeletons']],
                'requirements' : ['TRAJ_CREATE'],
            },
            'SKE_INIT': {
                'func': processTrajectoryData,
                'argkws': {**{'skeletons_file': fn['skeletons'], 
                            'masked_image_file':fn['masked_image'],
                            'trajectories_file': fn['skeletons']},
                            **param.init_skel_param},

                'input_files' : [fn['masked_image'], fn['skeletons']],
                'output_files': [fn['skeletons']],
                'requirements' : ['TRAJ_JOIN'],
            },
            'BLOB_FEATS': {
                'func': getBlobsFeats,
                'argkws': {**{'skeletons_file': fn['skeletons'], 
                            'masked_image_file': fn['masked_image']}, 
                            **param.blob_feats_param},
                'input_files' : [fn['skeletons'], fn['masked_image']],
                'output_files': [fn['skeletons']],
                'requirements' : ['SKE_INIT'],
            },
            'SKE_CREATE': {
                'func': trajectories2Skeletons,
                'argkws': {**{'skeletons_file': fn['skeletons'], 
                            'masked_image_file': fn['masked_image']}, 
                            **param.skeletons_param},
                'input_files' : [fn['masked_image']],
                'output_files': [fn['skeletons']],
                'requirements' : ['SKE_INIT'],
            },
            'SKE_ORIENT': {
                'func': correctHeadTail,
                'argkws': {**{'skeletons_file': fn['skeletons']}, **param.head_tail_param},
                'input_files' : [fn['skeletons']],
                'output_files': [fn['skeletons']],
                'requirements' : ['SKE_CREATE'],
            },
            'SKE_FILT': {
                'func': getFilteredSkels,
                'argkws': {**{'skeletons_file': fn['skeletons']}, **param.feat_filt_param},
                'input_files' : [fn['skeletons']],
                'output_files': [fn['skeletons']],
                'requirements' : ['SKE_CREATE'],
            },
            'INT_PROFILE': {
                'func': getIntensityProfile,
                'argkws': {**{'masked_image_file': fn['masked_image'], 'skeletons_file': fn['skeletons'],
                              'intensities_file': fn['intensities']}, **param.int_profile_param},
                'input_files' : [fn['skeletons'],fn['masked_image']],
                'output_files': [fn['intensities']],
                'requirements' : ['SKE_CREATE'],
            },
            'INT_SKE_ORIENT': {
                'func': correctHeadTailIntensity,
                'argkws': {**{'skeletons_file': fn['skeletons'], 'intensities_file': fn['intensities']},
                           **self.param.head_tail_int_param},
                'input_files' : [fn['skeletons'], fn['intensities']],
                'output_files': [fn['skeletons']],
                'requirements' : ['INT_PROFILE'],
            },
            'FEAT_CREATE': {
                'func': getWormFeaturesFilt,
                'argkws': {'skeletons_file': fn['skeletons'], 'features_file': fn['features'],
                           **param.feats_param,
                           'use_skel_filter': self.use_skel_filter, 'use_manual_join': False
                           },
                'input_files' : [fn['skeletons']],
                'output_files': [fn['features']],
                'requirements' : ['SKE_CREATE'],
            },
            'FEAT_MANUAL_CREATE': {
                'func': getWormFeaturesFilt,
                'argkws': {'skeletons_file': fn['skeletons'], 'features_file': fn['feat_manual'],
                           **param.feats_param,
                           'use_skel_filter': self.use_skel_filter, 'use_manual_join': True,
                           },
                'input_files' : [fn['skeletons']],
                'output_files': [fn['feat_manual']],
                'requirements' : ['SKE_CREATE',
                                  ('has_manual_joined_traj', partial(hasManualJoin, fn['skeletons']))],
            },
            'WCON_EXPORT': {
                'func': exportWCON,
                'argkws': {'features_file': fn['features']},
                'input_files' : [fn['features']],
                'output_files': [fn['features'], fn['wcon']],
                'requirements' : ['FEAT_CREATE'],
            },
        }
        
        # points only for single worm
        if is_single_worm:
            self.checkpoints['COMPRESS_ADD_DATA'] = {
                'func':storeAdditionalDataSW,
                'argkws' : {'video_file': fn['original_video'], 'masked_image_file': fn['masked_image']},
                'input_files' : [fn['original_video'], fn['masked_image']],
                'output_files': [fn['masked_image']],
                'requirements' : ['COMPRESS'],
            }
            self.checkpoints['STAGE_ALIGMENT'] = {
                'func': alignStageMotion,
                'argkws': {'masked_image_file': fn['masked_image'], 'skeletons_file': fn['skeletons']},
                'input_files' : [fn['skeletons'], fn['masked_image']],
                'output_files': [fn['skeletons']],
                'requirements' : ['COMPRESS_ADD_DATA', 'SKE_CREATE'],
            }
            
            self.checkpoints['CONTOUR_ORIENT'] = {
                'func': switchCntSingleWorm,
                'argkws': {'skeletons_file': fn['skeletons']},
                'input_files' : [fn['skeletons']],
                'output_files': [fn['skeletons']],
                'requirements' : ['SKE_CREATE',
                                  ('has_contour_info', partial(hasExpCntInfo, fn['skeletons']))],
            }
            #make sure the file has the additional files, even before start compression
            for key in ['COMPRESS', 'COMPRESS_ADD_DATA']:
                self.checkpoints[key]['requirements'] += \
            [('has_additional_files', partial(hasAdditionalFiles, fn['original_video']))]
            
            is_valid_contour = ['CONTOUR_ORIENT', ('is_valid_contour', partial(isGoodVentralOrient, fn['skeletons']))]
            is_valid_alignment = ['STAGE_ALIGMENT', ('is_valid_alignment', partial(isGoodStageAligment, fn['skeletons']))]

            #make sure the stage was aligned correctly
            self.checkpoints['FEAT_CREATE']['requirements'] += is_valid_contour + is_valid_alignment
            
            #the skeleton must be oriented to save a correct map. For this dataset I am expecting to save the profile map.
            self.checkpoints['INT_PROFILE']['requirements'] += is_valid_contour
            
        
        #add provenance file field if it is not explicity added
        for point in self.checkpoints:
            self.checkpoints[point]['provenance_file'] = self.checkpoints[point]['output_files'][0]
            assert self.checkpoints[point]['provenance_file'].endswith('.hdf5')
    
    def hasRequirements(self, point):
        requirements_results = {}

        #check the requirements of a given point
        for requirement in self.checkpoints[point]['requirements']:
            if isinstance(requirement, str):
                #if the requirement is a string, check the requirement with the checker 
                requirements_results[requirement] = self.checker.get(requirement)
            else:
                try:
                    requirements_results[requirement[0]] = requirement[1]()
                except (OSError): 
                    #if there is a problem with the file return back requirement
                    requirements_results[requirement[0]] = False
        
        self.unmet_requirements = [x for x in requirements_results if not requirements_results[x]]
        
        return self.unmet_requirements
    
    def getUnfinishedPoints(self, checkpoints2process):
        return self.checker.getUnfinishedPoints(checkpoints2process)
    
