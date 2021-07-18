#!/usr/bin/env python3

"""Process scanned files to count the votes.

   This a main program can be run in multiple parallel process.

   Review the database for rows in Images that have not yet had this info filled in.
   Decode the barcodes and translate the numbers into precinct IDs
   Write the information back to the database."""

import sys
import os
from pathlib import Path
sys.path.append(fr'{os.path.dirname(__file__)}/votes/src15')
sys.path.append(fr'{os.path.dirname(__file__)}/util')
from ballot_scanner import BallotScanner
import datetime
import dbase
from ETP_util import fullpath_to_image, subpath_to_image
import GLB_globs
import json
import logging
from marks_from_scores import marks_from_scores, suspicion
import mylogging
import pandas
import re
# import signal  # doesn't work on windows -- see win_ip_signal
from tabulator import Tabulator
import time
from timer import timer
import inter_proc_signal

GLB = GLB_globs.GLB_globs()
path_to_logfile = GLB.path_to_vote_counting_logs
PATH_TO_IMAGES = GLB.path_to_images

semaphore = inter_proc_signal.win_ip_signal(GLB.daemon_semaphore_path)
semaphore.clear()
mylogging.basicConfig(filename=GLB.path_to_log, level=logging.DEBUG, filemode='a')
logging.info(sys.argv)
pid = os.getpid()
tot_processed = 0
db = dbase.ETPdb()
db.connect('testing')
# db.connect('testing', autocommit=False)  # we will be using transactions here.

tmr = timer()

def process_one_image(scanner, tabulator, image_num, precinct,
                      page_num, data_accumulators):
    """process the votes on an image."""
    start = time.time()
    form_path = Path(fullpath_to_image(image_num))
    # status = scanner.process_one_scanned_form(form_path, data_accumulators)
    tmr.switch_to('ballot_scanner')
    try:
        status = scanner.process_one_scanned_form(form_path, data_accumulators,
                                                  precinct, int(page_num))
    except Exception as e:
        logging.exception(f'Exception for {form_path}; precinct={precinct}; '
                          f'page={page_num}')
        print(f'{e}', sys.stderr)
        status = None  # continue after error


    result = scanner.get_form_result_as_dict()
    elapsed = time.time() - start
    logmsg = "Form: {} Status: {} time: {} secs; success: {}; comment: {}"\
             .format(form_path.name, status, elapsed, result["processing_success"],
                     result["processing_comment"])
    if status:
        logging.info(logmsg)

    else:
        logging.error(f"Form: {form_path.name} failed -- {logmsg}")

    tmr.switch_to()
    return status, result

def prepare_update_for_one_contest(contest, csubid, image_number):
    contest_out = contest.copy()
    choices_out = list()
    contest_out['sub_id'] = csubid
    contest_out['image_number'] = image_number
    if False: # contest_out['found'] is False:
        # although this contest is in the template, it wasn't found
        # on the instance, usually because of a badly marked ballot
        for col in ['suspicion_by_pct', 'undervoted_by_pct', 'overvoted_by_pct',
                     'tot_scores', 'suspicion_by_pct']:
            contest_out[col] = None
        # in this case we add no entries to the choices_out list

    else:
        choices = contest_out.pop('choices')

        for choice in choices:
            choice['image_number'] = image_number
            choice['img_contest_subid'] = csubid
            choices_out.append(choice)

        # alternate method for deciding what's chosen
        xchoices = [x['score'] for x in choices_out]
        xresult = marks_from_scores(xchoices,
                                    contest['votes_allowed'])
        xmarked = xresult['marked']
        for i in range(len(xmarked)):
            choices_out[i]['marked_by_pct'] = \
                xmarked[i]
        contest_out['suspicion_by_pct'] = xresult['suspicions']
        contest_out['undervoted_by_pct'] = xresult['num_undervoted']
        contest_out['overvoted_by_pct'] = xresult['overvoted']
        contest_out['tot_scores'] = xresult['tot_scores']
        contest_out['suspicion_by_pct'] = xresult['suspicions']

    return contest_out, choices_out

