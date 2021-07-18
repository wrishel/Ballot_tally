"""Example stacked widgets as objects with designer"""


# CURRENTLY HACKED ONLY TO RUN precess_vites.py
#
#   Todo: use command line parameters to select what runs
#

import datetime
import dbase
import GLB_globs
import logging
import mylogging
import os
import shutil
import subprocess
import sys
import time

SLEEP_SECONDS = 10  # wait time before checking if subprocesses still running
print(datetime.datetime.now().isoformat(' '))   # for debugging
GLB = GLB_globs.GLB_globs()
db = dbase.ETPdb()
if GLB.TESTING:
    db.connect('testing')
    # db.recreate_images()

else:
    # db = dbase.ETPdb()
    db.connect('testing')   # using testing database for production

db.fix_orphaned_rows()

# C:\Users\15104\Dropbox\Programming\ElectionTransparency\ballot_tally\discover_new_images.py

mylogging.basicConfig(filename=GLB.path_to_log,
                      level=logging.DEBUG, filemode='a')
logging.info(sys.argv)

# start parallel processes
#
ext_processes = []
def start_process(prog_name, numprocesses):
    global ext_processes
    for i in range(numprocesses):
        f = f'{os.getcwd()}\\invok_powershell_venv.ps1'
        print(f)
        # ext_processes.append(subprocess.Popen(['python', f]))
        ext_processes.append(subprocess.Popen(["powershell.exe",
                                               f, prog_name]))
        logging.info(f'started {prog_name}; p={ext_processes[-1].pid}')

# start_process('discover_new_images.py', 1)
# start_process('process_barcodes.py', 1)
start_process('process_votes.py',5)

for p in ext_processes:
    print({f'barcode process: {p.pid}'}, file=sys.stderr)

while True:
    exitflag = True
    for p in ext_processes:
        pp = p.poll()
        if pp is None:          # continue if at least one process is running
            time.sleep(SLEEP_SECONDS)
            exitflag = False

    if exitflag:
        break

# report = db.report_ballots_by_precinct()
# for row in report:


logging.info(f'All daemons closed')