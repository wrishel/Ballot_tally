
"""Identify images with a page number that is suspicious wrt the image number.

   Input is the scratch file named below."""

with open(r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2020.2\scratches\scratch.txt') as inf:
    data = inf.readlines()
    l = list()
    for x in data:
        img, page = x.split()
        if int(img) % 4 + 1 != int(page):
            print((img, page))
