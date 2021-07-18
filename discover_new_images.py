"""Scan the scanning output directory adding a batch of new image numbers
   to Images.

   This currently only starts looking above the highest image number in the
   database. It won't look for image numbers below the max that might be missing.

   This is running in parallel with multiple copies of process_barcodes.py, but
   no more than one copy of this process can be running."""

import os
print(os.getcwd())
import dbase
from ETP_util import fullpath_to_image
import GLB_globs
import logging
import mylogging
import os
# import signal   # not on Windows
import sys
import time
import inter_proc_signal

GLB = GLB_globs.GLB_globs()
mylogging.basicConfig(filename=GLB.path_to_log,
                      level=logging.DEBUG, filemode='a')
logging.info(sys.argv)

BATCH_SIZE = 1000
INTERBATCH_SHORT_SLEEP = .025
INTERBATCH_LONG_SLEEP = 10

semaphore = inter_proc_signal.win_ip_signal(GLB.daemon_semaphore_path)
semaphore.clear()
# # This is not going to work on Windows.
# SIGINT = 2
# global stopflag
# stopflag = False
# def intHandler(x, y):
#     global stopflag
#     stopflag = True
#     print('interrupt')
#
# signal.signal(SIGINT, intHandler)

# Todo: establish a common logging location with compressed3
# Todo: establish a common config file location with compressed3

def post_images(img_numbers):
    """If the images in img_numbers correspond to existing files,
        for them in the Images table.

       Returns a set of the image numbers added,"""

    batch = list()
    images_to_check = set([imgnum for imgnum in img_numbers])
    # if we find files matching check_set, add them to batch
    for next_image_num in sorted(images_to_check):
        if semaphore.exists(): return None
        if os.path.isfile(fullpath_to_image(next_image_num)):
            batch.append((next_image_num, None, None, None, None))
            images_to_check.remove(next_image_num)

    if len(batch) > 0:
        db.add_images(batch)
        s = (f'batch of {len(batch)} from {batch[0][0]} to {batch[-1][0]}')
        print(s)
        logging.info(s)

    return set([int(row[0]) for row in batch]) # set image numbers added

db = dbase.ETPdb()
if GLB.TESTING:
    db.connect('testing')
    # db.recreate_images()

else:
    db = dbase.ETPdb()
    db.connect('testing')   # using testing database for production

ret = db.get_all_image_numbers()
known_images = set((row[0] for row in ret))
high_water_mark = max(known_images)

while True:
    # get missing images numbers < high water mark
    missing_images = set(range(high_water_mark)) - known_images
    m = f'{len(known_images)} previous images, max is {high_water_mark},' \
        f'{len(missing_images)} missing images'
    print(m)
    logging.info(m)
    semaphore.exit_if_exists()
    added = post_images(missing_images)
    known_images |= added
    max_added = -1 if len(added) == 0 else max(added)
    high_water_mark = max(high_water_mark, max_added)

    new_batch = set(range(high_water_mark + 1,
                    high_water_mark + 1 + BATCH_SIZE))

    semaphore.exit_if_exists()
    added_new = post_images(new_batch)
    known_images |= added_new
    max_added = -1 if len(added_new) == 0 else max(added_new)
    high_water_mark = max(high_water_mark, max_added)

    if len(added_new) + len(added) > 0:
        interbatch_sleep = INTERBATCH_SHORT_SLEEP

    else:
        interbatch_sleep = INTERBATCH_LONG_SLEEP  # nothing found last time

    time.sleep(interbatch_sleep)          # give the processors a chance