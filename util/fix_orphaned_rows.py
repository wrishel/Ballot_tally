"""Correct image rows that were checked out to an instnace of proceess_barcodes
   but not processed."""

import dbase
import GLB_globs

GLB = GLB_globs.GLB_globs()
db = dbase.ETPdb()
if GLB.TESTING:
    db.connect('testing')
    # db.recreate_images()

else:
    db = dbase.ETPdb()
    db.connect('testing')   # using testing database for production

db.fix_orphaned_rows()
