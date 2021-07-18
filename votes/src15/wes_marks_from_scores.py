from numbers import Number



def marks_from_scores(score_list: list[Number], votes_allowed: int,
                pct: float, min_score:float) -> dict:
    """Resolve the scores for the choices in a contest.

       Convert them to a list of booleans describing whether each
       choice was marked and booleans indicating whether the overall
       contest was undervoted or overvoted.

       Some contests have scores that are too close to call. For these
       the returned values are None. The paramter pct is a fraction that
       is used to decide what is too close to call."""

    # Todo: change type hint for lists to iterables

    sumscores = sum(score_list)
    sll = len(score_list)
    marked_list = [False] * sll
    scores = sorted(zip(score_list, range(sll)), reverse=True)
    if scores[0][0] < min_score:
        marked_list = [False] * sll
        ratio = None

    else:
        assert votes_allowed < sll, \
            f'score_list = {score_list}; votes_allowed = {votes_allowed}'
        gaps = [(scores[i][0] - scores[i + 1][0], i)
                for i in range(sll - 1)]
        biggest_gap = max(gaps)
        candidates = [scores[i] for i in range(biggest_gap[1] + 1)]
        sum_candidates = sum((x[0] for x in candidates))
        ratio = round(sum_candidates / sumscores, 2)
        if ratio < pct:
            marked_list = [None] * sll  # too close to call
            overvoted = None
            undervoted = None

        else:
            for i in range(biggest_gap[1] + 1):
                marked_list[scores[gaps[i][1]][1]] = True

    numvotes = marked_list.count(True)
    if numvotes > votes_allowed:
        overvoted = True
        marked_list = [False] * sll
    else:
        overvoted = False

    undervoted = numvotes < votes_allowed

    return {"Allowed": votes_allowed,
            "Scores": ' '.join((f'{x:5.1f}' for x in score_list)),
            "Output": ''.join((str(x)[0] for x in marked_list)),
            "Overvoted": overvoted,
            "Undervoted": undervoted,
            "Ratio": ratio
            }
