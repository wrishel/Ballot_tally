"""Test driver: repeatedly adds batches of images to the Image table."""

#   This is running in parallel with multipe copies of process_barcodes.py, but
#   no more than one copy of this process can be running.

import dbase
import GLB_globs
import signal
import time
import datetime

SIGINT = 2
global stopflag
stopflag= False
BATCH_SIZE = 100000
TESTING = True
PAUSE_SECS = 1

def intHandler(x, y):
    global stopflag
    stopflag = True
    print('interrupt')

signal.signal(SIGINT, intHandler)
GLB = GLB_globs.get()
config = GLB.config
PATH_TO_IMAGES = config['Election']['pathtoimages']
MAX_IMAGE_NUM = config['Election']['maximagenum']

if TESTING:
    db = dbase.ETPdb(dbase.test_dbconfig)
    db.recreate_images()

else:
    db = dbase.ETPdb(dbase.dbconfig)

max_image_num = db.get_highest_image_num()[0][0]
if max_image_num:
    next_image_num = int(max_image_num) + 1
else:
    next_image_num = 0
print(next_image_num)

MAX_IMAGE_NUM = next_image_num + 1000  # temp for testing
while next_image_num < MAX_IMAGE_NUM:
    batch = []
    max_batch = next_image_num + BATCH_SIZE - 1
    while next_image_num <= max_batch:
        batch.append((next_image_num, None, None, None, None))
        next_image_num += 1
    if stopflag: break
    db.add_images(batch)
    print('generating',datetime.datetime.now(), next_image_num)
    time.sleep(PAUSE_SECS)          # give the processors a chance

