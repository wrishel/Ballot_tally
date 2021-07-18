

# This is complicated so it might be worth reading the documentation.
#
# We will create SQL with a WHERE clause the selects a traunch of
# choices with precinct/contest level data appended.
#
# The selected choices will be fed to the run method of the rpt object
# that is createat main. That method will actually execute the
# enter process. It will:
#
# - aggregate choices within an image to a contest block (see
#   the contest_block class)
#
# - perhaps adjust that data according to the adjust_block
#   method below
#
# - make decisions on what to tally for the end of the report
#
# - decide whether to include the image for the particular contest
#   instance at hand
#
# - emit the image and text data for a contest to the image log
#
# - emit a final block to the image log with the tallies.
#
# The SQL and WHERE clause can be found at ----  MIAN ---- at the
# bottom.
#




from collections import Counter
from collections.abc import Iterable
import cv2
import dbase
import ETP_util
from image_logger import ImageLogger
import image_processing_lib
from marks_from_scores import marks_from_scores, suspicion
import GLB_globs
import mysql.connector as connector
from numbers import Number
import os
from pathlib import Path
import random
import sys
from util import divz

GLB = GLB_globs.GLB_globs()

CONTEST_LEFT_EDGE_FROM_CX = 135
CONTEST_COLUMN_WIDTH = 1130
CONTEST_BOTTOM_EDGE_BELOW_CY = 300
CONTEST_HEIGHT_HEADERS = 320
SHOW_MARK_OFFSET_Y = 30
SHOW_MARK_OFFSET_X = 300
SHOW_MARK_BY_PCT_OFFSET_X = SHOW_MARK_OFFSET_X + 60
SHOW_SCORE_OFFSET_X = SHOW_MARK_BY_PCT_OFFSET_X + 60
CONTEST_COMMENTS_OFFSET_y = 30              # offset from lowest choice entry
RED = (0, 0, 255)
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
DARK_BLUE = (191, 0, 0)

db = dbase.ETPdb()
db.connect('testing')

def dbgimg(img, name):
    """Save an image for use while debugging."""

    cv2.imwrite(rf'C:\Users\15104\Downloads\{name}.jpg', img)


class contest_block(object):
    def __init__(self, row):
        self.image_number = row.image_number
        self.contest_name = row.contest_name
        self.precinct = row.precinct
        self.votes_allowed = row.votes_allowed
        self.overvoted = row.overvoted
        self.overvoted_by_pcnt = row.overvoted_by_pct
        self.undervoted = row.undervoted
        self.undervoted_by_pcnt = row.undervoted_by_pct
        self.validcount = row.validcount
        self.suspicion_by_pct = row.suspicion_by_pct
        self.choices = []
        self.sumscores = 0
        self.count = 0

    def different_row(self, other):
        return self.image_number != other.image_number or \
               self.contest_name != other.contest_name

    def has_marked_write_in(self):
        for choice in self.choices:
            if 'write in' in choice['choice_name'].lower() \
                    and choice['marked_by_pct']:
                return True

        return False

    def reportable(self, alt_rules)->bool:
        """Return true if this contest should be included in the report."""

        # alternative rule sets
        if alt_rules == 'all':
            return True

        elif alt_rules == 'for_examination':
            # what would need to be examined manually

            if self.suspicion_by_pct: return True
            if self.overvoted_by_pcnt: return True
            if self.has_marked_write_in(): return True

            for choice in self.choices:
                if 'write in' in choice['choice_name'].lower() \
                        and choice['marked']:
                    return True

        elif alt_rules == 'comparing old to new':

            if suspicion.TOT_PCNT_LOW & self.suspicion_by_pct:
                return False
            for choice in self.choices:
                if choice['marked'] != choice['marked_by_pct']:
                    return True
            # if not self.validcount and \
            #        self.sumscores > len(self.choices):
            #     return True
            if self.undervoted_by_pcnt and self.undervoted == 0:
                return True
            if \
                    self.overvoted or \
                            self.suspicion_by_pct:
                return True

        return False

