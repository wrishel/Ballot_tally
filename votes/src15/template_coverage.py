from pathlib import Path
from tabulator import Tabulator
import time
import json
from datetime import datetime
import logging

from metadata import * 

path_to_metadata_dir = Path("../metadata")
path_to_template_results_dir = Path("../templatesV15")

#setup basic logging if not done somewhere else by calling routines
logging.basicConfig(
    #filename=path_to_logfile,   #uncomment to go to file
    level=logging.DEBUG,  #logging.INFO,
    #format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
    format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

class CoverageAccumulator():
    def __init__(self):
        self.precincts = {}

    def _add_coverage(self, precinct, contest):
        #count each time a precinct-contest is added
        if precinct and contest:
            contests = self.precincts.setdefault(precinct, {})
            contests[contest] = contests.get(contest, 0) + 1
        else:
            print("WARNING - either precinct:{precinct} or contest:{contest[0:20]}... is missing!")

    def extract_choices_dictionary(self, choices_dict):
        #scan this template and add coverage for each pre-contest
        precinct = choices_dict.get("precinct")
        for contest in choices_dict['contests']:
            self._add_coverage(precinct, contest['contest_name'])
    
    def is_covered(self, precinct, contest):
        contests = self.precincts.get(precinct)
        if contests and (contest in contests.keys()):
            return True
        return False

    def dump(self):
        for precinct, contests in self.precincts.items():
            for contest, count in contests.items():
                print(f"Coverage: {precinct} {contest} = {count}")


if __name__ == "__main__":

    metadata = Metadata(path_to_metadata_dir)
    metadata.load_all_metadata()

    coverage_accum = CoverageAccumulator()

    for c_dict in path_to_template_results_dir.glob("choices*.json"):
        with open(c_dict, "r") as f:
            choices_dict = json.load(f)
            coverage_accum.extract_choices_dictionary(choices_dict)

    #coverage_accum.dump()

    #find all the gaps, based on metadata
    for precinct, contests in metadata.precincts.items():
        for contest in contests:
            if coverage_accum.is_covered(precinct, contest):
                continue
            else:
                print(f"No Template Coverage: {precinct} <--> {contest}")


    print("done")