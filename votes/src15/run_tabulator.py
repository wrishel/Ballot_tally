from pathlib import Path
from tabulator import Tabulator
import time
import json
from datetime import datetime
import logging

from ballot_scanner import BallotScanner
from tabulator import Tabulator

path_to_logfile = Path("../errors/all_ballot_scanner.log")
path_to_image_logfile = Path("../errors/all_ballot_image_log.html")
path_to_metadata_dir = Path("../metadata")
path_to_template_dir = Path("../templatesV15")
json_logfile_path = Path("../results/all_ballot_results.json")

if __name__ == "__main__":

    #setup basic logging if not done somewhere else by calling routines
    logging.basicConfig(
        filename=path_to_logfile,
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    
    tabulator = Tabulator()

    #load the json data, into memory, why not
    json_file_path = Path("/Users/david/Dropbox/PythonProjects-dpm/Ballot_tests/results/all_ballot_results.json")

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
            
    print("Number of JSON data records = ", len(data))

    #page_count = 0
    reasons = {}

    for ballot in data:

        tabulator.add_form_result(ballot)

        #get stats on failures
        if ballot['processing_comment'] != "":
            cmt = ballot['processing_comment']
            reasons[cmt] = reasons.get(cmt, 0) + 1
        # p = ballot.get('page')
        # if p is not None:
        #     if ballot['page'] == 1:
        #         page_count += 1

    tabulator.save_to_csv(Path("../tabulator_tests"))
    # print(f"page 1 count = {page_count}")
    print("Done tabulating")

    reasons_sorted = sorted( reasons.items(), key = lambda kv:(kv[1],kv[0]), reverse=True)
    print("reasons:")
    for k, v in reasons_sorted:
        print(f"{k} = {v}")

    #tabulator.print_contests()