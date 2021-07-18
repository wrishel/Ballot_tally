"""Utility based on image number, actual files, and barcodes.

   Scans all possible file numbers and logs whether there is an image file with
   that number and if there is corresponding row in the Images table.

   If ADD_TO_IMAGES is true, it adds a row in the Images table where it is not there
   already."""

from ETP_util import fullpath_to_image, subpath_to_image
from HARTgetBallotType import HARTgetBallotType, b2str
import GLB_globs
import etpconfig
import dbase
import datetime
import os
import sys
GLB = GLB_globs.get()

GLB.db.connect('testing')
db = GLB.db
config = GLB.config
MAX_IMG_NUM = 95921

start_time = datetime.datetime.now()

TESTING = True
if TESTING:
    db = dbase.ETPdb()
    db.connect('testing')

else:
    db = dbase.ETPdb()
    db.connect('production')

in_dir = set()
for n in range(MAX_IMG_NUM):
    pth = fullpath_to_image(n)
    isf = os.path.isfile(pth)
    if isf:
        in_dir.add(n)

rows = db.get_image_nums()
already_in_db = set((r.image_number for r in rows))

indbct = 0
indirct = 0
numbers_to_add = set()
with open('/Users/Wes/Downloads/load_db.log', 'w') as log:
    for n in range(MAX_IMG_NUM):
        if n in already_in_db:
            indbct += 1
        else:
           numbers_to_add.add(n)
        if n in in_dir: indirct += 1
        s = (f'{n:6d}\t{n in already_in_db}\t{n in in_dir}\n')
        log.write(s)

print (n, sorted(numbers_to_add))

db.add_image_nums('test', sorted(numbers_to_add))

# in_dir_tree = set()
# all_nums = dict()
# for n in range(67164):
#     all_nums[n] = None
#     pth = fullpath_to_image(n)
#     isf = os.path.isfile(pth)
#     if isf:
#         in_dir_tree.add(n)





# with open('/Users/Wes/Downloads/load_db.log', 'w') as log:
#     for n in range(67164):
#         pth = fullpath_to_image(n)
#         isf = os.path.isfile(pth)
#         alr = n in already_in_db
#         log.write(f'{n}\tisf={isf}\talr={alr}\n')
#         if ADD_TO_IMAGES:
#             if isf and not alr:
#                 db.add_image_nums('test', n)
#         if n % 100 == 0:
#             print(f'\t\t\t{n}')
#
#     print(f'\t\t\t{n}')

