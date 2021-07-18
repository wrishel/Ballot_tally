#from pyzbar import pyzbar  #tested with pyzbar.__version__ == 0.2.1
import sys
import cv2    #tested with cv2.__version__ == 4.4.0
import time
from datetime import datetime
import numpy as np
import re
from collections import *
from pathlib import Path
import csv
import json
import pandas as pd
import logging
from enum import IntFlag, auto

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [10, 10]

#import our library files
#NOTE - this is probably not correct way to do local imports!
#these library files should be in same directory as ballot_scanner

from image_logger import ImageLogger
from barcode_lib import *
from image_processing_lib import *
from metadata import *

class FormStatus(IntFlag):
    NOTHING = auto()  #this can't be right? Can't create an IntFlag with no value????
    VALIDCOUNT = auto() #not really independent from UNDER and OVER??
    UNDERCOUNT = auto()
    OVERCOUNT = auto()
    WRITEIN = auto()
    UNDERTHRESHOLD = auto()

#note that caller should implement logging choices

class BallotScanner():
    
    def __init__(self, path_to_metadata_dir, path_to_template_dir, path_to_image_logfile) -> None:
        #NOTE - all "path_to" should be supplied as Path("x/y/z") using pathlib
        self.path_to_metadata_dir = path_to_metadata_dir
        self.path_to_template_dir = path_to_template_dir
        
        #pass in None if you don't want to log certain images
        self.path_to_image_logfile = path_to_image_logfile

        self.page = None  
        self.precinct = None 

        self.image_number = ""     #will hold the stem of the current form, eg minus path and minus ext, so 12345.jpg => "12345"
        self.form_result = None     #will be the json-ready results of the current form (top level dict)

        #some local cache files
        self.template_cache = {}
        self.choices_json_cache = {}
        #self.precinct_to_barcode = {} #this is not 1:1, can't use dictionary, but don't need it anyway
        #V1.5 replaced by metadata call -> self.barcode_to_precinct = {}

        self.visually_log_after_homology_message = ""    #if string is not null, log the image with message explaination about homology issue

        #open various image logger
        # if path is None, self.image_logger will not write any logs        
        self.image_logger = ImageLogger(self.path_to_image_logfile, 15)
       
        #load precinct barcode dictionaries
        #V1.5 - load Metadata, which has the barcode dictionaries now
        #self._load_precinct_to_barcode_dictionaries()
        self.metadata = Metadata(self.path_to_metadata_dir) #V1.5
        self.metadata.load_all_metadata()


    def get_form_result_as_json(self):
        #returns a single form's results as JSON-encoded string
        return json.dumps(self.form_result, indent=2)

    def get_form_result_as_dict(self):
        return self.form_result

    #this is the main routine to process one form
    def process_one_scanned_form(self, form_path, data_accumulaters, precinct=None, page=None ):
        #occasional throws from CV2 or unfixed bugs - trap them here
        
        self.form_result = {}
        try:
            logging.info("Form: {} - START processing new ballot".format(form_path))  #show full path on start
            duration_start_time = time.time()
            self.form_result["processing_success"] = "Unknown"
            self.form_result["processing_comment"] = "" 
            return_status = self._do_process_one_scanned_form(form_path, data_accumulaters, precinct, page )
        
        except:
            print(f"Form:{form_path} - caught exception = {sys.exc_info()[0]}")
            logging.error("Form: {} - Fatal exception {} Form was NOT processed".format(form_path.stem, sys.exc_info()[0]))
            self.form_result["processing_success"] = False
            self._add_processing_comment(f"Fatal exception was thrown: {sys.exc_info()[0]}")
            return_status = False
        
        finally:
            duration = time.time() - duration_start_time
            logging.info(f"Form: {form_path.name} - FINISHED processing ballot. Total time: {duration} seconds")
            return return_status

    def _do_process_one_scanned_form(self, form_path, data_accumulaters, precinct, page ):

        #let the caller pass in precinct and page if they are already known - otherwise set to None
        self.page = page   
        self.precinct = precinct
        self.form_path = form_path

        self.image_number = form_path.stem #remember to use pathlib Path to pass in form's location!
        self.form_result["image_number"] = self.image_number
        self.form_result["date_time_tabulated"] = datetime.now().isoformat()
 
        img = cv2.imread(str(form_path))
        self.img = img

        if img is None:
            logging.error("FORM: {} - UNABLE TO LOAD ".format(form_path))
            self.form_result["processing_success"] = False
            self._add_processing_comment("Could not read form file")
            return False
        
        #pre-compute and cash the gray and binary forms of the image - might save time later
        #no, turns out there's not much re-use, since re-contouring happens after alignment, warping, etc.
        #self.image_gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
        #_, self.image_binary = cv2.threshold(self.image_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
        #self.image_contours, _ = cv2.findContours(self.image_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)  #CHAIN_APPROX_SIMPLE is tiny bit faster?

        #check if the form is blank - will have barcode, but we don't need to mess with it if the form is blank

        if self._isFormBlank():
            logging.info(f"Form:{form_path.name} appears to be blank - skipping it")
            self.form_result["processing_success"] = False
            self._add_processing_comment("Form was probably blank")
            return False

        #if we already know the precinct and page, we can skip the barcode reading
        if self.precinct is None or self.page is None:
            
            #we don't have one or more elements so we need to extract barcodes to see what precinct and page this is
            ul_bc, ll_bc = extract_bar_codes(img, form_path)
            if ul_bc is None or ll_bc is None:
                #initial barcode not readable - try temporary alignment first
                logging.info("Form: {} - INITIAL barcodes could not be read - will try temporary alignment".format(form_path.name))
                temp_aligned_image, _ = align_form_using_barcode_stripes(img, form_path)
                #try extract_bar_codes against aligned version
                ul_bc, ll_bc = extract_bar_codes(temp_aligned_image, form_path)
                
                #if fails do the flip try
                if ul_bc is None or ll_bc is None:      

                    logging.info("Form: {} - INITIAL barcodes could not be read - will try 180 flip".format(form_path.name))
                    
                    message = "Form failed barcode extraction - will try flipping it\n"
                    #self.image_logger.log_image(img, 30, datetime.now(), form_path.name, message)
                    self.visually_log_after_homology_message += "Form was FLIPPED - please inspect HOMOLOGY\n"        
                    
                    #flip image 180 for upside down images
                    #img_flip = cv2.rotate(img, cv2.ROTATE_180)
                    img_flip = cv2.flip(img, -1) #flip both H and V, should give 180
                    
                    #try bc again
                    ul_bc, ll_bc = extract_bar_codes(img_flip, form_path)
                    if ul_bc is None or ll_bc is None:

                        #try align 
                        #try extract_b_c
                        #if fail

                        logging.error("Form: {} - barcodes could NOT be read even after flip. Form NOT processed".format(form_path.name))
                        self.form_result["processing_success"] = False
                        self._add_processing_comment("Barcodes were unreadable even after trying 180 flip")
                        return False
                    else:
                        logging.info("Form: {} - Flipped Barcodes look OK - will process flipped version".format(form_path.name))
                        
                        img = img_flip
                        self.img = img
                        
                        message = "Flipped form passed barcode extraction - continuing \n"
                        
                        #self.image_logger.log_image(img, 30, datetime.now(), form_path.name, message)
                        self.form_result["flipped_form"] = True 
                else:
                    logging.info("Form: {} - Barcode temporary alignment worked, continue processing".format(form_path.name))

            #V1.5 precinct = self.barcode_to_precinct.get(ul_bc)
            precinct = self.metadata.convert_barcode_to_precinct(ul_bc)
            if precinct is None:
                message = "Form: {} Fail - no precinct found for barcode - skipped {}".format(form_path.name, ul_bc)
                logging.error(message)
                self.form_result["processing_success"] = False
                self._add_processing_comment("No precinct was found for barcode {}".format(ul_bc))
                return False
            else:
                self.precinct = precinct
                self.page = int(ll_bc[7:8])
                logging.debug("Form: {} Extracted and mapped ul_bc: {} -> Precinct: {} and ll_bc: {} -> Page:{}".format(form_path.name, ul_bc, self.precinct, ll_bc, self.page))

        else:
            #we know P and P, so check for whether or not we should flip the form
            status = check_for_flipped_form(img, form_path)
            if status:
                #we need to flip it
                img_flip = cv2.flip(img, -1) #flip both H and V, should give 180
                img = img_flip
                self.img = img
                #self.image_gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)
                #_, self.image_binary = cv2.threshold(self.image_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
                #self.image_contours, _ = cv2.findContours(self.image_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)  #CHAIN_APPROX_SIMPLE is tiny bit faster?
                
                self.visually_log_after_homology_message += "Form was FLIPPED - please inspect HOMOLOGY\n" 
                self.form_result["flipped_form"] = True 
                logging.info("Form: {} - Had to flip, but flipped Barcodes look OK - will process flipped version".format(form_path.name))     

        #resume processing with either regular or flipped form
        self.form_result["page"] = self.page
        self.form_result["precinct"] = self.precinct

        logging.info("Form: {} has precinct {} and Page {}".format(form_path.name, self.precinct, self.page))

        #load the metadata for this form
        
        img_template, choices_dict = self._load_form_metadata(self.precinct, self.page)
        
        message1 = ""
        message2 = ""

        if choices_dict is None:
            message1 = "Form: {} fails - precinct: {} page: {} has no CHOICES metadata. Not processed.".format(
                form_path.name, self.precinct, self.page)
            logging.error(message1)
            self._add_processing_comment(message1)      
        
        if img_template is None:
            message2 = "Form: {} fails - precinct: {} page: {} has no TEMPLATE metadata. Not processed.".format(
                form_path.name, self.precinct, self.page)
            logging.error(message2)
            self._add_processing_comment(message2)
        
        if choices_dict is None or img_template is None:
            self.form_result['processing_success'] = False
            return False
        
        if choices_dict['precinct'] != self.precinct or choices_dict['page'] != self.page:
            message = "Form: {} fail - form's precinct/page does not match template's precinct/page. Not processed".format(form_path.name)
            logging.error(message)
            self.form_result['processing_success'] = False
            self._add_processing_comment(message)
            return False

        #######
        # align the form against the template
        #######

        final_choices_dict = None

        #First we try the contour-finding + sliding-template approach, which is more robust than Homology-mapping
        #this model morphs the choices dictionary cX,cY to point to the form's actual locations, and only vertical aligns the form

        img_reg, M, message, final_choices_dict = align_form_and_update_CB_locations(img, img_template, choices_dict, self)

        if final_choices_dict is None or img_reg is None:
            #oops - we failed to map all template CB to the form, so now try the Homology approach

            img_reg, H, M, message = alignImages(img, img_template, choices_dict, form_path)
            if img_reg is None or H is None:
                #oops we failed both methods - mark this ballot form as un-parseable
                self.form_result['processing_success'] = False
                self._add_processing_comment("Form could not be aligned well enough to parse")
                return None
            
            else:
                #success!
                final_choices_dict = choices_dict #this method doesn't touch the choice_dict
                self.visually_log_after_homology_message += message
                self.form_result['H_matrix'] = H.tolist() #this is the WARP matrix
                self.form_result['M_matrix'] = M.tolist() #this is the affine matrix - should be applied BEFORE the Warp
        
        else:
            #success with contour/sliding-template, and did NOT need Homology
            self.visually_log_after_homology_message += message
            self.form_result['M_matrix'] = M.tolist()  #this is the AFFINE transformation for vertical align and x,y displacement
            self.form_result['H_matrix'] = None #no warp is done unless Homology is used

        #if we reach here, we have successfully mapped form to img_reg and have a good choices_dict
                
        img_gray = cv2.cvtColor(img_reg, cv2.COLOR_BGR2GRAY)
        ret, img_binary = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)

        #for each contest, score the choice boxes
        #verify precinct
        
        contests = final_choices_dict['contests']

        contest_result_status = {} #used to drive image logging report

        self.form_result["contests"] = {}

        self.form_result["contests"] = [] #list to accumulate all contests on this form
        
        for contest in contests:
            #allocate a new dataframe if this contest doesn't have one
            contest_df = data_accumulaters.setdefault(contest['contest_name'], pd.DataFrame())            
            newstatus = self.process_contest(img_reg, img_binary, contest, self.precinct, contest_df, form_path.name )
            contest_result_status[contest['contest_name']] = newstatus
        
        #add a visual log for questionable forms
        #aggregate all contests for each form

        # message = ""
        # log_it = False
        # for contest_name, newstatus in contest_result_status.items():
        #     if newstatus & FormStatus.OVERCOUNT:
        #         message += "OVER-count in: {}\n".format(contest_name)
        #         log_it = True
        #     if newstatus & FormStatus.UNDERCOUNT:
        #         message += "UNDER-count in: {}\n".format(contest_name)
        #     if newstatus & FormStatus.WRITEIN:
        #         message += "WriteIn in: {}\n".format(contest_name) 
        #         log_it = True           
        #     if newstatus & FormStatus.UNDERTHRESHOLD:
        #         message += "UNDER THRESHOLD votes in: {}\n".format(contest_name)
        #         log_it = True
        #     if newstatus & FormStatus.UNDERCOUNT and newstatus & FormStatus.UNDERTHRESHOLD:
        #         message += "WARNING - UNDERCOUNT AND UNDERTHRESHOLD - possibly a MISSED VOTE!"
        #         log_it = True
        #     if self.visually_log_after_homology_message != "":
        #         message += (self.visually_log_after_homology_message )
        #         log_it = True
        #         self.visually_log_after_homology_message = ""
                
        # #by default, we won't log form of only UNDERCOUNTs, but will log any with UNDERTHRESH or OVERCOUNT or WRITEIN
        # if log_it:
        #     self.image_logger.log_image(img_reg, None, datetime.now(), form_path, message)

        #new version - extract each contest and only log the contest

        box_color = (0,0,0)
        box_scale = 25 #from wes
        for contest_name, newstatus in contest_result_status.items():
            message = f"Precinct {precinct}\n"
            say_it = False

            if newstatus & FormStatus.OVERCOUNT:
                message += "OVER-count in: {}\n".format(contest_name)
                say_it = True

            #if newstatus & FormStatus.UNDERCOUNT:
            #    message = "UNDER-count in: {}\n".format(contest_name)

            if newstatus & FormStatus.UNDERTHRESHOLD:
                message += "UNDER THRESHOLD votes in: {}\n".format(contest_name)
                say_it = True

            if newstatus & FormStatus.WRITEIN:
                message += "WriteIn in: {}\n".format(contest_name) 
                say_it = True

            if newstatus & FormStatus.UNDERCOUNT and newstatus & FormStatus.UNDERTHRESHOLD:
                message += "WARNING - UNDERCOUNT AND UNDERTHRESHOLD - possibly a MISSED VOTE!"
                say_it = True

            if say_it:
                contest_img = extract_contest_frame(img_reg, final_choices_dict, contest_name, box_color)
                self.image_logger.log_image(contest_img, box_scale, datetime.now(), form_path, message)                

        self.form_result["processing_success"] = True
        return True

    def process_contest(self, img, img_binary, contest, precinct, contest_df, form_name):
        #extract vote score for each choice box
        #6Feb21 - add accumulator for number of under votes
        logging.debug("Form: {} - begin scoring contest: {} in Precinct:{}".format(form_name, contest["contest_name"], precinct))
        
        candidate_scores = {} #track percent marked, then assign_votes turns that into 1 or 0
        candidate_names = []
        newstatus = FormStatus(0)  #this seems bizzare. I must be missing something?
        
        this_contest_json = {}
        self.form_result['contests'].append(this_contest_json)
        
        this_contest_json["contest_name"]  = contest["contest_name"]
        this_contest_json["votes_allowed"] = contest['votes_allowed']
        this_contest_json["choices"] = []
                
        for cb in contest['choice_boxes']:
            cX = cb["cX"]
            cY = cb["cY"]
            score, ul_x, ul_y, lr_x, lr_y = score_inside_choice_box(img, img_binary, cX, cY)
            
            #encode details of score extraction to json
            this_choice_json = {}
            this_contest_json["choices"].append(this_choice_json)

            this_choice_json["score"] = score  #absolute score, percent of box filled 0-100
            this_choice_json["location_ulcx"] = ul_x
            this_choice_json["location_ulcy"] = ul_y
            this_choice_json["location_lrcx"] = lr_x
            this_choice_json["location_lrcy"] = lr_y

            logging.debug("Form: {}  - scoring candidate: {} = {}".format(form_name, cb["candidate"], score))
            candidate = cb['candidate']
            candidate_scores[candidate] = score
            candidate_names.append(candidate) #used to ensure that accumulator has all the names

            #capture candidate to json
            this_choice_json["choice_name"] = candidate
            
            #for now, mark the box and show the score on the image
            show_choice_box_on_image(img, cX, cY, (255,0,0)) #inner box in blue
            
            if score >= LOW_THRESHOLD and score < HIGH_THRESHOLD:
                color = (0,0,255) #red - signifies a possible missread
            else:
                color = (0,255,0) #green

            #capture threshold used to json
            this_choice_json["lower_threshold"] = LOW_THRESHOLD
            this_choice_json["upper_threshold"] = HIGH_THRESHOLD
            this_choice_json["marked"] = False #might get changed later, for valid vote
          
            show_score_on_image(img, cX, cY, score, color)

        newstatus, vote_getters, undervote_count = self.assign_votes(contest['votes_allowed'], candidate_scores, newstatus, form_name)
        
        #update json report with deductions about over and under counts
        this_contest_json["overvoted"]       = True if newstatus & FormStatus.OVERCOUNT else False
        
        #this_contest_json["undervoted"]      = True if newstatus & FormStatus.UNDERCOUNT else False
        if newstatus & FormStatus.UNDERCOUNT:
            #save the actual undervote count into JSON (or 0 => no undercount)
            this_contest_json['undervoted'] = int(undervote_count)
        else:
            this_contest_json['undervoted'] = 0

        this_contest_json["underthreshold"]  = True if newstatus & FormStatus.UNDERTHRESHOLD else False
        this_contest_json["validcount"]      = True if newstatus & FormStatus.VALIDCOUNT else False

        newstatus = self.accumulate_contest(contest_df, precinct, newstatus, vote_getters, candidate_names, undervote_count )
        
        #circle the vote_getters boxes with red or green circle
        for cand in vote_getters:
            #find the choice box coords - brute force search - FIX ME
            for cb in contest['choice_boxes']:
                if cb['candidate'] == cand:
                    if (newstatus & FormStatus.OVERCOUNT):
                        color = (0,0,255) #red
                    else:
                        color = (0,255,0) #green
                    draw_circle_around_choice_box(img, cb['cX'], cb['cY'], color)
                    #fix me - (Write in) won't work correctly?

        #finally, update the "marked" status for all candidate IF THIS IS A VALID vote
        #NOTE we previously marked everyone False, so only valid vote can flip to True
        if (newstatus & FormStatus.VALIDCOUNT):
            for cand in vote_getters:
                for choice in this_contest_json["choices"]:
                    if choice['choice_name'] == cand:
                        choice['marked'] = True
                 

        return newstatus

    def assign_votes(self, votes_allowed, candidate_scores, newstatus, form_name):
        # returns status and votes_cast list of candidate names with valid votes
        # 9Feb21 - accumulate and return number of undervotes per contest
        
        votes_cast = sum([1 for (cand,score) in candidate_scores.items() if score >= HIGH_THRESHOLD])
        possible_misreads = sum([1 for (cand,score) in candidate_scores.items() 
                        if score >= LOW_THRESHOLD and score < HIGH_THRESHOLD ])
        if possible_misreads > 0:
            logging.warning("Form: {} - some choices boxes were BETWEEN LOW AND HIGH Thresholds, and did not count".format(form_name))
            self._add_processing_comment("Form had votes in no-mans-land between high and low threshold")
            newstatus |= FormStatus.UNDERTHRESHOLD
        
        vote_getters = []
        undervote_count = 0

        if votes_cast > 0 and votes_cast <= votes_allowed:
            #valid votes
            newstatus |= FormStatus.VALIDCOUNT
            vote_getters = [cand for (cand, score) in candidate_scores.items() if score >= HIGH_THRESHOLD]

        if votes_cast > votes_allowed:
            #overcount invalidates ALL the votes
            newstatus |= FormStatus.OVERCOUNT
            #set vote_getters for marking the audit form tho they won't accumulate actual votes!!
            vote_getters = [cand for (cand, score) in candidate_scores.items() if score >= HIGH_THRESHOLD]
        
        #V15 - undercount means less than votes allowed, even if not zero
        #9Feb21 - each vote less than votes_allowed adds to total undercount
        if votes_cast < votes_allowed:
            newstatus |= FormStatus.UNDERCOUNT  #undercount does not invalidate good votes
            undervote_count = (votes_allowed - votes_cast)

        return newstatus, vote_getters, undervote_count
            
    def accumulate_contest(self, contest_df, precinct, newstatus, vote_getters, candidate_names, undervote_count ):
        #update the contest dataframe with the new votes
        #using dataframes to do this - may be a mistake?
        #9Feb21 - added accum of undervote_count
        
        #make sure this contest has an undercount column
        if 'under count' not in contest_df.columns:
            x = len(contest_df.columns)
            contest_df.insert(loc=x, column='under count', value=0)

        #make sure this contest has an overcount column
        if 'over count' not in contest_df.columns:
            x = len(contest_df.columns)
            contest_df.insert(loc=x, column='over count', value=0) 
            
        #make sure this precinct has a row in df
        if precinct not in contest_df.index:
            contest_df.loc[precinct] = 0
        
        #make sure all candidates are in the dataframe
        for candidate in candidate_names:
            if candidate not in contest_df.columns:
                contest_df.insert(0, column=candidate, value=0) 

        if newstatus & FormStatus.UNDERCOUNT:
            #undercount
            contest_df.at[precinct, 'under count'] += undervote_count

        if newstatus & FormStatus.OVERCOUNT:
            #overcount
            contest_df.at[precinct, 'over count'] += 1
    
        if newstatus & FormStatus.VALIDCOUNT:
            #accumulate votes only for VALIDCOUNT, not for OVERCOUNT
            for cand in vote_getters:
                #add vote(s)
                contest_df.at[precinct, cand] += 1
        
        #check for write-ins to flag for visual logger - probably belongs somewhere else
        #write in votes are accumulated as regular candidate names (set up by the template extracter code)
        for cand in vote_getters:
            if "Write In" in cand: #we can have (Write in 1) and (Write in 2)
                newstatus |= FormStatus.WRITEIN
                break #only need one to set the flag

        return newstatus

    def _load_form_metadata(self, precinct, page_number):
        #for a given precinct and page_number, check the cache for metadata, and if not there, load it

        template_name = "template_{}_{}.jpg".format(precinct, page_number)
        choices_name_json = "choices_{}_{}.json".format(precinct, page_number)
        template_path = self.path_to_template_dir / template_name
        choices_json_path = self.path_to_template_dir / choices_name_json 

        #first see if the template is in our global cache - FIX ME
        template_img = self.template_cache.get(template_name)
        if template_img is None:
            #note that imread returns None if file not found
            template_img = cv2.imread(str(template_path))
            if template_img is None:
                logging.warning(f"Form: {self.form_path} - Precinct: {self.precinct} Page: {self.page} template file:{template_path.name} NOT FOUND")
                template_img = None
            else:              
                self.template_cache[template_name] = template_img
                logging.debug("Added {} to template cache".format(template_name))
        
        #then see if the choices JSON data is in our global cache - FIX ME
        choices_dict = self.choices_json_cache.get(choices_name_json)
        if choices_dict is None:
            try:
                with open(str(choices_json_path)) as f:
                    choices_dict = json.load(f)
                    logging.debug("Added {} to choices JSON cache".format(choices_name_json))
                    self.choices_json_cache[choices_name_json] = choices_dict  
            except FileNotFoundError:
                logging.warning(f"Form: {self.form_path} - Precinct: {self.precinct} Page: {self.page} file:{choices_json_path.name} NOT FOUND")
                choices_dict = None

        return template_img, choices_dict

    def _isFormBlank(self):
        #try to find choicebox-shaped contours.
        #if not enough, conclude form is blank?
        
        #temp_gray     = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        #_, temp_binary = cv2.threshold(temp_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
        #temp_contours, _ = cv2.findContours(temp_binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        #take a subset of the image, upper half, inset to avoid barcodes
        #that should never be all devoid of choiceboxes, right?

        #these constants should go into a special FORM class for each election
        OFFSET_FROM_TOP = 100
        OFFSET_FROM_LEFT = 200
        TOP_INNER_HEIGHT = 1900
        TOP_INNER_WIDTH = 2100

        image_inner_top = self.img[OFFSET_FROM_TOP:OFFSET_FROM_TOP+TOP_INNER_HEIGHT, OFFSET_FROM_LEFT:OFFSET_FROM_LEFT+TOP_INNER_WIDTH, :]  #rows, cols, colors

        # temp_gray     = cv2.cvtColor(image_inner_top, cv2.COLOR_BGR2GRAY)
        # _, temp_binary = cv2.threshold(temp_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
        # inner_top_contours, _ = cv2.findContours(temp_binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)        
        # #we look for specific contour sizes and angles - to match the ballot's choice boxes
        # #use same parameters as the template_extractor

        # find_cb_constraints = CB_select_constraints()  #defaults most constraints, override a few locally
        # find_cb_constraints.max_cb_width = 110 #this is mean + 2SD
        # find_cb_constraints.max_cb_height = 60 #this is mean + 2SD
        # find_cb_constraints.min_cb_angle = 85.0 #these should be wide enough to accept most things
        # find_cb_constraints.max_cb_angle = 95.0
    
        #look for percentage of pixels that aren't white (e.g. where the printed words are)
        temp_gray  = cv2.cvtColor(image_inner_top, cv2.COLOR_BGR2GRAY)
        #NOTE that the binary inversion CANNOT use THRESH_OTSU since that creates lots of noise!
        _, temp_binary_even = cv2.threshold(temp_gray, 127, 255, cv2.THRESH_BINARY_INV)
        non_zero_score = cv2.countNonZero(temp_binary_even)
        area = temp_binary_even.shape[0] * temp_binary_even.shape[1] * 1.0
        percent_non_white = non_zero_score / area
        if percent_non_white < 0.01: #form is blank if there is no black ink marks
            return True
        return False

        # #are there any CB?
        # candidate_choiceboxes, num_skipped = extract_candidate_choice_box_contours(inner_top_contours, find_cb_constraints)
        # print(f"isBlank found {self.form_path.name} CB = {len(candidate_choiceboxes)} and non-white score = {score} percent = {score/area}")
        
        # plt.imshow(temp_binary_even, cmap='gray')
        # plt.show()

        # if len(candidate_choiceboxes) < 2:  #fixme - is this the right threshold? A form with one Proposition?
        #     return True
        # else:
        #     return False

    def _add_processing_comment(self, message):
        #create or add to JSON processing comment
        prior = self.form_result.get("processing_comment", "")
        if prior == "":
            self.form_result['processing_comment'] = message
        else:
            self.form_result['processing_comment'] = prior + "; " + message
        return
        
