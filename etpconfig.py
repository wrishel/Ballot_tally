
"""Precess config file for etp."""

# This could be better if the handling of list items used a subscripting interface.
#
# That would require writing __setiten__ and __getitem__ for both sections and individual keys
#
import configparser
import GLB_globs
import sys

class ConfigTypeError(Exception): ...

class Scanconfig(configparser.ConfigParser):
    def __init__(self, path):
        self.GLB_name = 'config'
        super().__init__()
        self.path = path
        self.read(path)
        self.modified = False

    def write(self):
        with open(self.path, 'w') as configfile:
            super().write(configfile)
        self.modified = False

    def set_list(self, key, list):
        text = '|'.join(list)
        self.__setitem__(key, value)
        self.modified = True

    def get_list(self, section, key):
        text = self.get_or_else(section, key, '')
        lst = text.split('|')
        if lst == ['']: lsst = list()
        return lst

    def add_to_unique_list(self, item, section, key):
        list = self.get_list(section, key)
        if item not in list:
            list.append(item)
            self[section][key] = '|'.join(list)

    def get_dict(self, section, key):
        """return a dict where the text in the file looks like key:value, key: value, ...

           spaces at the beginning or end of key or value are ignored. Embedded spaces OK.
           Embedded delimiters not OK."""

        ret = dict()
        text = self[section][key]
        for item in [x.strip() for x in text.split(',')]:
            k, v = item.split(':')
            k, v = k.strip(), v.strip()
            ret[k] = v
        return ret

    def get_or_else(self, section, key, alt):
        """Get the identified value or, if it's not there the value in alt"""

        try:
            retval = self[section][key]
        except KeyError:
            retval = alt
        return retval

    def get_int_or(self, section, key, alt):
        """Return the identified integer or, if it's not there the value in alt.

           For '' return 0. For anything else int() won't process, raise an ConfigTypeError."""

        try:
            retval = self[section][key]
        except KeyError:
            retval = alt

        if retval == '': retval = 0
        try:
            return int(retval)
        except:
            raise ConfigTypeError

    def get_bool_or(self, section, key, alt):
        """Return the identified integer or, if it's not there the value in alt.

           For '' return boolean. For anything else bool() won't process, raise an ConfigTypeError."""

        try:
            retval = self[section][key]
        except KeyError:
            return alt

        if retval == '': return False
        elif retval == 'False': return False
        elif retval == 'No': return False
        elif retval == 'True': return True
        elif retval == 'Yes': return True
        raise ConfigTypeError(f'{retval} not sufficiently boolean.')
        return retval


if __name__ == '__main__':
    import os     # only used for testing, put import here for doc purposes
    import tempfile
    testvalue = '''
        [ballot]
        DoubleSided=False
        Length = 17

        [Election]
        PathToImages =
        SeveralThings = a|b|c
        Adict = A:a,B:b, C : c  ,D: d,  E:   e 
        empty =
        not_an_int = z
        an_int = 42
        # not_even_an_entry
        aTrue = True
        aFalse = False
        
    '''
    checkvalues = (
        ('ballot', 'DoubleSided', 'False'),
        ('ballot', 'Length', '17'),
        ('Election', 'PathToImages', '')
    )

    (_, fpath) = tempfile.mkstemp()       # get temp file
    try:
        with open(fpath, 'w') as testfile:
            testfile.write(testvalue)
        c = Scanconfig(fpath)
        for (sec, item, value) in checkvalues:
            assert c[sec][item] == value

        # check writing changes
        #
        c['Election']['added'] = 'I added this'
        c['ballot']['Length'] = 'I changed this'
        c.write()
        checkvalues1 = (
            ('ballot', 'DoubleSided', 'False'),
            ('ballot', 'Length', 'I changed this'),
            ('Election', 'PathToImages', ''),
            ('Election', 'added', 'I added this')
        )
        c1 = Scanconfig(fpath)
        for (sec, item, value) in checkvalues1:
            assert c1[sec][item] == value

        # unit test dictionary
        #
        adict = c.get_dict("Election", "Adict")
        assert adict == {"A": 'a', "B": 'b', "C": 'c', "D": 'd', "E": 'e'}

    finally:
        os.remove(fpath)

    assert c.get_or_else('Election', 'an_int', 1234) == '42'
    assert c.get_or_else('Election', 'not_even_an_entry', 1234) == 1234
    assert c.get_int_or('Election', 'an_int', 1234) == 42
    assert c.get_int_or('Election', 'not_even_an_entry', 1234) == 1234
    assert c.get_bool_or('Election', 'aTrue', 1234) == True
    assert c.get_bool_or('Election', 'aFalse', 1234) == False
    assert c.get_int_or('Election', 'an_int', 1234) == 42
    assert c.get_int_or('Election', 'not_even_an_entry', 1234) == 1234
    try:
        x = c.get_int_or('Election', 'not_an_int', 1234)
        assert False, 'Should never get here.'

    except ConfigTypeError as e:
       assert isinstance(e, ConfigTypeError)


