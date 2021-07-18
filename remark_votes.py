#!/usr/bin/env python3

"""Reprocess votes to decide on marked choices with a different algorithm"""


# Todo: move unit test to the marks_from_scores module
import sys
import os
from pathlib import Path
sys.path.append(fr'{os.path.dirname(__file__)}/votes/src')
import csv
import datetime
import dbase
import GLB_globs
import logging
from marks_from_scores import marks_from_scores, suspicion
import mylogging
import random
# import signal
import timer
import inter_proc_signal

tmr = timer.timer()
GLB = GLB_globs.GLB_globs()
path_to_logfile = GLB.path_to_vote_counting_logs
# path_to_image_logfile = GLB.path_to_vote_counting_image_log
PATH_TO_IMAGES = GLB.path_to_images

semaphore = inter_proc_signal.win_ip_signal(GLB.daemon_semaphore_path)
semaphore.clear()
mylogging.basicConfig(filename=GLB.path_to_log, level=logging.DEBUG, filemode='a')
logging.info(sys.argv)
pid = os.getpid()
tot_processed = 0
db = dbase.ETPdb()
db.connect('testing')  # we will be using transactions here.
# db.connect('testing', autocommit=False)  # we will be using transactions here.

if __name__ == "__main__":
    tmr.push('get rows')
    # imgs_to_process = db.get_choices_for_remarking('marked_by_pct')

    # imgnums = (17296)
    random.seed('hetp')
    # imgnums = sorted(random.sample(range(279420), 27942))
    imgnums = None
    # # imgnums = [100916]
    print('process these images: ', imgnums)

    imgs_to_process = db.get_choices_for_remarking('marked_by_pct', imgnums)
    print('got rows')
    tmr.pop()
    numrows = len(imgs_to_process)
    logging.info(f'retrieved {numrows} images')
    count = 0
    start_time = datetime.datetime.now()
    updates = list()
    for row in imgs_to_process:
        score_list = [float(x) for x in row.scores.split(',')]
        choice_id_list = row.choice_ids.split(',')
        votes_allowed = row.votes_allowed
        res = marks_from_scores(score_list, votes_allowed)
        # significant perf improvement? is there a multi-row update?
        tmr.push('update')
        db.tx_start()
        d = {'overvoted_by_pct':    res['overvoted'],
             'undervoted_by_pct':   res['num_undervoted'],
             'sub_id':              row.cont_subid,
             'image_number':        row.imgnum,
             'suspicion_by_pct':    res['suspicions']
        }
        db.update_from_dict('img_contest', ('sub_id', 'image_number'), d)
        v = dict()
        for i in range(len(res['marked'])):
            v['marked_by_pct'] = res['marked'][i]
            v['id'] = choice_id_list[i]
            db.update_from_dict('img_choice', 'id', v)

        db.tx_commit()
        tmr.pop()

        # show progress on the console
        count += 1
        if count % 100 == 1:
            now = datetime.datetime.now()
            elapsed = now - start_time
            rate = elapsed / count
            time_to_go = (numrows - count) * rate
            predicted_time = now + time_to_go
            # can't figure out how to format using time module
            sprectime = str(predicted_time.time())[:5]
            logging.info(f'processed {row.imgnum}')
            print(f'{row.imgnum:06d},  count={count}, % done: {count / numrows:%}' \
                  f' estimated finish: {sprectime}')
            print(tmr.get_times())
