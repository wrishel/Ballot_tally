"""Utilites including msgBpx. DateTimeEditUpdater, construct_list_text, ETP file paths"""

import GLB_globs
GLB = GLB_globs.GLB_globs()


def subpath_to_image(num):
    """Break up num into a directory/file name combo, without the file type suffix.

       Num should be an integer in numeric or string form, <= 999999."""

    fname = ('00000' + str(num))[-6:]
    dir = fname[:3]
    return dir, fname

def fullpath_to_image(num):
    base = GLB.path_to_images
    dir, fname = subpath_to_image(num)
    return  f"{base}/{dir}/{fname}.jpg"   # todo: polishing: this is ugly and scanner-specific

# GLB.register(subpath_to_image, "subpath_to_image")
# GLB.register(fullpath_to_image, "fullpath_to_image")




