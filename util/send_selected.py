"""Copy a randomly selected set of images from the main
   directory to a flat output directory."""


from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import dbase
import os
from pathlib import Path
import random

import shutil
GLB = GLB_globs.GLB_globs()
random.seed(2004)

files_to_send = r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2021.1\scratches\scratch1.txt'
with open(files_to_send, 'r') as inf:
   sendfiles = [int(x) for x in inf.readlines()]

# sendfiles = random.sample(sendfiles,7500)
# with open(r'C:\Users\15104\Downloads\image_info.csv','w') as ouf:
#     for fn in sendfiles:
#         print(fn, file=ouf)

input_dir = GLB.path_to_images
output_dir = r'C:\Users\15104\Dropbox\david\old_not_new'
Path(output_dir).mkdir(parents=True, exist_ok=True)

for img_num in sorted(sendfiles):
    shutil.copy2(fullpath_to_image(img_num), output_dir)

