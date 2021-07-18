
from util import concise_pairs, report, report_quantities

with open(r'C:\Users\15104\AppData\Roaming\JetBrains\PyCharm2020.2\scratches\scratch.txt') as inf:
    data = sorted([int(x) for x in inf.readlines()])

print(report_quantities('2SHR1', concise_pairs(data)))