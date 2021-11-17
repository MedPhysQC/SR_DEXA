# -*- coding: utf-8 -*-
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
"""
Changelog:
    20211116: initial version

"""
__version__ = '20211116'
__author__ = 'aschilham'

## WAD-QC imports: BEGIN
LOCALIMPORT = False
try: 
    # try local folder
    import wadwrapper_lib
    LOCALIMPORT = True
except ImportError:
    # try wad2.0 from system package wad_qc
    from wad_qc.modulelibs import wadwrapper_lib

## WAD-QC imports: END

import pydicom as dicom
import base64
import json

class DummyLogger:
    def _output(self, prefix, msg):
        print("{}: {}".format(prefix, msg))

    def warning(self, msg):
        self._output("[warning] ", msg)

    def info(self, msg):
        self._output("[info] ", msg)

    def error(self, msg):
        self._output("[error] ", msg)

    def debug(self, msg):
        self._output("[debug] ", msg)


class DCMSR_IO():
    def __init__(self, logger=None):
        """
        init
        """
        self.dcm = None
        if logger is None:
            self.logger = DummyLogger()
        else:
            self.logger = logger
        
    def read(self, fname):
        """
        Read DCM SR
        """
        try:
            self.dcm = dicom.read_file(fname)
        except Exception as e:
            msg = "Could not read {} as dicom".format(fname)
            self.logger.error(msg)
            raise ValueError(msg)
                             
        try:
            if not self.dcm.Modality == "SR":
                msg = "Wrong modality type! Wanted SR, got {}".format(self.dcm.modality)
                self.logger.error(msg)
                raise ValueError(msg)
        
        except Exception as e:
            raise

        
    def get_content(self):
        """
        iterate through nested containers and return a json
        """
        def nested_iter(start, content):
            for cont in content.ContentSequence:
                if cont.ValueType == "CONTAINER":
                    startt = list(start)
                    startt.append(cont.ConceptNameCodeSequence[0].CodeMeaning)
                    yield from nested_iter(startt, cont)

                elif cont.ValueType == "TEXT":
                    name = cont.ConceptNameCodeSequence[0].CodeMeaning
                    yield start, {'name': name, 'type': 'string', 'value': cont.TextValue}

                elif cont.ValueType == "NUM":
                    cmv = cont.MeasuredValueSequence
                    units = cmv[0].MeasurementUnitsCodeSequence[0].CodeMeaning
                    value = cmv[0].NumericValue
                    name = cont.ConceptNameCodeSequence[0].CodeMeaning
                    yield start, {'name': name, 'type': 'float', 'value': float(value), 'units': units}
                        
        
        # construct a nested dictionary
        pars = list(nested_iter([], self.dcm))
        params = {}
        for lab, result in pars:
            par = params
            for la in lab:
                if not la in par.keys():
                    par[la] = {}
                par = par[la]
            par[result['name']] = result
        
        params = params.get("BMD Rate of Change Report", params) # strip first level

        # find correct datasets
        datasets = {}
        for key,vals in params.items():
            if key.startswith ("Data Set "):
                datasets[vals['Data Set Title']['value']] = key
        
        # results
        results = {'scaninfo': [], 'summary':[], 'history':[], 'other':[]}

        # results: add top level information
        delkeys = []
        for key, vals in params.items():
            if not vals.get("type", None) is None:
                results['other'].append(vals)
                delkeys.append(key)
        for key in delkeys:
            del params[key]
        
        # results: add scan information
        if "Scan Information" in params:
            for key, vals in params["Scan Information"].items():
                results['scaninfo'].append(vals)
            del params["Scan Information"]

        # results: add Summary and or History
        for d,v in datasets.items():
            # results: add summary data if requested
            if "Summary" in d:
                for key, vals in params[v].items():
                    if vals.get("type", None) is None:
                        for kkey, vvals in vals.items():
                            vvals['name'] = "{}_{}".format(key, vvals['name'])
                            results['summary'].append(vvals)
                    else:
                        results['summary'].append(vals)
                        
                del params[v]

            # results: add history data if requested
            if "History" in d:
                for key, vals in params[v].items():
                    if vals.get("type", None) is None:
                        for kkey, vvals in vals.items():
                            vvals['name'] = "{}_{}".format(key, vvals['name'])
                            results['history'].append(vvals)
                    else:
                        results['history'].append(vals)
                    
                del params[v]
                    
                
        #print(json.dumps(results, indent=4, sort_keys=True))

        return results
    
    def _list_params(self):
        """
        Read the params of the report, and replace object::<name> with the base64 decoded object
        """
        params = {}
        objects = {}
    
        try:
            for cont in self.dcm.ContentSequence:
                if cont.ValueType == "TEXT":# and cont.ConceptNameCodeSequence[0].CodeMeaning == WADQCCODE_PARAMS[0]:
                    self.logger.info("TEXT ContentSequence of type {}".format(cont.ConceptNameCodeSequence[0].CodeMeaning))
                    params[cont.ConceptNameCodeSequence[0].CodeMeaning] = json.loads(cont.TextValue)
                elif cont.ValueType == "CONTAINER":# and cont.ConceptNameCodeSequence[0].CodeMeaning == WADQCCODE_OBJECTS[0]:
                    self.logger.info("CONTAINER ContentSequence of type {}".format(cont.ConceptNameCodeSequence[0].CodeMeaning))
                    objects = {}
                    for con in cont.ContentSequence:
                        if con.ValueType == "TEXT": 
                            objects[con.ConceptNameCodeSequence[0].CodeMeaning] = base64.b64decode(con.TextValue)
                        else:
                            self.logger.info("Nested {} ContentSequence of type {}".format(con.ValueType, con.ConceptNameCodeSequence[0].CodeMeaning))
                    
        except Exception as e:
            msg = "Huh?! ({})".format(str(e))
            self.logger.error(msg)
            raise ValueError(msg)
    
        self.logger.info("Found {} params and {} objects".format(len(params.keys()), len(objects.keys())))
    
        for key,val in params.items():
            if isinstance(val, str) and val.startswith('object::'):
                if not val in objects.keys():   
                    msg = "Could not find object! ({})".format(str(val))
                    self.logger.error(msg)  
                    raise ValueError(msg)
                else:
                    params[key] = objects[val]
        return params
    
    
    
    

if __name__ == "__main__":
    """
    test routine
    """
    obj_def = [
        # type, meaning
        ("Container", "BMD Rate of Change Report"),
    ]
    WADQCCODE_MANUAL_INPUT = ("WAD-QC Manual Input", "WQ-MAN_INP")
    #fname = "/data/Store/DICOM/DEXA/SR_DEXA/dcm/000000/series000/SR000000.dcm"
    #fname = "/data/Store/DICOM/DEXA/SR_DEXA/dcm/000001/series000/SR000000.dcm"
    fname = "/data/Store/DICOM/DEXA/SR_DEXA/dcm/000001/series000/SR000001.dcm"
    #fname = "/data/Store/DICOM/DEXA/SR_DEXA/dcm/000002/series000/SR000000.dcm"

    print("===Start SR test===")
    gen2 = DCMSR_IO()
    gen2.read(fname)
    content = gen2.get_content()
    print(json.dumps(content, indent=4, sort_keys=True))
    
    print("===Finished SR test===")
