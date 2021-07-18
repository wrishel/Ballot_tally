"""marks_from_scores

   Given a set of scores for the target areas of a contest,
   determine which are marked and whether the pattern is
   "suspicious", i.e., needing manual verification."""

import csv
from enum import IntFlag, auto
from numbers import Number
from util import divz


class suspicion(IntFlag):
    TOT_PCNT_LOW = 1
    IND_SCORE_LOW = 2  # individual non-zero score low


def marks_from_scores(orig_score_list: list[Number],
                      votes_allowed: int,
                      suspicious_score: float = 3.0,
                      min_score: float = 3.0,
                      suspicious_total_pct=.85
                      ) -> dict:
    """Decide which choices are marked in a contest based on the scores,
       which are measures of how thoroughly a target area for a choice
       is filled in.

       The "percentage" of a score is its value divided by the total
       of all the scores.

       min_score          Scores less than this value are treated
                          as zero.

       suspicious_score  If any non-zero score is < this value, the
                         overall result is flagged as
                         suspicion.IND_SCORE_LOW

       suspicious_total_pct  If the scores that are "marked" sum to
                             less than tnis percent of the total the
                             overall result is flagged as
                             suspicion.TOT_PCNT_LOW.

       Returns {
            "marked":           list(bool)   True for areas marked
            "overvoted":        bool  If True, no areas are marked
            "num_votes":        int   Number of votes marked
            "num_undervoted":   int   num_undervoted,
            "suspicions":int    flags from suspicion enum
            }
       """

    # Todo: change type hint for lists to iterables

    suspicions = 0
    sll = len(orig_score_list)
    sumorig = sum(orig_score_list)
    score_list = [x if x > min_score else 0 for x in orig_score_list]
    for score in score_list:
        if 0 < score < suspicious_score:
            suspicions |= suspicion.IND_SCORE_LOW

    max_mark = max(score_list) / 3  # scores < this will not be "marked"
    if max_mark == 0:
        marked_list = [False] * sll
    else:
        marked_list = [s >= max_mark for s in score_list]
    numvotes = marked_list.count(True)
    overvoted = numvotes > votes_allowed
    if overvoted:
        marked_list = [False] * sll
        numvotes = 0
        num_undervoted = 0
    else:
        num_undervoted = max(votes_allowed - numvotes, 0)
        marked_total = sum([score_list[i] for i in range(sll)
                            if marked_list[i]])
        if sumorig > sll * min_score:    # don't show unmarked contests as suspicious
            if divz(marked_total, sumorig) < suspicious_total_pct:
                suspicions |= suspicion.TOT_PCNT_LOW

    return {"marked":         marked_list,
            "overvoted":      overvoted,
            "num_votes":      numvotes,
            "num_undervoted": num_undervoted,
            "tot_scores":     sumorig,
            "suspicions":     int(suspicions)
            }


if __name__ == "__main__":
    csv_columns = ['sl', 'va', 'marked', 'overvoted', 'num_votes',
                   'num_undervoted', 'suspicions']
    csv_path = 'rpts/vote_scores.csv'
    with open(csv_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader()
        MIN_PCT = .80
        MIN_SCORE = 2.4
        for va, sl in [
            (1, (2.7, 0)),
            (1, (2.7, 0, 0, 0)),
            (2, (65, 3, 70, 0, 0)),
            (2, (65, 3, 70, 0, 0)),
            (2, (15, 3, 70, 0, 0)),
            (1, (0, 0, 0, 0, 2.3)),  # suspicious individual score
            (1, (0, 0, 0, 0, 2.5)),
            (3, (15, 10, 16, 3, 2)),
            (1, (2, 2.2, 2.1, 0.5, 0.2)),
            (1, (0, 0, 0, 0, 60)),
            (2, (0, 0, 0, 90, 60)),
            # (1, (0, 0, 0, 0, 0)),
            # (1, (0.5, 0.5, 0.5, 0.5, 4)),
            # (2, (0.5, 0.5, 0.5, 0.5, 4)),
            # (1, (0.5, 0, 0, 4, 0)),
            # (1, (0.1, 0.2, 0.2, 0.1, 4)),
            # (1, (0.5, 4, 0, 0, 4)),
            # (2, (0.5, 4, 0, 0, 4)),
            # (2, (0.5, 2, 0, 0, 2)),
            (2, (55, 10, 56, 3, 2)),
            (2, (15, 4, 16, 3, 2)),
            (2, (30, 4, 70, 3, 2)),
            (2, (50, 4, 70, 3, 2)),
            (1, (5, 4, 90, 3, 2)),
            (2, (5, 90, 90, 90, 2)),  # overvoted
            (1, (5, 90, 90, 3, 2)),  # overvoted
            (2, (5, 4, 90, 3, 2)),
            (2, (70, 4, 70, 3, 2)),
            (1, (20, 20, 70, 20, 20)),
            (2, (20, 20, 70, 70, 20)),
            (2, (10, 10, 70, 70, 10)),
            (2, (10, 10, 80, 80, 10)),
            (1, (10, 10, 80, 19, 10)),
            (1, (100, 5, 4, 3, 2)),
            (2, (100, 5, 4, 3, 2)),
            (3, (100, 5, 4, 3, 2)),
            (2, (100, 90, 4, 3, 2)),
            (3, (100, 90, 4, 3, 2)),
            (3, (100, 5, 4, 3, 2)),
            (2, (100, 90, 4, 3, 2)),
            (3, (100, 90, 70, 3, 2)),
            (3, (30, 40, 30, 3, 2)),
            (1, (100, 30, 4, 3, 2)),
            (1, (80, 20, 21, 3, 2)),
        ]:
            print(va, sl)
            result = marks_from_scores(sl, va)
            result['sl'] = sl
            result['va'] = va
            print(result)

            writer.writerow(result)
