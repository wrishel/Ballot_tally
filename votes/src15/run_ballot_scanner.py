from pathlib import Path

from numpy.lib.function_base import average
from tabulator import Tabulator
import time
import json
from datetime import datetime
import logging

from ballot_scanner import BallotScanner
from tabulator import Tabulator

path_to_logfile = Path("../errors/0205_ballot_scanner.log")
path_to_image_logfile = Path("../errors/0205_ballot_image_log.html")
path_to_metadata_dir = Path("../metadata")
path_to_template_dir = Path("../templatesV15")
json_logfile_path = Path("../results/0205_ballot_results.json")

if __name__ == "__main__":

    #setup basic logging if not done somewhere else by calling routines
    logging.basicConfig(
        filename=path_to_logfile,
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    
    #CHANGED IN V1.5 - separated metadata from template directories
    scanner = BallotScanner(path_to_metadata_dir, path_to_template_dir, path_to_image_logfile)
    
    #Tabulator is a simple tabulator driven by the JSON output.
    #might serve as a good template for your database update code?
    tabulator = Tabulator()

    #data_accumulator is my original tabulator built into the core logic - will be removed at some point
    #just pass in the dictionary and ingore it
    data_accumulaters = {}
    
    #this is where the json strings get dumped, if you want to dump a copy.
    jlf = open(json_logfile_path, 'w')

    #path_to_form_dir = Path("/Volumes/Data/david-data/Dropbox/david/")
    path_to_form_dir = Path("/Volumes/Data/david-data/Dropbox/david/02-05")
    #path_to_form_dir = Path("/Volumes/Data/david-data/Dropbox/PythonProjects-dpm/Ballot_tests/failed_forms_from_wes/")
    
    successes = 0
    blanks = 0
    failures = 0
    times = []

    #for form_path in path_to_form_dir.glob('**/27*.jpg'):  #matches all JPG in the directory (can be made recursive also)
    for form_path in path_to_form_dir.glob('**/*.jpg'):  #matches all JPG in the directory (can be made recursive also)
        
        start = time.time()
        
        #this is the main routine - pass in the path to image, one image path at a time
        #Note - you might rather pass the actual image bytes in? Should I create an alternate entry point for that?

        status = scanner.process_one_scanned_form(form_path, data_accumulaters)
        
        elapsed = time.time() - start
        times.append(elapsed)

        #returns True if all was well, or False if there was a problem (a change from V1!!)

        if (status == True):
            
            #grab the processed form's json as an actual json string
            #OR grab the form's data using: scanner.get_form_result_as_dict()

            #NOTE - this writes the JSON as a concatenated string, which is probably NOT what you want
            #change this to create an array if you want to write out standard JSON file format, but what about crashes

            json_string = scanner.get_form_result_as_json()  #gets actual JSON-encoded string
            jlf.write(json_string)

            tabulator.add_form_result(scanner.get_form_result_as_dict())
            successes += 1

        else:

            #even the failure will produce some minimal JSON result.
            json_string = scanner.get_form_result_as_json()
            jlf.write(json_string)

            #we aren't tabulating the failures, as they have no votes extracted.
            #but count blank forms for interest
            result = scanner.get_form_result_as_dict()
            comment = result.get("processing_comment")
            form = result.setdefault("image_number", "unknown")

            if comment and ("probably blank" in comment):
                blanks += 1
            else:
                print(f"scanner returns non-blank failure on form: {form}")
                failures += 1

        #if (successes + failures + blanks) % 10 == 0:
        #    print(f"Processing stats: successes:{successes} blanks:{blanks} failures:{failures}")

    jlf.close()

    #tabulator.print_contests()

    path_to_results_directory = Path("../results")
    tabulator.save_to_csv(path_to_results_directory)

    print(f"FINAL Processing stats: successes:{successes} blanks:{blanks} failures:{failures}")
    average_time = average(times)
    print(f"average time per form = {average_time} seconds")
    exit()
