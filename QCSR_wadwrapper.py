#!/usr/bin/env python
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This code is an analysis module for WAD-QC 2.0: a server for automated 
# analysis of medical images for quality control.
#
# The WAD-QC Software can be found on 
# https://bitbucket.org/MedPhysNL/wadqc/wiki/Home
# 
#
# Changelog:
#   20211116: first version based on QCCT_wadwrapper.py vs 20201002
# ./QCSR_wadwrapper.py -c Config/ct_philips_umcu_series_mx8000idt.json -d TestSet/StudyMx8000IDT -r results_mx8000idt.json

__version__ = '20211116'
__author__ = 'aschilham'

import os
# this will fail unless wad_qc is already installed
from wad_qc.module import pyWADinput
from wad_qc.modulelibs import wadwrapper_lib
import QCSR_lib

try:
    import pydicom as dicom
except ImportError:
    import dicom

def logTag():
    return "[QCSR_wadwrapper] "

##### Real functions
def qc_series(data, results, action, override={}):
    """
    QCCT_UMCU Checks: extension of Philips QuickIQ (also for older scanners without that option), for both Head and Body if provided
      Uniformity
      HU values
      Noise
      Linearity 

    Workflow:
        1. Read SR
        2. Extract values
        3. Build json output
    """
    try:
        params = action['params']
    except KeyError:
        params = {}

    # overrides from test scripts
    for k,v in override.items():
        params[k] = v

    qclib = QCSR_lib.DCMSR_IO()
    qclib.read(data.series_filelist[0][0])
    content = qclib.get_content()

    # build results json
    res_list = ['scaninfo', 'other']
    if params.get('section', "Summary") == "Summary":
        res_list.append("summary")
    if params.get('section', "History") == "History":
        res_list.append("history")
        
    for sect in res_list:
        for vals in content[sect]:
            if vals['type'] in ['int', 'float']: 
                results.addFloat(vals['name'], float(vals['value']))
            elif vals['type'] in ['string']: 
                v = str(vals['value'])
                results.addString(vals['name'], v[:min(len(v),100)])
            else:
                raise ValueError("Result '{}' has unknown result type '{}'".format(vals['name'], vals['type']) )



def acqdatetime_series(data, results, action):
    """
    Read acqdatetime from dicomheaders and write to IQC database

    Workflow:
        1. Read only headers
    """
    try:
        params = action['params']
    except KeyError:
        params = {}

    ## 1. read only headers
    dcmInfile = dicom.read_file(data.series_filelist[0][0], stop_before_pixels=True)

    dt = wadwrapper_lib.acqdatetime_series(dcmInfile)

    results.addDateTime('AcquisitionDateTime', dt) 

def main(override={}):
    """
    override from testing scripts
    """
    data, results, config = pyWADinput()

    # read runtime parameters for module
    for name,action in config['actions'].items():
        if name == 'acqdatetime':
            acqdatetime_series(data, results, action)

        elif name == 'qc_series':
            qc_series(data, results, action, override)

    #results.limits["minlowhighmax"]["mydynamicresult"] = [1,2,3,4]

    results.write()
    
if __name__ == "__main__":
    # main in separate function to be called by sr_tester
    main()