class report(object):
    """Create a report based on a sorted series of tuples generating output
       on "breaks" in the sorted data."""

    def __init__(self, log_name, datastream, reporting_method,
                 adjust_block=None):
        """Initialize and process the whole report."""

        imglp = fr'{GLB.path_to_logs}{log_name}.html'
        self.image_logger = ImageLogger(imglp)
        self.cur_img_num = None
        self.cur_img = None
        self.emitted_count = 0
        self.examined_contests_count = 0
        self.accumulators = Counter()
        self.adjust_block = adjust_block
        self.reporting_method = reporting_method
        self.datastream = datastream

    def run(self)->int:
        """Execute the report"""

        first_time = True
        for row in self.datastream:
            if first_time:
                current_contblk = contest_block(row)
                first_time = False

            newcb = contest_block(row)
            if current_contblk.different_row(newcb):
                self.emit_block(current_contblk)
                current_contblk = newcb
                if self.emitted_count % 25 == 0:
                    print(self.emitted_count)

            self.process_row(row, current_contblk)

        self.emit_block(current_contblk)

        self.finish()
        return self.emitted_count

    def process_row(self, row, contest):
        """Add another choice to an existinc contest block"""


        x = int((row.location_ulcx + row.location_lrcx) / 2)
        y = int((row.location_ulcy + row.location_lrcy) / 2)
        # maxy = row.location_lrcy
        contest.choices.append({'y': y, 'x': x,
                        'choice_name': row.choice_name,
                        'score': row.score,
                        'marked': row.marked,
                        'marked_by_pct': row.marked_by_pct})
        contest.sumscores += row.score

    def emit_block(self, contblk:contest_block):
        """Emit the block if there is difference worth noting."""

        if self.adjust_block:
            self.adjust_block(contblk)
        self.examined_contests_count += 1

        # accumulate counts for all contests, whether or not
        # emitted

        for ix in range(len(contblk.choices)):
            ch = contblk.choices[ix]

        sus = contblk.suspicion_by_pct
        if contblk.has_marked_write_in():
            self.accumulators["Write-in"] += 1

        for bit, meaning in ( \
                  (suspicion.TOT_PCNT_LOW,
                   f"Suspicion: Total percentage low"),
                  (suspicion.IND_SCORE_LOW,
                   f"Suspicion: Low individual score in percents")
             ):
            if sus and sus & bit:
                self.accumulators[meaning] += 1

        if contblk.overvoted_by_pcnt:
            self.accumulators['overvoted'] += 1

        if contblk.undervoted_by_pcnt:
            if contblk.undervoted_by_pcnt < contblk.votes_allowed:
                self.accumulators['undervoted non-empty'] += 1

        if contblk.reportable(self.reporting_method) is False:
            sys.stderr.write('../try')
            sys.stderr.flush()
            return

        self.emitted_count += 1
        # sys.stderr.write('*')
        # sys.stderr.flush()
        # only retrieve a new image when we need one
        if self.cur_img_num != contblk.image_number:
            imgp = ETP_util.fullpath_to_image(contblk.image_number)
            self.cur_img = cv2.imread(imgp)

        # annotate the contest in the image
        for choice in contblk.choices:
            if choice['marked_by_pct'] > 0:
                cv2.putText(self.cur_img, "X",
                            (choice['x'] + SHOW_MARK_BY_PCT_OFFSET_X,
                             choice['y'] + SHOW_MARK_OFFSET_Y),
                            cv2.FONT_HERSHEY_SIMPLEX, 2.8, GREEN, 18)

            cv2.putText(self.cur_img,
                        f' {choice["score"]:6.1f}  '
                        f'{divz(choice["score"], contblk.sumscores):6.1%}',
                        (choice['x'] + SHOW_SCORE_OFFSET_X,
                         choice['y'] + SHOW_MARK_OFFSET_Y),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.8, BLUE, 6)

        # create the message in the text column of the report

        msg = f'Precinct {contblk.precinct}\nContest {contblk.contest_name}\n'
        tab = '&nbsp;' * 4
        msg += 'Notes:\n'
        if contblk.has_marked_write_in():
            msg += f'{tab}WRITE IN\n'

        for bit, meaning in ( \
                  (suspicion.TOT_PCNT_LOW,
                   f"SUSPICION: Total percentage low"),
                  (suspicion.IND_SCORE_LOW,
                   f"SUSPICION: Low individual score in percents")
             ):
            if sus and sus & bit:
                msg += f"{tab}{meaning}\n"

        if contblk.overvoted_by_pcnt:
            msg += f"{tab}OVERVOTED" + os.linesep

        if contblk.undervoted_by_pcnt:
            msg += f"{tab}UNDERVOTED BY {contblk.undervoted_by_pcnt}"

        # excerpt part of the image for the left column of the log
        sorted_choices = sorted(contblk.choices, key=lambda d: d['y'])
        left_x = int(sorted_choices[0]['x']) - CONTEST_LEFT_EDGE_FROM_CX
        top_y = int(sorted_choices[0]['y']) - CONTEST_HEIGHT_HEADERS
        right_x = left_x + CONTEST_COLUMN_WIDTH
        bottom_y = int(sorted_choices[-1]['y']) + CONTEST_BOTTOM_EDGE_BELOW_CY
        guessed_img = self.cur_img[top_y:bottom_y, left_x:right_x, :]
        self.image_logger.log_image(guessed_img, 25, None, Path(imgp), msg)

    def finish(self):
        """Emit a closing block."""

        msg = 'Summary of counts.\n'
        msg = f'Examined {self.examined_contests_count} contests ' \
              f'and included {self.emitted_count} of them.\n'
        for k in sorted(self.accumulators):
            msg += f'    {k}: {self.accumulators[k]}\n'

        print('\n' + msg)
        pix1 = fr'{GLB.proj_base}\res\SUMMARY.jpg'
        img = cv2.imread(pix1)
        self.image_logger.log_image(img, 100, None, Path(pix1), msg)

