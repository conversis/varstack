# -*- coding: utf-8 -*-
'''
Varstack - A system to create stacked configuration structures
'''

__all__ = [ "Varstack" ]

import logging, re, yaml
from pprint import pprint

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

class Varstack:
    def __init__(self, config_filename='/etc/varstack.yaml'):
        self.config_filename = config_filename
        self.valid_combine = ['merge', 'replace']
        self.log = logging.getLogger(__name__)
        self.log.addHandler(NullHandler())
        self.data = {}

    """Evaluate a stack of configuration files."""
    def evaluate(self, variables):
        config = yaml.safe_load(open(self.config_filename))
        for path in config['stack']:
            fullpath = self.__substitutePathVariables(config['datadir']+'/'+path+'.yaml', variables)
            if not fullpath:
                continue
            try:
                fh = open(fullpath, 'r')
            except (OSError, IOError) as e:
                self.log.info('file "{0}" not found, skipping'.format(fullpath))
                continue
            self.log.info('found file "{0}", merging'.format(fullpath))
            self.__loadFile(fh)
            fh.close()
        rawdata = self.data
        return self.__cleanupData(rawdata)

    """Replace variables in a path with their respective values."""
    def __substitutePathVariables(self, path, variables):
        new_path = path
        tags = self.__extractVarNames(path)
        for tag in tags:
            if tag not in variables:
                self.log.warning('Unknown variable "{0}" in path "{1}", skipping'.format(tag, new_path))
                return False
            new_path = re.sub('%\{'+tag+'\}', variables[tag], new_path)
        return new_path

    """Extract a list of variable names present in a string."""
    def __extractVarNames(self, string):
        pattern = re.compile('%\{(.*?)\}')
        tags = []
        for match in pattern.finditer(string):
            tag = match.groups(1)[0]
            if tag not in tags:
                tags.append(tag)
        return tags

    """Remove metadata from configuratin."""
    def __cleanupData(self, data):
        if type(data) == dict:
            newdata = {}
            for key in data:
                if key != '__combine':
                    newdata[key] = self.__cleanupData(data[key])
        elif type(data) == list:
            if type(data[0]) == dict and '__combine' in data[0]:
                newdata = data[1:]
            else:
                newdata = data
        else:
            newdata = data
        return newdata

    """Load a YAML files and merge it into the existing configuration."""
    def __loadFile(self, filehandle):
        data = yaml.safe_load(filehandle)
        self.data = self.__mergeData(self.data, data, 'merge', '<root>')

    """Merge two configuration sets."""
    def __mergeData(self, old, new, combine, keyname):
        if type(old) != type(new):
            self.log.error('key "{0}": previous type is {1} but new type is {2}.'.format(keyname, type(old).__name__, type(new).__name__))
            return False
        #self.log.debug('processing key "{0}"'.format(keyname))
        if type(new) == dict:
            if '__combine' in new:
                if new['__combine'] in self.valid_combine:
                  combine = new['__combine']
                  self.log.debug('switching combination mode to {0} for key {1}'.format(combine, keyname))
                else:
                  self.log.error('unknown combine mode "{0}" for key {1}'.format(new['__combine'], keyname))
            if combine == 'replace':
                self.log.debug('replacing dict {0}'.format(keyname))
                return new
            else:
                self.log.debug('merging dict {0}'.format(keyname))
                for key in new:
                    if key not in old:
                        self.log.debug('adding new key "{0}".'.format(keyname+'/'+key))
                        old[key] = new[key]
                    else:
                        old[key] = self.__mergeData(old[key], new[key], combine, keyname+'/'+key)
                return old
        elif type(new) == list:
            if type(new[0]) == dict and '__combine' in new[0]:
                if new[0]['__combine'] in self.valid_combine:
                    combine = new[0]['__combine']
                    self.log.debug('switching combination mode to {0} for key {1}'.format(combine, keyname))
                else:
                    self.log.error('unknown combine mode "{0}" for key {1}'.format(new[0]['__combine'], keyname))
            if combine == 'replace':
                self.log.debug('replacing list {0}'.format(keyname))
                return new
            else:
                self.log.debug('merging list {0}'.format(keyname))
                return old+new
        else:
            return new
