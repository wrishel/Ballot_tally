from pathlib import Path
import json
import time

from database_updater import *

def load_all_json_results(path):
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
            data.append(json.loads(obj))

    print(f"loaded {len(data)} JSON records")
    return data

if __name__ == "__main__":

    json_file_path = Path("../results/all_ballot_results.json")
    json_as_python = load_all_json_results(json_file_path)

    dbu = DatabaseUpdater()


    if dbu.connect("election", "election"):

        #do some stuff
        start_time = time.time()
        count = 0

        print("started database updating")

        dbu.start_transactions()

        for jr in json_as_python:

            #dbu.start_transactions(batchsize=1)
            status = dbu.insert_or_update_one_form(jr)
            count += 1
            #if status:
            #    dbu.finish()
            #else:
            #    dbu.rollback_transactions()
        
        dbu.finish()

        stop_time = time.time()
        print(f"Elapsed time = {stop_time - start_time} per tx: {(stop_time - start_time) / count}")

    else: 
        print("Something went wrong")

    print("Done")