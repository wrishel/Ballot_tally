#!/usr/bin/env python3

"""Reset the unnormalized precinct and party fields in the Images table
   by reinterpreting the barcode_upper field.
"""


import dbase
import datetime
from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import etpconfig
import os
import sys
import time

TESTING = True
pid = os.getpid()

if __name__ == '__main__':
    GLB = GLB_globs.get()
    config = GLB.config
    PATH_TO_IMAGES = config['Election']['pathtoimages']
    tot_processed = 0
    start_time = datetime.datetime.now()

    if TESTING:
        db = dbase.ETPdb()
        db.connect('testing')

    else:
        db = dbase.ETPdb()
        db.connect('production')

    decode_bc = dict()
    for row in db.get_barcodes():
        assert row.barcode not in decode_bc
        decode_bc[row.barcode] = (row.precinct_id, row.party_id)

    tries = 0
    # get a list of rows to fix
    #
    rows_to_fix = db.get_images_for_barcode(pid, 10)      # batch of 10
    fixes = [] # tuples of (precinct, page_number, image_number)
    last_img_num = None

    for row in rows_to_fix:
        image_num = row.image_number
        last_img_num = image_num
        pth = fullpath_to_image(image_num)
        precinct = None
        party_id = None
        pagenum = None

        #                                       outputs
        # Possible errors               precinct    party   page
        #                               --------    -----   ----
        #  1) no file for this number   MISSING     MISSING MSG
        #  2) upper barcode missing     UNKNOWN     UNKNOWN --
        #  3) lower barcode missing        --          --   UNK
        #  4) upper barcode doesn't     UNREC       UNREC   --
        #     translate

        try:
            barcodes = hgbt.getBallotBarcodes(pth)
        except IOError as e:
            print(f'{e}', sys.stderr)
            barcodes = (None, None)
            precinct = party_id = 'MISSNG'
            pagenum = 'MSG'

        else:
            pagenum = page_num(barcodes[1])     # may be None
            if pagenum is None: pagenum = 'UNK'
            if barcodes[0] is None:
                precinct = party_id = 'UNKNOWN'
            else:
                try:
                    (precinct, party_id) = decode_bc[barcodes[0]]
                except KeyError:
                    # print(image_num, 'Unknown', barcode)
                    precinct = party_id = 'UNREC'

        fixes.append((precinct, pagenum, party_id, barcodes[0], barcodes[1], image_num))
        time.sleep(.15)     # avoid starving the UI

    tot_processed += len(fixes)
    if len(fixes) != 0:
        print(pid, 'processed', tot_processed, last_img_num,
              datetime.datetime.now() - start_time)
    db.update_unscanned_images(fixes)
    if stopflag:
        t = datetime.datetime.now() - start_time
        print(f'===> pid {pid} exiting after interrupt, total processed={tot_processed}, time={t}')
        exit(0)

    # t = .20 starves the UI in fast simulation. Probably not in operation
    # if len(fixes) != 0:
    #     t = 1
    #     print(f'{pid} dozing')
    # else:
    t = .25
    time.sleep(t) # give other processes a chance

