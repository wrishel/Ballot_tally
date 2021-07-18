""""Timer.py module for measuring clock time."""

# Records time in various categories as named in calls.
#
# import timer
# t = timer()   # starts the clock running
# (do stuff for 1 second)
# t.switch_to('name1')  # accumulate time under name1
# (do stuff for 2 second))
# t.switch_to('name2')  # accumulate time under name2
# (do stuff for 3 second))
# t.switch_to('name1')  # accumulate more time under name1
# (do stuff for 4 second))
# t.get_times()  # returns a list of name, total time (secs), count
#                 e.g.,
#                 [('name1',    6.0,  2),
#                  ('name2',    3.0,  1),
#                  ('~other~',  1.0,  1)]
#
# other methods: push(name)   # switch to name
#                pop()        # revert to the name before push

import os
import sys
import time
from datetime import datetime

class timer(object):
    """Accumulate timings for performance monitoring."""

    def __init__(self):
        self.times = {}
        self.counts = {}
        self.timing = '~other~'  # what is  being timed now
        self.last_start = datetime.now()
        self.switch_to()    # initially running for ~other~
        self.pushed_names = list()

    def switch_to(self, name:str = '~other~'):
        self._accumulate()
        self.timing = name
        self.counts[name] =  self.counts.get(name, 0) + 1
        self.last_start = datetime.now()
        # uncomment the next line for tracing
        # print(os.getpid(), name, file=sys.stderr)

    def push(self, name:str = '~other~'):
        self.pushed_names.append(self.timing)
        self.switch_to(name)

    def pop(self):
        self.switch_to((self.pushed_names.pop()))

    def _accumulate(self):
        self.times[self.timing] = \
            self.times.get(self.timing, 0.0) \
             + (datetime.now() - self.last_start).total_seconds()

        self.last_start = datetime.now()

    def get_times(self) -> list:
        self._accumulate()
        return sorted([(x, self.times[x], self.counts[x])
                        for x in self.times.keys()])

    def __repr__(self)->str:
        vals = [f'{str(x)}' for x in self.get_times()]
        return f'<timer: {"; ".join(vals)}>'


if __name__ == '__main__':
    # --------------------- unit testing
    def test(b: bool, s: str) -> bool:
        if not b:
            print(s, file=sys.stderr)
        return not b

    expected = [('A', 1.3, 3),
                ('B', 0.2, 1),
                ('pushed', 0.8, 1),
                ('~other~', 0.1, 2)]
    start = datetime.now()
    t = timer()
    t.switch_to('A')
    time.sleep(1)
    t.switch_to("B")
    time.sleep(0.2)
    t.switch_to('A')
    time.sleep(0.3)
    t.push('pushed')
    time.sleep(0.8)
    t.pop()
    time.sleep(0.05)
    t.switch_to()
    time.sleep(0.1)
    results = t.get_times()
    total_time = (datetime.now() - start).total_seconds()
    if test(len(expected) == len(results), 'Lengths mismatched'):
        exit(-1)
    sumtimes = 0
    for i in range(len(expected)):
        exp_name = expected[i][0]
        if test(exp_name == results[i][0],
                f'Item {i} name mismatch: '
                f'{exp_name} vs {results[i][0]}'):
            continue

        exp_time = expected[i][1]
        res_time = results[i][1]
        sumtimes += res_time
        # Accept 10% extra time because the sleep times are small.
        test(exp_time <= res_time <= 1.10 * exp_time,
                f'item "{exp_name}" time mismatch: '
                f'{exp_time} vs {res_time}')
        # check counts
        exp_count = expected[i][2]
        res_count = results[i][2]
        test(exp_count == res_count,
            f'"{exp_name}" count mismatch {exp_count} vs {res_count}')

    # Was all clock time accounted for?
    # Allow for floating point rounding.
    test(abs(sumtimes - total_time) < 1e-14 * total_time,
        f"total time mismatch: {sumtimes} vs {total_time}")