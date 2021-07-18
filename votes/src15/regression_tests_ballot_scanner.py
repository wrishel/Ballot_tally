from pathlib import Path
from tabulator import Tabulator
import time
import json
from datetime import datetime
import logging
import sys

from deepdiff import DeepDiff
from pprint import pprint

from ballot_scanner import BallotScanner

path_to_logfile = Path("../errors/regression_tests.log") #todo add test and verify to log files?
path_to_image_logfile = None # todo add tests for image logs?   Path("../errors/image_log.html")

path_to_metadata_dir = Path("../templates")
path_test_dir = Path("../regression_tests")

def process_ballot_and_compare_to_json(scanner, path_to_one_ballot, path_to_comparison_json):
    #one ballot vs one json file

    #just pass in the old data accumulator and ingore it for now since Wes does not use this
    data_accumulaters = {}

    status = scanner.process_one_scanned_form(path_to_one_ballot, data_accumulaters)
    if status is not True:
        print("Regression tests FAIL for form: {} - scanner return is not True".format(path_to_one_ballot.stem))
        return False

    #load the pre-prepared JSON output expected for this ballot
    try:
        with open(path_to_comparison_json) as f:
            correct_json = json.load(f)
            if correct_json is None:
                print("Regression tests FAIL for form: {} - cannot load JSON file: {}".format(
                        path_to_one_ballot.stem, path_to_comparison_json.stem))
                return False
    except:
        print("Regression tests FAIL for form: {} - cannot load JSON file: {}".format(
                        path_to_one_ballot.stem, path_to_comparison_json.stem))
        print("Fails due to caught exception = ", sys.exc_info()[0])
        return False

    #grab the ballot's JSON
    ballot_json = scanner.get_form_result_as_dict() #get version of output in python dictionary form
    
    #null out the one date field so we don't fail on that
    ballot_json['date_time_tabulated'] = ""
    correct_json['date_time_tabulated'] = ""

    #then do a bulk compare - this MIGHT get tripped up on insignificant decimal points??
    #may need to do a smarter comparison!
    #try DeepDiff to see if that works well enough?

    results = DeepDiff(ballot_json, correct_json, ignore_order=True)
    pprint (results, indent = 2)

    return True



if __name__ == "__main__":

    #simple regression tests
    #verify that the test ballot produces the same JSON as captured in a file
    #setup basic logging if not done somewhere else by calling routines
    
    logging.basicConfig(
        filename=path_to_logfile,
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    
    scanner = BallotScanner(path_to_metadata_dir, path_to_image_logfile)
    
    #probably should make this automatically fetch from the regression_test directory?
    test_pairings = [
        ('246500.jpg', '246500.json'),
        ('162532.jpg', '162532.json'),
        ('087616.jpg', '087616.json'),
        ('246500.jpg', '246500.json'),
        ('269208.jpg', '269208.json'),
        ('270496.jpg', '270496.json'),
        ('270620.jpg', '270620.json'),
        #(),
    ]

    #run thru all tests. Note that test process dumps errors if there are any

    for ballot, result in test_pairings:
        print("/n==========================================================================================")
        status = process_ballot_and_compare_to_json(scanner, path_test_dir / ballot, path_test_dir / result)


    print("REGRESSION TESTS DONE")

