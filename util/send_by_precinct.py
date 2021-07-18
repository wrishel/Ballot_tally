"""Copy a randomly selected set of images from the main
   directory to a flat output directory."""


from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import dbase
import os
import random

import shutil

db = dbase.ETPdb()
db.connect('testing')


GLB = GLB_globs.GLB_globs()
sql = '''select precinct, image_number from images
         order by precinct, image_number'''

rows = db.retrieve_many(sql)

input_dir = GLB.path_to_images
output_dir = r'E:\2020_Nov'
last_dir = None
totnum = len(rows)
cnt = 0
newcnt = 0
for row in rows:
    cnt += 1
    dest_dir = fr'{output_dir}\{row.precinct}'
    fname = f'{row.image_number:06d}'

    if cnt % 1000 == 1 or last_dir != row.precinct:
        print(row, f'{cnt}/{totnum}, newcnt: {newcnt}')
        last_dir = row.precinct

    if not os.path.exists(fr'{dest_dir}\{fname}.jpg'):
        newcnt += 1
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(fullpath_to_image(row.image_number), dest_dir)

