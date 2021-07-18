#!/usr/bin/env python3

"""Process scanned files to identify the precinct and page number.

   This a main program can be run in multiple parallel process.

   Review the database for rows in Images that have not yet had this info filled in.
   Decode the barcodes and translate the numbers into precinct IDs
   Write the information back to the database."""

# possible huge time saving in https://stackoverflow.com/questions/48281086/extracting-a-region-of-interest-from-an-image-file-without-reading-the-entire-im/48376269#48376269
# however, maybe not because we also need to decode the barcode in the lower left corner
# Todo: clear orphaned rows before this is started

import dbase
import datetime
from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
from HARTgetBallotType import HARTgetBallotType, b2str, page_num
import logging
import mylogging
import os
import signal
import sys
import time
import inter_proc_signal

GLB = GLB_globs.GLB_globs()
semaphore = inter_proc_signal.win_ip_signal(GLB.daemon_semaphore_path)
semaphore.clear()
mylogging.basicConfig(filename=GLB.path_to_log, level=logging.DEBUG, filemode='a')
logging.info(sys.argv)

TESTING = True
pid = os.getpid()
# global stopflag
# stopflag= False
#
# def intHandler(x, y):           # doesn't work on Windows
#     print(pid, 'interruption', x, y)
#     global stopflag
#     stopflag = True
#
# signal.signal(signal.SIGINT, intHandler)

PATH_TO_IMAGES = GLB.path_to_images
tot_processed = 0
start_time = datetime.datetime.now()

if TESTING:
    db = dbase.ETPdb()
    db.connect('testing')

else:
    db = dbase.ETPdb()
    db.connect('production')

precinct_lookup = dict()
for row in db.get_barcodes():
    assert row.precinct_id not in precinct_lookup
    precinct_lookup[row.precinct_id] = row.precinct_name

with HARTgetBallotType(GLB.dpi) as hgbt:
    tries = 0
    while True:
        # get a list of rows to fix
        #
        # todo: keep a black list of image numbers that have failed for the duration
        #       of the run. Exclude those in get_images_for_barcode
        rows_to_fix = db.get_images_for_barcode(pid, 20)      # batch of N
        fixes = []  # tuples of (precinct, page_number, image_number)
        unfixables = [] # list of image_number
        last_img_num = None
        first_img_num = None

        for row in rows_to_fix:
            image_num = row.image_number
            if first_img_num is None:
                first_img_num = image_num

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
                barcode_upper, barcode_lower = hgbt.getBallotBarcodes(pth)
            except IOError as e:
                logging.exception(pth)
                print(f'{e}', sys.stderr)
                barcode_upper, barcode_lower = None, None
                precinct = party_id = 'MISSNG'
                pagenum = 'MSG'

            except Exception as e:
                logging.exception(pth)
                continue

            else:
                if barcode_upper is None:
                    precinct = 'UNREC'
                else:
                    precinct = precinct_lookup.get(
                        int(GLB.extract_precinct(barcode_upper)),None)
                    if precinct is None:
                        precinct = 'UNREC'

                pgnum = 'UNK' if barcode_lower is None else page_num(barcode_lower)

            # fixes.append((precinct, pagenum, party_id, barcodes[0], barcodes[1], image_num))
            fixes.append((precinct, barcode_upper, barcode_lower, pgnum, image_num))

        tot_processed += len(fixes)
        if len(fixes) != 0:
            logging.info(f'precessed {tot_processed}; '
                         f'img nums: {first_img_num}-{last_img_num}')
            db.update_unscanned_images(fixes)
            print(pid, 'processed', tot_processed, last_img_num,
                  datetime.datetime.now() - start_time)

        if semaphore.exists():
            t = datetime.datetime.now() - start_time
            f = f'===> pid {pid} exiting after interrupt, ' \
                f'total processed={tot_processed}, time={t}'
            print(f)
            logging.info(f)
            exit(0)

        # t = .20 starves the UI in fast simulation. Probably not in operation
        # if len(fixes) != 0:
        #     t = 1
        #     print(f'{pid} dozing')
        # else:
        t = .10
        time.sleep(t) # give other processes a chance

