# -*- coding: utf-8 -*-
'''
Varstack - A system to create stacked configuration structures
'''

__all__ = [ "Varstack" ]

import logging, re, yaml, os
from pprint import pprint

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

class Varstack:
    def __init__(self, config_filename='/etc/varstack.yaml', config={}):
        self.config_filename = config_filename
        self.valid_combine = ['merge', 'replace', 'remove']
        self.log = logging.getLogger(__name__)
        self.log.addHandler(NullHandler())
        self.data = {}
        self.config = config
        if not 'gnupghome' in self.config:
            if 'HOME' in os.environ:
                self.config['gnupghome'] = os.environ['HOME']+'/.gnupg'
            elif 'PWD' in os.environ:
                self.config['gnupghome'] = os.environ['PWD']+'/.gnupg'
        if not 'datadir' in self.config:
            self.config['datadir'] = os.path.dirname(self.config_filename)+'/stack/'

    """Evaluate a stack of configuration files."""
    def evaluate(self, variables, init_data=None):
        if init_data:
            self.data = init_data
        try:
            cfh = open(self.config_filename, 'r')
        except (OSError, IOError) as e:
            self.log.error('Unable to load configuration file "{0}"'.format(self.config_filename))
            return {}
        self.config.update(yaml.safe_load(cfh))
        cfh.close()
        for path in self.config['stack']:
            fullpaths = self.__substitutePathVariables(self.config['datadir']+'/'+path+'.yaml', variables)
            if not fullpaths:
                continue
            for fullpath in fullpaths:
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
        new_paths = [path]
        tags = self.__extractVarNames(path)
        for tag in tags:
            tagparts = tag.split(':')
            pointer = variables
            for tagpart in tagparts:
                if tagpart not in pointer:
                    self.log.warning('No value for variable "%{{{0}}}" found in path "{1}", skipping'.format(tag, path))
                    return False
                pointer = pointer[tagpart]
            tagvalue = pointer
            multi = []
            for idx, value in enumerate(new_paths):
                if type(tagvalue) is dict:
                    self.log.warning('Value of variable "%{{{0}}}" in path "{1}" is a dictionary which is not allowed, skipping'.format(tag, path))
                    return False
                if type(tagvalue) is list:
                    for entry in tagvalue:
                       multi.append(re.sub('%\{'+tag+'\}', entry, new_paths[idx]))
                else:
                    multi.append(re.sub('%\{'+tag+'\}', tagvalue, new_paths[idx]))
            new_paths = multi
        return new_paths

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
        new = self.__check_enc(new)

        if type(old) != type(new):
            self.log.error('key "{0}": previous type is {1} but new type is {2}.'.format(keyname, type(old).__name__, type(new).__name__))
            return False
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
            elif combine == 'remove':
                self.log.debug('removing dict {0}'.format(keyname))
                return False
            else:
                self.log.debug('merging dict {0}'.format(keyname))
                for key in new:
                    if key not in old:
                        self.log.debug('adding new key "{0}".'.format(keyname+'/'+key))
                        old[key] = new[key]
                    else:
                        res = self.__mergeData(old[key], new[key], combine, keyname+'/'+key)
                        if not res:
                            old.pop(key, None)
                        else:
                            old[key] = res
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

    """Check if value is encrypted"""
    def __check_enc(self, value):
        if type(value) is str and value.find('-----BEGIN PGP MESSAGE-----') == 0:
            self.log.info('found an encrypted string, decrypting it')
            value = self.__decrypt_value(value)
        if type(value) == dict:
            for key in value:
                value[key] = self.__check_enc(value[key])
        if type(value) == list:
            for item in value:
                item = self.__check_enc(item)

        return value


    """Try to dectrypt encrypted_string"""
    def __decrypt_value(self, encrypted_string):
        try:
            import gnupg
            if not os.path.isdir(self.config['gnupghome']):
                raise
            gpg = gnupg.GPG(gnupghome=self.config['gnupghome'])
            gpg.encoding = 'utf-8'

            decrypted_string =  gpg.decrypt(encrypted_string)
            if decrypted_string.data == '':
                raise
            return yaml.safe_load(decrypted_string.data)
        except:
            self.log.error('could not decrypt string. Using its encrypted representation.')
            return encrypted_string
