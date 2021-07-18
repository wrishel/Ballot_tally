"""Copy a randomly selected set of images from the main
   directory to a flat output directory."""


from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import dbase
import os
import random

import shutil
GLB = GLB_globs.GLB_globs()


files_to_send = GLB.path_to_scratches /  'scratch.txt'
with open(files_to_send, 'r') as inf:
   sendfiles = set(int(x) for x in inf.readlines())

input_dir = GLB.path_to_images
output_dir = r'D:\2020_Nov\irfan_view'

for img_num in sorted(sendfiles):
    shutil.copy2(fullpath_to_image(img_num), output_dir)

