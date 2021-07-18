import time
import ray
import logging
import sys
import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime

from ballot_scanner import BallotScanner
from tabulator import Tabulator

path_to_logfile = Path("../errors/ray_ballot_scanner.log")
path_to_image_logfile = Path("../errors/ray_ballot_image_log.html")
path_to_metadata_dir = Path("../metadata")
path_to_template_dir = Path("../templatesV15")
json_logfile_path = Path("../results/ray_ballot_results.json")

NUMBER_WORKERS = 6

#####
### define the ballot scanner worker, which will be created as a Ray Actor, in a separate process

@ray.remote
class BallotScannerWorker():
    def __init__(self):
        logging.basicConfig(
            filename=path_to_logfile,
            level=logging.DEBUG,
            format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S') 

        #create our instance of BallotScanner
        self.scanner = BallotScanner(path_to_metadata_dir, path_to_template_dir, path_to_image_logfile)
        
        #data_accumulator is my original tabulator built into the core logic - will be removed at some point
        #just pass in the dictionary and ingore it
        self.data_accumulaters = {}
    
    def process_one_ballot(self, form_path):
        #start = time.time()
        
        #this is the main routine - pass in the path to image, one image path at a time
        #Note - you might rather pass the actual image bytes in? Should I create an alternate entry point for that?

        status = self.scanner.process_one_scanned_form(form_path, self.data_accumulaters, measure_extraneous_marks=False)  #, page=1, precinct="5MK-7")
        
        #elapsed = time.time() - start

        return (status, self.scanner.get_form_result_as_dict())

if __name__ == "__main__":

    ####
    ### driver routine
    ####

    #this is where the json strings get dumped, if you want to dump a copy.
    jlf = open(json_logfile_path, 'w')

    #Tabulator is a simple tabulator driven by the JSON output.
    tabulator = Tabulator()

    ray.init()

    start = time.time()

    successes : int = 0
    blanks : int = 0
    failures : int = 0
    total_ballots : int = 0

    #allocate a pool of workers (Ray Actors)
    pool = ray.util.ActorPool([BallotScannerWorker.remote() for x in range(NUMBER_WORKERS)])

    #submit the forms to the pool
    #for now, we submit all of them at once, but probably should batch them!

    for form_path in Path("/Volumes/Data/david-data/Dropbox/david/random").glob("*.jpg"):
        pool.submit(lambda a, v: a.process_one_ballot.remote(v), (form_path))
        total_ballots += 1

    print(f"submitted {total_ballots} ballots to processing pool")
    total_ballots = 0

    #now wait for each process to produce the ballot results, and store them

    while pool.has_next():

        #fetch the results from a scanner worker
        (status, result_as_dict) = pool.get_next_unordered()
        total_ballots += 1

        if status == False:
            comment = result_as_dict.get("processing_comment")
            if comment and ("probably blank" in comment):
                blanks += 1
            else:
                print(f"ballot failure: {comment}")
                failures += 1

        if total_ballots % 100 == 0:
            avg_time = (time.time() - start) / total_ballots
            print(f"Total ballots processed: {total_ballots} with average time per ballot:{avg_time}. Blanks: {blanks} Failures: {failures}")

        #convert the dict to a json string for file
        result_as_json = json.dumps(result_as_dict, indent=2)
        jlf.write(result_as_json)
        
        if (status == True):
            #tabulate but don't store for now
            tabulator.add_form_result(result_as_dict)

    jlf.close()
    ray.shutdown()

    print(f"DONE: Total ballots processed: {total_ballots} with average time per ballot:{avg_time}. Blanks: {blanks} Failures: {failures}")

        