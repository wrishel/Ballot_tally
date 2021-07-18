"""Comparison rpt.py

   Submodule to dbase.py for constructing the Comparison Report,
   which contains data merged from data imported from the Elections
   department and data accumulated by our vote counting.

  Usage:  from comparison_rpt import ElectionRpt
          er = ElectionRpt()
          er.run(election_data_iter, our_data_iter
          print(er.header_line)
          for tuple in er.build_output):
               print(tuple)

  Possible input iterables include SQL selections.
  Possible output incldes CSV."""

from __future__ import annotations
from collections.abc import Iterable, Callable
from util import divz

class SimpleRepr(object): # https://stackoverflow.com/questions/44595218/python-repr-for-all-member-variables
    """A mixin implementing a simple __repr__."""
    def __repr__(self):
        return "<{klass} @{id:x} {attrs}>".format(
            klass=self.__class__.__name__,
            id=id(self) & 0xFFFFFF,
            attrs=" ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items()),
            )

# def rpt_brk_last(a, b):
#     # Return the last instance seen, ignoring the rest
#     return b
#
# class RptBreak(SimpleRepr):
#     """Accumulate some data and return it a key value changes.
#
#        The key values must respond to !=
#
#        The accumulated values can be any objects that are collected
#        in a list until a break in the key values is seen.
#        """
#
#     def __init__(self, num_keys:int, num_accumulators:int):
#         self.key_values = [None] * num_keys
#         self.accums = [[]] * num_accumulators
#         self.first = True
#
#     def next(self, key_values:list, objs:list[object]):
#         assert len(key_values) == len(self.key_values), 'wrong number of keys'
#         assert len(objs) == len(self.sum_values), 'wrong number of values'
#         if self.first:
#             self.key_values = key_values
#             self.accums = objs
#             self.first = False
#             return None
#
#         if  key_values != self.key_values:
#             self.key_values = key_values
#             ret = self.accums.copy()
#             self.accums = objs
#             return ret
#
#         else:
#             for i in len(self.accums):
#                 self.accums[i].append(objs[i])
#
#             return None
#
#     def last(self):
#         return self.accums


class Choice(SimpleRepr):
    """One of the choices in a PrecinctContest"""

    def __init__(self, choice_name:str):
        self.choice_name = choice_name
        # data from Elections
        self.elec_votes = 0
        self.elec_winner_f = False  # flag if this choice is a winner
        # data from our counts
        self.our_votes = 0
        self.our_winner_f = False   # flag if this choice is a winner
        self.our_range_low = 0
        self.our_range_high = 0
        self.discrepancy = ''       # elec votes vs our range
        self.winners = ''             # our winner vs elec


class PrecinctContest(SimpleRepr):
    """A contest for a specific precinct with N choices."""

    def __init__(self, precinct:str, contest:str):
        self.precinct = precinct
        self.contest = contest
        self.elec_unrslvd_wi = 0    # elec unresolved write-ins
        self.elec_undervotes = 0
        self.elec_overvotes  = 0
        self.ballots_cast = 0       # see elecs_computed_bc
        self.elecs_computed_bc = 0  # ballots cast recomputed
        self.elec_margin = 0
        self.choices:dict[Choice] = dict()
        self.votes_allowed = None
        self.num_images = 0
        self.page_nums = list()
        self.our_unrslvd_wi = 0     # Our unresolved write-ins
        self.our_undervotes = 0     # our underevotes
        self.our_overvotes = 0      # our overvotes
        self.our_undetrmd = 0       # our undetermined (aka "suspicious")
        self.marked_unsuspic = 0    # number of unsuspicious marked choices
        self.cnt_unsuspic = 0       # count of unsuspicious choices
        self.our_mc_ratio = 0       # ratio of marked to total choices
        self.disagree_winner_f = False  # we disagree with elecs on winner

    def add_elec_data(self, elec_overvotes, elec_undervotes, ballots_cast):
        self.elec_undervotes = elec_undervotes
        self.elec_overvotes = elec_overvotes
        self.ballots_cast = ballots_cast

    def add_our_data(self,  undervotes, overvotes, votes_allowed,
                     suspicion, num_images, page_num, marked_unsuspic,
                     cnt_unsuspic):
        self.our_undervotes = undervotes
        self.our_overvotes  = overvotes
        self.votes_allowed = votes_allowed
        self.our_undetrmd = suspicion
        self.num_images = num_images
        self.marked_unsuspic = marked_unsuspic  # number of unsuspicious marked choices
        self.cnt_unsuspic = cnt_unsuspic        # count of unsuspicious choices
        self.add_page_num(page_num)

    def add_page_num(self, page_num):
        if page_num not in self.page_nums:
            self.page_nums.append(page_num)

    def disp_page_nums(self)->str:
        """Return page numbers separated by spaces"""

        return ','.join(sorted(self.page_nums))

    def same(self, other:PrecinctContest)->bool:
        """Close enough to be the same"""

        return type(other) == type(self) \
            and self.precinct == other.precinct \
            and self.contest == other.contest

    def add_choice_elec(self, choice:Choice):
        """Add a choice with elecs data"""

        assert choice.choice_name not in self.choices
        self.choices[choice.choice_name] = choice

    def update_choice_ours(self, choice_name:str, our_votes:int):
        """Call with one choice which usually is already here
           from elec data and add our info."""

        c = self.choices.get(choice_name, Choice(choice_name))
        c.our_votes = our_votes

    def vote_gap(self):
        """Return (low, high) the difference between our lowest
           and highest estimate for this contest."""

        low = - (self.votes_allowed * self.our_undetrmd)
        high = self.votes_allowed * (self.our_overvotes + \
                                     self.our_undetrmd) \
               + self.our_unrslvd_wi
        return low, high