def update_db_for_one_image(status, result):
    """Update the database for one image, which consists of
       multiple contest, each of which has multiple choices."""
    contests_to_post = list()
    choices_to_post = list()

    # hopefully temporary hack to deal with processing success = "unknown"
    if result['processing_success'] == 'Unknown':
        result['processing_success'] = False
        logging.error('Changed processing success to False')

    # modify the returned dict for storing in RDB
    imgret = result.copy()  # updates to image table row
    imgret['image_number'] = int(imgret['image_number'])
    imgret["assigned_to_pid"] = None
    imgret.pop('page', None)
    imgret.pop('precinct', None)
    if status:
        imgret['M_matrix'] = json.dumps(imgret['M_matrix'])
        imgret['H_matrix'] = json.dumps(imgret['H_matrix'])
        contests = imgret.pop('contests')

        # create new rows for contest_outest and img_choice
        csubid = 0  # subid + image num = primary key for contest_outest table
        for contest in contests:
            contest_out, choices_out = \
                prepare_update_for_one_contest(contest, csubid,
                                               imgret['image_number'])
            csubid += 1
            contests_to_post.append(contest_out)
            choices_to_post += choices_out

    db_time_start = datetime.datetime.now()
    tmr.push('db_store')
    db.accept_tabulation(imgret, contests_to_post, choices_to_post)
    tmr.pop()

# =======================================  MAIN  =======================================

scanner = BallotScanner(GLB.path_to_vote_counting_metadata_dir,
                    GLB.path_to_vote_counting_template_dir,
                    GLB.path_to_vote_counting_image_log)
tabulator = Tabulator()
# tabulator = None

data_accumulators = {}
path_to_form_dir = GLB.path_to_images
start_time = datetime.datetime.now()
count = 0
debugging_img_nums = None
# debugging_img_nums = [246501, 246502]

# if debugging_img_nums is not defined so far, get it from a scratch file
# if it == None, then this is a production run
try: debugging_img_nums   #  unknown variable name OK here
except NameError:
        imgs_to_process = r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2021.1\scratches\scratch1.txt'
        with open(imgs_to_process, 'r') as inf:
           debugging_img_nums = [int(x) for x in inf.readlines()]

if debugging_img_nums:
    db.fix_orphaned_rows()
    print(f'{len(debugging_img_nums)} debugging images')

while True:
    tmr.push('db_retriev')
    imgs_to_process = db.get_images_for_tabulation(pid, 10,
                                        debugging_img_nums)
    tmr.pop()
    print(pid, [x.image_number for x in imgs_to_process])
    numrows = len(imgs_to_process)
    logging.info(f'retrieved {numrows} images')
    for row in imgs_to_process:
        img_start_time = datetime.datetime.now()
        db_cum_start_time = datetime.datetime.now()
        status, result = process_one_image(scanner, tabulator, row.image_number,
                              row.precinct, row.page_number, data_accumulators)

        update_db_for_one_image(status, result)
        db_time_cum = datetime.datetime.now()-db_cum_start_time
        proctime = (datetime.datetime.now() - img_start_time)\
                    .total_seconds()
        logging.info(f'Processed #{row.image_number}'\
                     f'db seconds:{db_time_cum.total_seconds():.4f}'\
                     f', seconds: {proctime}')

        count += 1

    # create estimate of remaining time
    now = datetime.datetime.now()
    elapsed = (now - start_time).total_seconds()
    rate = elapsed / count
    print(
        f'pid: {pid:5d}, '
        f'count: {count:6d}, '
        f'rate: {rate:.4f}, '
    )
    # for t in tmr.get_times():
    #     print(pid, '%-14s,%12.3f,%8d' % t)

    # to avoid orphaned image rows w/ assigned_to_pid non null
    # currently only take graceful exits when all reserved
    # images have been processed
    if semaphore.exists():
        logging.info('Exit on semaphore.')
        for t in tmr.get_times():
            print(pid, '%-14s,%12.3f,%8d' % t)

        exit(0)

    if debugging_img_nums:
        exit(0)

    if numrows == 0:
        tmr.push('sleeping')
        time.sleep(10)  # reduce log size in idling state
        tmr.pop()