class datastream():
    """Supply data to the report object"""

    def __init__(self, sql):
        test_dbconfig = {
            "user":     "tevs",
            "password": "tevs",
            "database": "HETPtesting"
        }
        self.cnx = connector.connect(**test_dbconfig)
        self.cursor = self.cnx.cursor(named_tuple=True)
        self.cursor.execute(sql)

    def __iter__(self):
        return self

    def __next__(self):
        res = self.cursor.fetchone()
        if res:
            return res
        raise StopIteration

#  ------------------------------  MAIN ------------------------------

random.seed('hetp')

with open(r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2021.1\scratches\scratch.txt') as inf:
    to_log = []
    for l in inf.readlines():
        imgnum, contest = l.strip().split('\t')
        to_log.append(f'"{imgnum}|{contest}"')

    print(len(to_log))
    SAMPLE_SIZE = 575
    if len(to_log) <= SAMPLE_SIZE:
        sample = to_log
    else:
        sample = random.sample(to_log, 250)

    print(f'Sample size: {len(sample)/len(to_log):.1%}')

    work_list = f'({",".join(sample)})'

sql = f"""select
               ico.image_number      AS image_number,
               img.precinct          AS precinct,
               ico.contest_name      AS contest_name,
               ich.choice_name       AS choice_name,
               ico.overvoted         AS overvoted,
               ico.validcount        AS validcount,
               ico.votes_allowed     AS votes_allowed,
               ich.marked            AS marked,
               ico.suspicion_by_pct  AS suspicion_by_pct,
            #  ico.underthreshold    AS underthreshold,
               ico.undervoted        AS undervoted,
               ich.marked_by_pct     AS marked_by_pct,
               ico.overvoted_by_pct  AS overvoted_by_pct,
               ico.undervoted_by_pct AS undervoted_by_pct,
               ich.score             AS score,
               # ico.ratio_by_pct      AS ratio_by_pct,
               ich.location_ulcx     AS location_ulcx,
               ich.location_ulcy     AS location_ulcy,
               ich.location_lrcx     AS location_lrcx,
               ich.location_lrcy     AS location_lrcy

            from ((img_contest ico 
            join img_choice ich 
                 on  (((ico.image_number = ich.image_number) 
                   and (ico.sub_id = ich.img_contest_subid))))
            join images img on (ico.image_number = img.image_number))
            where concat(ico.image_number, '|', ico.contest_name) 
                  in {work_list}
            """

data = datastream(sql)
print('data stream created')
def adjust_block(block:contest_block):
    """Adjust the block returned from the database for this report."""

    # use the latest version of the marking algorithm
    score_list = [c['score'] for c in block.choices]
    result = marks_from_scores(score_list, block.votes_allowed)
    block.suspicion_by_pct = result['suspicions']
    block.overvoted_by_pcnt = result['overvoted']
    block.undervoted_by_pcnt = result['num_undervoted']
    for i in range(len(score_list)):
        block.choices[i]['marked_by_pct'] = int(result['marked'][i])

rpt = report('contest_to_examine', data,
             reporting_method='all',
             adjust_block=adjust_block)

print(rpt.run(), 'items in log')




