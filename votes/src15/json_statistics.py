import json
from pathlib import Path
from scanner_constants_and_data_structures import HIGH_THRESHOLD
import numpy as np

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [8, 8]

json_file_path = Path("/Users/david/Dropbox/PythonProjects-dpm/Ballot_tests/results/all_ballot_results.json")
#with open(json_file_path) as f:
#    data = json.load(f)

data = []
with open(json_file_path) as json_file:
    obj = ""
    for line in json_file.readlines():
        #print("line = ", line)
        clean = line.strip()
        if "}{" in clean:
            #terminate the obj and convert to json
            obj += "}"
            data.append(json.loads(obj))
            obj = "{"
            continue        
        obj += str(clean)
        #print("len obj = ", len(obj))
    
    if len(obj) > 0:
        data.append(json.loads(obj)) #last one

print("len data = ", len(data))
        

pres = []
trump = 0
for ballot in data:
    #is this a result that has contests (vs blank etc)
    contests = ballot.get('contests')
    if contests:
        for contest in contests:
            if "PRESIDENT" in contest['contest_name']:
                pres.append(contest)
                for cb in contest['choices']:
                    if "TRUMP" in cb['choice_name']:
                        if cb['marked'] == True:
                            trump += 1

print(f"There were {len(pres)} presidential contests")
print(f"There were {trump} 'marked' votes for Trump")

results = {}
for contest in pres:
    for choice in contest['choices']:
        if choice['marked'] == True:
            name = choice['choice_name']
            results[name] = results.get(name, 0) + 1

print(results)

fails = {}
for contest in pres:
    if contest['overvoted'] == True:
        fails['overvoted']  = fails.get('overvoted',0) + 1
    if contest['undervoted'] == True:
        fails['undervoted']  = fails.get('undervoted',0) + 1
    if contest['validcount'] == True:
        fails['validcount']  = fails.get('validcount',0) + 1

print()
print(fails)

#page 1
page_count = 0
for ballot in data:
    p = ballot.get('page')
    if p:
        if ballot['page'] == 1:
            page_count += 1
    #else:
    #    print("ballot missing page = ", ballot)

print("page 1 = ", page_count)

#true/false
true_count = 0
false_count = 0
for ballot in data:
    p = ballot.get('processing_success')
    if p is not None:
        if ballot['processing_success'] == True:
            true_count += 1
        else:
            false_count += 1
    else:
        print("ballot missing 'processing success!' = ", ballot)
print(f"processing success counts T:{true_count}  F:{false_count}")

#near threshold of 3
close_call = 0
closeness = 0.1
for ballot in data:
    #is this a result that has contests (vs blank etc)
    contests = ballot.get('contests')
    if contests is not None:
        for contest in contests:
            for cb in contest['choices']:
                if abs(cb['score'] - HIGH_THRESHOLD) <= closeness:
                    print(f"Close call: form: {ballot['image_number']} score:{cb['score']} contest:{contest}\n")
                    close_call += 1

print(f"Number of close calls = {close_call}")

# all_scores = []
# easy = 0
# one_and_over = 0
# p_wins = []

# for ballot in data:
#     for contest in ballot['contests']:
#         if contest['votes_allowed'] == 1 and contest['overvoted'] == True:
#             candidate_scores = []
#             one_and_over += 1
#             for choice in contest['choices']:
#                 score = choice['score']
#                 all_scores.append(score)
#                 candidate_scores.append(score)
#             #did anyone in contest get more than X% of total
#             sorted_scores = sorted(candidate_scores, reverse=True)
#             all = sum(candidate_scores)
#             percent_win = int(100 * (sorted_scores[0] / all))
#             p_wins.append(percent_win)

# np_scores = np.array(all_scores, dtype=float)
# print("len scores = ", len(all_scores))
# print("number of overvote 1-winner contests ", one_and_over)
# print("easy calls = ", easy)
# #plt.hist(all_scores, bins=200)

#np_scores /= sum(np_scores)
#np_scores *= 100
# plt.subplot(211)
# plt.title("density of scores for 1-winner OVERvoted contests")
# plt.hist(np_scores, density=1, bins=100)
# plt.subplot(212)
#plt.title("density non-zero scores for 1-winner")
#plt.hist(p_wins, bins=100)
#plt.hist(np_scores, density=1, bins=[ x for x in range(1,101)])
#plt.xlabel("choicebox score")
# plt.title("Best candidate's percentage of total score per 1 win overvoted contest")
# plt.hist(p_wins, density=1, bins=100)
# plt.show()