class ElectionRpt(SimpleRepr):
    """Container for all Precinct_contests in an election."""

    def __init__(self):

        # the key for pct_contests is (precinct_name, contest_name)
        self.pct_contests:dict[PrecinctContest] = dict()

    def run(self, elec_rows:Iterable, our_rows:Iterable):
        """This is the MAIN."""

        self._load_elec_results(elec_rows)
        self._merge_our_results(our_rows)
        self._compute_elecs_ballot_count()
        self._create_totals()
        self._compute_winners()
        self._compute_our_ranges()
        for t in self._output_rows():
            yield t

    def _add_contest(self, pc: PrecinctContest):
        t = pc.precinct, pc.contest
        assert t not in self.pct_contests
        self.pct_contests[t] = pc

    def _load_elec_results(self, elec_rows):
        """Deserialize elec_rows into the pct_contests structure."""

        first_time = True
        curr_contest = None
        for row in elec_rows:
            next_contest = PrecinctContest(row.pct, row.contest)
            next_contest.add_elec_data(row.num_overvotes,
                            row.num_undervotes, row.ballots_cast)
            if first_time:
                curr_contest = next_contest
                first_time = False
            if not curr_contest.same(next_contest):
                self._add_contest(curr_contest)
                curr_contest = next_contest

            choice = Choice(row.choice)
            if 'write-ins' in choice.choice_name.lower():
                curr_contest.elec_unrslvd_wi += row.num_votes
                continue  # we don't add this as a choice

            choice.elec_votes = row.num_votes
            curr_contest.add_choice_elec(choice)

        self._add_contest(curr_contest)  # close contest after last row

    def _merge_our_results(self, our_rows):
        """Merge our results into the precinct/contests from elecs"""

        for row in our_rows:
            key = row.precinct, row.contest_name
            pc = self.pct_contests.get(key,
                            PrecinctContest(row.precinct, row.contest_name))
            pc.add_our_data(row.undervotes_by_pct, row.overvotes_by_pct,
                            row.votes_allowed, row.suspicion_by_pct,
                            row.num_images, row.page_number, row.marked,
                            row.cnt_unsuspic)
            if 'write in' in row.choice_name.lower():
                pc.our_unrslvd_wi += row.votes_by_pct
                continue    # Don't treat this as a choice.
            pc.update_choice_ours(row.choice_name, row.votes_by_pct)

    def _compute_elecs_ballot_count(self):
        # For sides 1 & 2 thus will get the same value as
        # pc.ballots_cast. For sides 3 and 4 it will give
        # a better value for comparing to our image count.

        for pc in self.pct_contests.values():
            x = pc.votes_allowed * pc.elec_overvotes \
                + pc.elec_unrslvd_wi + pc.elec_undervotes \
                + sum([z.elec_votes for z in pc.choices.values()])
            pc.elecs_computed_bc = x / pc.votes_allowed

    def _create_totals(self):
        """Add a pseudo precinct for county-wide totals."""

        totl = ' Cnty'
        newpccs = dict()
        for pc in self.pct_contests.values():
            k = totl, pc.contest
            newpc = newpccs.get(k, PrecinctContest(totl, pc.contest))
            newpc.ballots_cast += pc.ballots_cast
            newpc.elecs_computed_bc += pc.elecs_computed_bc
            newpc.num_images += pc.num_images
            newpc.elec_unrslvd_wi += pc.elec_unrslvd_wi
            newpc.elec_undervotes += pc.elec_undervotes
            newpc.elec_overvotes += pc.elec_overvotes
            newpc.our_unrslvd_wi += pc.our_unrslvd_wi
            newpc.our_undervotes += pc.our_undervotes
            newpc.our_overvotes += pc.our_overvotes
            newpc.our_undetrmd += pc.our_undetrmd
            newpc.votes_allowed = pc.votes_allowed
            newpc.cnt_unsuspic += pc.cnt_unsuspic
            newpc.marked_unsuspic += pc.marked_unsuspic
            for n in pc.page_nums:
                newpc.add_page_num(n)

            newchoices = newpc.choices
            for chk in pc.choices.keys():
                newchoice = newchoices.get(chk, Choice(chk))
                pcc = pc.choices[chk]
                newchoice.elec_votes += pcc.elec_votes
                newchoice.our_votes += pcc.our_votes
                newchoice.our_range_low += pcc.our_range_low
                newchoice.our_range_high += pcc.our_range_high
                newchoices[chk] = newchoice

            newpc.choices = newchoices
            newpccs[k] = newpc

        for k in newpccs.keys():
            self.pct_contests[k] = newpccs[k]

    def _compute_our_ranges(self):
        """Compute our low and high values and discrepancy."""

        for pc in self.pct_contests.values():
            if pc.contest == 'Proposition 20':
                print(pc.precinct)

            chcs = pc.choices.values()
            # tot_choices = len(chcs)
            # num_marked = sum([ch.our_votes for ch in chcs])
            marked_ratio = pc.marked_unsuspic / pc.cnt_unsuspic
            for ch in chcs:
                if ch.our_votes:
                    ch.our_range_low = ch.our_votes
                    ch.our_range_high = \
                        ch.our_votes \
                        + pc.our_unrslvd_wi \
                        + pc.votes_allowed * pc.our_overvotes
                    if pc.our_undetrmd:
                        r = 1 - marked_ratio
                        reduction = min(round(pc.our_undetrmd * r),1)
                        ch.our_range_low -= reduction
                        r = marked_ratio
                        enhancement = min(round(pc.our_undetrmd * r),1)
                        ch.our_range_high += enhancement

                    # compute discrepancy field
                    d = ''
                    if ch.elec_votes < ch.our_range_low:
                        d = ch.elec_votes - ch.our_range_low
                    elif ch.elec_votes > ch.our_range_high:
                        d = ch.elec_votes - ch.our_range_high
                    if d != '':
                        ch.discrepancy = f'{d:+}'

    def _compute_winners(self):
        # compute margin and then winners by election counts and our counts
        for pc in self.pct_contests.values():
            choices = pc.choices.values()

            # compute margins based on election votes
            srt_ch = sorted(choices, key=lambda ch: ch.elec_votes,
                             reverse=True)
            if len(srt_ch) <= pc.votes_allowed:
                pc.elec_margin = srt_ch[-1].elec_votes
            else:
                pc.elec_margin = srt_ch[pc.votes_allowed - 1].elec_votes - \
                                 srt_ch[pc.votes_allowed].elec_votes

            # flag election winners
            for i in range(pc.votes_allowed):
                ch = srt_ch[i]
                v = ch.elec_votes
                if v > 0:
                    ch.winners += '<'


            srt_ch = sorted(choices, key=lambda ch: ch.our_votes,
                             reverse=True)
            # flag our winners
            for i in range(pc.votes_allowed):
                ch = srt_ch[i]
                v = ch.elec_votes
                if v > 0:
                    ch.winners += '>'

    def header_line(self):
        return ("Precinct", "Contest", "Choice", "Elec Votes",
                "Notes", "Our Low", "Our High", "Out of Range",
                "Est. Elec Ballots Cast", "Our Number of Images",
                "Ball Cast - # Imgs", "Side Number",
                "Elec Invalid Write In", "Our Unresolved Write In",
                "Elec Overvotes", "Our Overvotes",
                "Elec Undervotes", "Our Undervotes", "Our Tentative")

    def _build_output_row(self, pc:PrecinctContest, ch:Choice):
        """Return a detail row"""

        return \
           [pc.precinct, pc.contest, ch.choice_name, ch.elec_votes,
            ch.winners, ch.our_range_low, ch.our_range_high,
            ch.discrepancy]

    def _output_rows(self):
        """Yield output rows interleaving breaks on contest."""

        # output the detail lines
        num_cols = len(self.header_line())
        for k in sorted(self.pct_contests.keys()):
            pc = self.pct_contests[k]
            sum_elec_votes = sum_our_votes = 0
            for ch in sorted(pc.choices.values(),
                             key=lambda cho: cho.elec_votes,
                             reverse=True):
                sum_our_votes += ch.our_votes
                sum_elec_votes += ch.elec_votes
                outrow = self._build_output_row(pc, ch)
                outrow += (num_cols - len(outrow)) * ['']
                yield outrow

            # output the summary at the bottom
            vg = pc.vote_gap()
            r = vg[1] - vg[0]
            rm = divz(r, pc.elec_margin)  # R/M ratio
            break_row = [pc.precinct, pc.contest,
                         (f'R/M: {rm:.0%}; Totals: '), sum_elec_votes,
                         '*' if rm >= 1 else '',
                         sum_our_votes + vg[0], sum_our_votes + vg[1],
                         '',    # Out of Range Column
                         pc.elecs_computed_bc, pc.num_images,
                         abs(pc.elecs_computed_bc - pc.num_images),
                         pc.disp_page_nums(),
                         pc.elec_unrslvd_wi, pc.our_unrslvd_wi,
                         pc.elec_overvotes, pc.our_overvotes,
                         pc.elec_undervotes, pc.our_undervotes,
                         pc.our_undetrmd]

            yield break_row
            yield [''] * num_cols  # blank row
