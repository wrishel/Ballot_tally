"""Copy a randomly selected set of images from the main
   directory to a flat output directory."""

"""Consecutive runs of this program will not resend files that
   were previously sent. 
"""

from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import dbase
import random
import os
import random
import shutil
GLB = GLB_globs.GLB_globs()

# random.seed(999)
# random.seed(90645)
random.seed(101744)

# select all combos
# for each combo
#    select N random example image numbers



already_sent_file = f'{os.path.dirname(os.path.abspath(__file__))}\\random_images_sent.txt'
with open(already_sent_file, 'r') as inf:
   already_sent = set(int(x) for x in inf.readlines())

db = dbase.ETPdb()
db.connect('testing')

input_dir = GLB.path_to_images
# output_dir = r'C:\Users\15104\Dropbox\david\random'
# output_dir = r'C:\Users\15104\Dropbox\david\random2'
output_dir = r'C:\Users\15104\Dropbox\david\random3'


imgs = set()
sql = \
   f"""select distinct precinct, page_number from images"""
ret1 = db.retrieve(sql)
for precinct, page in ret1:
    sql = f"""select image_number from images
              where precinct = '{precinct}'
                and page_number = {page}"""
    ret = db.retrieve(sql)
    for row in random.sample(ret, min(8, len(ret))):
        imgs.add(row[0])

print (len(imgs))
# images = set([x[0] for x in ret]) - already_sent

for img_num in sorted(imgs):
    shutil.copy2(fullpath_to_image((img_num)), output_dir)

with open(already_sent_file, 'a') as of:
    of.writelines((f'{x:06d}\n' for x in sorted(imgs)))





