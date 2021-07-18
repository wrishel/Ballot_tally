"""Front end to logging.basicConfig() that sets project defaults.

   This presets the libary logging objects to the defaults defined here.

   After using this an app should log events using the regular logging
   API. There is no specialized object created here.

   See test_myLogging/test_myLogging.py for a usage example.
"""

import logging
import os

def get_log_file_path(logname):
    return logging.getLogger(logname).manager.root.handlers[0].baseFilename


def basicConfig(**k):
    """Overrides or provide defaults for logging.basicConfig: log file names, format.


       If the caller does not provide a filename in the kw args, the
       default is name.log. That is, the log name is used in the log file name."""

    # if 'name' not in k:
    #     raise ValueError('Logging must include a log name in "name="')

    # if 'filename' not in k:
    #     k['filename'] = os.path.join(os.getcwd(), k['name'] + '.log')

    # Provide some default arguments.
    #
    for argname, argval in [
        ('format', '%(asctime)s\t%(levelname)s\t%(process)d\t'+
                   '%(module)s\t%(funcName)s(%(lineno)s)\t%(message)s'),
        # ('format', '%(asctime)s\t%(levelname)s\t'+
        #            '%(funcName)s(%(lineno)s)\t%(message)s'),
        ('level', 'INFO'),
        ('filemode', 'w'),
    ]:
        if argname not in k:
            k[argname] = argval
    logging.basicConfig(**k)

if __name__ == '__main__':
    fname = os.path.splitext(os.path.basename(__file__)[0])
    fbase = os.path.split[0]
    log_file_name = os.path.join(os.getcwd(), os.path.basename(__file__), '.log')
    basicConfig(None, name=os.path.basename(__file__),
                          filemode='w')
    logging.info('Sample output to log')