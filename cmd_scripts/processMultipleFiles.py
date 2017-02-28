# -*- coding: utf-8 -*-
"""
Created on Tue Jun  9 15:12:48 2015

@author: ajaver
"""
from tierpsy.processing.processMultipleFilesFun import processMultipleFilesFun
from tierpsy.processing.ProcessMultipleFilesParser import ProcessMultipleFilesParser

if __name__ == '__main__':
	args = ProcessMultipleFilesParser().parse_args()
	processMultipleFilesFun(**vars(args))
