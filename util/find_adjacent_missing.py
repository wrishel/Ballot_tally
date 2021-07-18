"""Find image numbers that are missing even though their adjacent numbers
   are present.
"""

import GLB_globs
import pprint

GLB = GLB_globs.GLB_globs()
import util

with util.open_scratch('scratch.txt') as inf:
    img_nums = [int(x) for x in inf.readlines()]

assert len(img_nums) > 4, "Too few items"

diffs = [img_nums[i+1] - img_nums[i] for i in range((len(img_nums)-1))]
x = [(i, img_nums[i], img_nums[i+1], diffs[i])
       for i in range(len(diffs)) if  diffs[i] > 100]

for z in x:
    print (z)

0
# pp = pprint.PrettyPrinter()
# pp.pprint(img_nums)