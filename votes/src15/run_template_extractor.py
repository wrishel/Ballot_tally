####
#changes for V1.5
#refactored more control logic into this driver so that different drivers could co-exist
####

from pathlib import Path
from tabulator import Tabulator
import time
import json
from datetime import datetime
import logging

from template_extractor import *
from barcode_lib import *

path_to_logfile = Path("../errors/random3-template_extractor.log")
path_to_image_logfile = Path("../errors/random3-template_extractor_image_log.html")
path_to_metadata_dir = Path("../metadata")

path_to_template_results_dir = Path("../templatesV15")

#setup basic logging if not done somewhere else by calling routines
logging.basicConfig(
    filename=path_to_logfile,   #uncomment to go to file
    level=logging.DEBUG,  #logging.INFO,
    #format='%(asctime)s.%(msecs)03d %(levelname)s - %(funcName)s: %(message)s',
    format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

if __name__ == "__main__":

    #open image logger if desired
    if path_to_image_logfile is not None:
        image_logger = ImageLogger(path_to_image_logfile, 15)
    else:
        image_logger = None

    metadata = Metadata(path_to_metadata_dir)
    metadata.load_all_metadata()

    extractor = TemplateExtractor(metadata, image_logger)

    precinct_tracker = {} #keep track of what already have - FIXME - make this more robust, load existing from file, etc
    #mark off templates that we already have
    for fpath in path_to_template_results_dir.glob("*.json"):
        match = re.search(r'choices_([a-zA-Z0-9\-]+)_([1234]).json', fpath.name)
        if match is not None and len(match.group(1))>0 and len(match.group(2)) == 1:
            pr = match.group(1)
            pg = match.group(2)
            print(f"Found Precinct: {pr} Page: {pg} in directory - will not re-load this one")
            pages = precinct_tracker.setdefault(pr, set())
            pages.add(pg)

    #see what we are missing (precincts)
    all_precincts = set(metadata.precincts.keys())
    print("Missing precincts include: ", all_precincts - set(precinct_tracker.keys()))

    #range across some sample ballots to be used for template generation

    for template_path in Path("/Users/david/Dropbox/david/random3/").glob('*.jpg'):
        
        #decide if we need this sample, or do we already have it? 

        bc_image = cv2.imread(str(template_path))  #color, BGR

        #lets see if we can skip the autostraighten for simple barcode parse?        
        ul_bc, ll_bc = extract_bar_codes(bc_image, template_path)
        if ul_bc is None or ll_bc is None:
            logging.error(f"Form: {template_path.name} Screening -UNABLE TO EXTRACT BOTH BARCODES - SKIPPING FORM")
            continue

        logging.info(f"Form: {template_path.name} Screening - extracted BAR CODES WERE: {ul_bc} {ll_bc}")

        precinct = metadata.convert_barcode_to_precinct(ul_bc)
        page = int(ll_bc[7:8])
        logging.info(f"Form: Screening of {template_path.name} extracted precinct={precinct} page={page}")

        #do we need this form, or do we already have a good version?
        got_pages = precinct_tracker.setdefault(precinct, set())
        if page in got_pages:
            print(f"WE ALREADY HAVE {precinct} AND PAGE:{page} - skip this form {template_path.name}")
            continue
        #will add it to tracker later, only if successful

        #yes, extract what we can - choiceboxes has all the template info
        et_status, choiceboxes = extractor.extract_template(template_path, precinct, page)
        
        vt_status = False
        template_choices_json = None
        
        if et_status is True: #we have some choiceboxes to evaluate
            #do choicebox validation, eventually offer a chance to UX for repair??
            logging.info(f"form:{template_path.name} START final validation")

            vt_status, bad_box_set = extractor.validate_template(choiceboxes)
            
            message = ""
            if vt_status:
                message += f"Form: {template_path.name} PASSED validation\n"
                message += f"Precinct: {extractor.precinct} Page: {extractor.page}\n"
                logging.info(f"Form: {template_path.name} PASSES validation")
                print(f"Form: {template_path.name} PASSES validation")
            
            else:
                message += f"Form: {template_path.name} FAILED validation\n"
                message += f"Precinct: {extractor.precinct} Page: {extractor.page}\n"
                message += f"Correct these choicesboxes (0=first box) {bad_box_set}"
                logging.error(f"Form: {template_path.name} FAILS validation")
                logging.error(f"Correct these choicesboxes (0 = first box): {bad_box_set}")
                print(f"Form: {template_path.name} FAILS validation")

            #convert choice-boxes to JSON
            template_choices_json = extractor.convert_to_json(choiceboxes, '2Jan2020', "McCallie")        
                
            if image_logger:
                #convert back to dictionary to generate a round-trip annotation
                choices_dict_rt = json.loads(template_choices_json)
                painted_image_gbr = extractor.annotate_template(template_path, choices_dict_rt)
                image_logger.log_image(painted_image_gbr, 25, datetime.now(), template_path, message)
        
        #if we have a validated extraction, do something with it
        if vt_status is True:

            print(f"ready to store TEMPLATE JSON - added {precinct} & {page} to tracker")

            
            #prepare the file name for where this template and metadata will go:
            path_to_save_template_file = path_to_template_results_dir / "template_{}_{}.jpg".format(extractor.precinct, extractor.page)
            path_to_save_choices_file = path_to_template_results_dir / "choices_{}_{}.json".format(extractor.precinct, extractor.page)
            
            #first save the straightened but un-marked template file
            opencv_status = cv2.imwrite(str(path_to_save_template_file), extractor.get_straightened_image() )
            if opencv_status is False:
                print("UNABLE TO SAVE template file - unknown exception in CV2.IMWRITE")
                print("Will skip writing CHOICES file as well")
                continue

            print(f"SAVED NEW TEMPLATE file: {path_to_save_template_file}!")
            
            #then save the choice-box JSON file
            try:
                with open(path_to_save_choices_file, "w") as outfile: 
                    outfile.write(template_choices_json)
            except:
                print("UNABLE TO SAVE choices file - Exception: {}".format( sys.exc_info()[0] ))
                continue

            print(f"SAVED NEW CHOICES file: {path_to_save_choices_file}!")
            precinct_tracker[precinct].add(page)

print("Done with Template Extraction")


    


