#
# VERSION 1.5 TEMPLATE_EXTRACTOR.PY
#
# semi-automated extraction of templates from sample forms
#
# template name format is: "template_PRECINCT_PAGENUM.jpg"
# extracted JSON data goes into file named "choices_PRECINCT_PAGENUM.json"
#
#

from pyzbar import pyzbar

import sys
import cv2
import numpy as np
import re
from collections import *
from pathlib import Path
import csv
import json

import pandas as pd
from datetime import datetime
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

import logging

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [10, 10]

from image_logger import ImageLogger    #shared with scanner
from barcode_lib import *               #shared with scanner
from image_processing_lib import *      #shared with scanner
from template_ocr_lib import *          #only used by template_extractor ??
from metadata import *                  #used only by template_extractor?

#V1.5 version
class TemplateExtractor():

    def __init__(self, metadata, image_logger):

        self.metadata = metadata

        self.path_to_template = None
        self.template_image  = None      #original image as loaded by cv2.imread -> GBR colors
        self.template_image_rgb  = None  #when swtiched to RGB for tesseract
        self.template_gray = None
        self.template_binary = None
        self.contours = None     #output of cv2.findContours
        self.hierarchy = None   #output of cv2.findContours

        self.precinct = None      #will be extacted from sample form via the barcode to precinct mapping
        self.page = None
        self.ul_bc = ""   #extracted barcodes
        self.ll_bc = ""

        self.affine_matrix_M = None

        self.image_logger = image_logger #if None, no log will be written

    #main entry point for processing a form into a template
    def extract_template(self, path_to_sample_form, precinct, page):
        #trap unexpected thrown failures here (bugs!)
        try:
            logging.info(f"Form:{path_to_sample_form} - ------>>>>BEGIN TEMPLATE PROCESSING<<<<<-------")
            status, choices = self._do_extract_template(path_to_sample_form, precinct, page)
            logging.info(f"Form:{path_to_sample_form} - -------->>>>>FINISHED TEMPLATE PROCESSING<<<<<<--------")

        except:
            print("Extract Template {} - caught exception = {}".format(path_to_sample_form, sys.exc_info()[0]))
            logging.error("Form: {} - Fatal exception {} Form was NOT processed".format(path_to_sample_form.stem, sys.exc_info()[0]))
            status = False
            choices = None
        
        return status, choices
    
    #does the actual work
    def _do_extract_template(self, path_to_sample_form, precinct, page):
        
        #if we already know the precinct and page, just cache them here
        self.precinct = precinct
        self.page = page

        #sample_form is the scan from which a template will be extracted and converted to template/choices db
        self.path_to_template = path_to_sample_form
        self.template_image = cv2.imread(str(path_to_sample_form))  #color, BGR

        #first, auto-straighten form using barcodes to straighten (align with veritical)
        self.template_image, self.affine_matrix_M  = align_form_using_barcode_stripes(self.template_image, path_to_sample_form)
        
        #keep a temporary copy of the rotated image that we can mark up for visual review
        #template_image_copy = self.template_image.copy()

        #then process as usual...
        self.template_gray        = cv2.cvtColor(self.template_image, cv2.COLOR_BGR2GRAY) #gray
        self.template_image_rgb   = cv2.cvtColor(self.template_image, cv2.COLOR_BGR2RGB) #needed for tesseract
        _, self.template_binary   = cv2.threshold(self.template_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)

        #get barcodes for precinct and page, unless we already have them passed in from main program
        if self.precinct is None or self.page is None:
            self.ul_bc, self.ll_bc = extract_bar_codes(self.template_image, path_to_sample_form)
            logging.info("Form: {} Extracted BAR CODES WERE: {} {}".format(path_to_sample_form.stem, self.ul_bc, self.ll_bc))
            self.precinct = self.metadata.convert_barcode_to_precinct(self.ul_bc)
            self.page = int(self.ll_bc[7:8])
            logging.info(f"Form: {path_to_sample_form.stem} extracted precinct={self.precinct} page={self.page}")

        if self.precinct is None:
            print("Fatal error - no precinct found for barcode: {}\n\n".format(self.ul_bc))
            logging.error("Form: {} FATAL error - no precinct found for barcode: {}. SKIPPING".format(path_to_sample_form.stem, self.ul_bc))
            return False, None

        #prepare the file names for where this template and metadata will go:
        #self.path_to_template_file = self.path_to_metadata_dir / "template_{}_{}.jpg".format(self.precinct, self.page)
        #self.path_to_choices_file = self.path_to_metadata_dir / "choices_{}_{}.json".format(self.precinct, self.page)
            
        #now find contours - use OTSU thresholding and BINARY inversion (form background = black)
        ###_, self.template_binary = cv2.threshold(self.template_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
        
        #and extract all contours using RETR_TREE method
        ###self.contours, self.hierarchy = cv2.findContours(self.template_binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        #we look for specific contour sizes and angles - to match the ballot's choice boxes
        
        #find_cb_constraints = CB_select_constraints()  #defaults most constraints, override a few locally
        #find_cb_constraints.max_cb_width = 110 #this is mean + 2SD
        #find_cb_constraints.max_cb_height = 60 #this is mean + 2SD
        #find_cb_constraints.min_cb_angle = 85.0 #these should be wide enough to accept most things
        #find_cb_constraints.max_cb_angle = 95.0
    
        #first, find everything that looks like a choice box - this has to work well, so use a CLEAN TEMPLATE!
        #this routine replaced by better approach using botb contours and template-matching
        ###candidate_choiceboxes, num_skipped = extract_candidate_choice_box_contours(self.contours, find_cb_constraints)

        candidate_choiceboxes = find_all_choiceboxes_using_contour_and_template_match(self)
        num_skipped = 0

        #reject empty forms
        if len(candidate_choiceboxes) <= 0:
            print(f"Warning - no choiceboxes found for form {path_to_sample_form.stem} - skipping")
            logging.warn(f"Warning - form {path_to_sample_form.stem} has no choiceboxes - skipping {path_to_sample_form.stem}")
            return False, None

        #reject any form that skipped choiceboxes based on the mean+2SD rule defined above
        #this can't happen anymore?
        if num_skipped > 0:
            print(f"Warning - skipped choiceboxes = {num_skipped} on {path_to_sample_form.stem} - skipping this one")
            logging.warn(f"Warning - form {path_to_sample_form.stem} had {num_skipped} skipped choiceboxes - skip this one ")
            return False, None            

        #use choice box x,y locations to deduce columns, and clean up messy xC centers
        #no, we have already deduced columns in the choicebox finder code
        ###sorted_results = self._deduce_and_assign_columns(candidate_choiceboxes)

        #no, we don't need to do this - actually could have caused alignement problems
        ##sorted_results = self._clean_up_choice_box_centers(sorted_results)


        #most of the work happens here - multiple passes of OCR against ChoiceBox locations to parse the form
        sorted_results = candidate_choiceboxes #patching together old and new code

        choiceboxes = extract_candidates_and_contests_using_CB_and_metadata(self.template_image, self.template_image_rgb, 
                                       sorted_results, self.metadata, self.path_to_template)
        
        cb_df = \
            pd.DataFrame([(cb.cnum, cb.area, cb.cX, cb.cY, cb.w, cb.h, cb.angle, cb.column, cb.contest_num, cb.candidate_name[0:30], \
            cb.contest_name[0:30], cb.votes_allowed ) for cb in choiceboxes], \
            columns=['cnum', 'area', 'cX', 'cY', 'w', 'h','angle', 'column', 'contest#','candidate', 'contest', 'votes-allowed'])
        
        print(f"RESULTS for form: {self.path_to_template.name}")
        print(cb_df)

        #return that we found possibly valid choiceboxes
        return True, choiceboxes

    def validate_template(self, choiceboxes):
        #uses internal (pre-JSON) data to try to find any missing or inconsistent data
        #assumes choiceboxes are sorted by contest_number ascending
        #returns ??
        all_good = True
        bad_choiceboxes = set()
        
        if self.precinct is None or self.page is None:
            all_good = False
            logging.error(f"Form: {self.path_to_template} Validation Error - missing Precinct or Page")
        
        #validate that all CB got filled with something
        #note cannot guarantee that a CB was never parsed, unfortunately!
        for count, cb in enumerate(choiceboxes):
            if cb.column == -1 or cb.contest_num == -1 or cb.candidate_name in (None, "", "[YES]", "[NO]", \
                    "[BONDSYES]", "[BONDSNO]","[EMPTY]") or cb.votes_allowed == -1 or  \
                    cb.contest_type not in  ["regular", "proposition"]  or   \
                    cb.contest_name in ("", None, "[UNKNOWN]", "[PROP-OR-MEASURE]", "[UNKNOWN CONTEST NAME]"):
                logging.error(f"Form: {self.path_to_template} Validation Error - Choicebox {count} incomplete!")
                all_good = False
                bad_choiceboxes.add(count) #note these are zero based!

        #now validate regular contests against metadata
        cur_contest_num = -1
        for count, cb in enumerate(choiceboxes):
            if cb.contest_type != "regular":
                continue
            if cb.contest_num != cur_contest_num:
                cur_contest_num = cb.contest_num
                contest_name = cb.contest_name
                
                #validate that contest is in this precinct
                status = self.metadata.contest_is_in_precinct(contest_name, self.precinct)
                if not status:
                    logging.error(f"Form: {self.path_to_template} Validation Error - Contest {contest_name} not in precinct!")
                    all_good = False
                    bad_choiceboxes.add(count)

                #validate that all contest_names are the same for this contest_num
                #this ought to catch overly aggressive OCR assignment of candidate, since that could bring wrong contest !!
                #tricky - for now just warn that there is a problem and flag each CB
                candidate_pointer = count
                candidate_contest_problem = False
                while (candidate_pointer < len(choiceboxes) and choiceboxes[candidate_pointer].contest_num == cur_contest_num):
                    if choiceboxes[candidate_pointer].contest_name != cb.contest_name: #use first candidate as correct????
                        bad_choiceboxes.add(candidate_pointer)
                        candidate_contest_problem = True
                    candidate_pointer += 1
                if candidate_contest_problem:
                    logging.error(f"Form: {self.path_to_template} Validation Error - Candidates don't all belong in same Contest: {contest_name}")
                    all_good = False                 
                
                #validate that each non-writein candidate is in this contest:
                for cand_cb in choiceboxes[count:]:
                    if cand_cb.contest_num != cur_contest_num:
                        break
                    cand_name = cand_cb.candidate_name
                    contest_name = cand_cb.contest_name
                    if cand_name == "Write-in" and not self.metadata.is_writein_allowed(contest_name):
                        logging.error(f"Form: {self.path_to_template} Validation Error - Write-in not allowed for Contest {contest_name}!")
                        all_good = False
                        bad_choiceboxes.add(count)
                    else:
                        continue    #writein was good, skip other tests this CB                        
                    if not self.metadata.candidate_is_valid(cand_name):
                        logging.error(f"Form: {self.path_to_template} Validation Error - Candidate {cand_name} is not valid!")
                        all_good = False
                        bad_choiceboxes.add(count)
                    if not self.metadata.candidate_is_in_contest(cand_name, contest_name):
                        logging.error(f"Form: {self.path_to_template} Validation Error - Candidate {cand_name} is not in Contest {contest_name}!")
                        all_good = False
                        bad_choiceboxes.add(count)

        #now validate propositions and measures
        cur_contest_num = -1
        for count, cb in enumerate(choiceboxes):
            if cb.contest_type != "proposition":
                continue
            if cb.contest_num != cur_contest_num:
                cur_contest_num = cb.contest_num
                contest_name = cb.contest_name
                if "Proposition" not in contest_name:
                    continue #fixme add Measures

                #validate that this Prop is in this precinct
                status = self.metadata.contest_is_in_precinct(contest_name, self.precinct)
                if not status:
                    logging.error(f"Form: {self.path_to_template} Validation Error -  Proposition {contest_name} not in precinct!")
                    all_good = False
                    bad_choiceboxes.add(count)

                #validate that this Prop has a pair of candidates (yes, no, bonds yes, bonds no) both in contest
                first = cb
                if not self.metadata.candidate_is_in_contest(first.candidate_name, contest_name):
                    logging.error(f"Form: {self.path_to_template} Validation Error - Proposition {contest_name} has bad Affirmative choice!")
                    all_good = False
                    bad_choiceboxes.add(count)

                if count+1 > len(choiceboxes):
                    logging.error(f"Form: {self.path_to_template} Validation Error - Proposition {contest_name} missing a Negative choice!")
                    all_good = False
                    bad_choiceboxes.add(count) #what to do here?                    
                
                second = choiceboxes[count+1] 
                if not self.metadata.candidate_is_in_contest(second.candidate_name, contest_name):
                    logging.error(f"Form: {self.path_to_template} Validation Error - Proposition {contest_name} has bad Negative choice!")
                    all_good = False
                    bad_choiceboxes.add(count+1)

        return all_good, bad_choiceboxes


    def annotate_template(self, path_to_form, choices):
        #paint all the data from choiceboxes onto the form, return painted image for caller to display
        #envision use as verification step?
        #choices represents the JSON data, but caller has converted to python dictionary

        #load the form as BGR, since that's what CV2 likes
        original_image = cv2.imread(str(path_to_form))
        #painted_image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        #first, auto-straighten form using barcodes to straighten (align with veritical)
        #V1.5 - we now apply the alignment using M-matrix from choices file, since we want to verify that it was OK 
        #painted_image = align_form_using_barcode_stripes(painted_image, path_to_form)

        m_data_points = choices.get('M_matrix')
        if m_data_points:
            M = np.array(m_data_points)
            painted_image = apply_affine_to_image(original_image, M)
        else:
            logging.warning(f"Template {path_to_form.stem} did not have M affine transformation matrix")
            painted_image = original_image
        
        #first paint precinct and page numbers at top
        show_precinct_page_on_image(painted_image, choices['precinct'], choices['page'])

        for contest in choices['contests']:
            #fix me - we need better way to flag Propositions!
            if "Proposition" in contest['contest_name'] or "Measure" in contest['contest_name']:
                painted_image = self._paint_proposition_header_and_choicebox_names(painted_image, contest)
            else:
                painted_image = self._paint_contest_header_and_choicebox_names(painted_image, contest)

        
        #Leave in BGR form, as most display propgrams can figure that out (not imshow() tho!)
        return painted_image

    def get_straightened_image(self):
        #this should be the reference straightened but UNMARKED image
        return self.template_image

    def _paint_contest_header_and_choicebox_names(self, image, contest):
        #contest is the json-sourced dictionary for this contest
        #get choice boxes to sort (need the top one)
        cb_list = [ cb for cb in contest['choice_boxes'] ]
        cb_list = sorted(cb_list, key=lambda cb:(cb['cY']), reverse=False)
        top_cb = cb_list[0]

        #paint header above top_cb by guesstimate
        show_contest_name__and_votes_allowed_on_image(image, top_cb['cX'], top_cb['cY'], 
            contest['contest_name'], contest['votes_allowed'])

        #show names
        for cb in cb_list:
            self._paint_name_on_image(image, cb['cX'], cb['cY'], cb['candidate'] )
            #paint inside CB itself
            show_choice_box_on_image(image, cb['cX'], cb['cY'], (255,0,0)) #color is (BGR)

        return image

    def _paint_proposition_header_and_choicebox_names(self, image, contest):
        #contest is the json-sourced dictionary for this contest
        #get choice boxes to sort (need the top one)
        cb_list = [ cb for cb in contest['choice_boxes'] ]
        cb_list = sorted(cb_list, key=lambda cb:(cb['cY']), reverse=False)
        top_cb = cb_list[0]

        #paint header above top_cb by guesstimate
        show_proposition_name_on_image(image, top_cb['cX'], top_cb['cY'], contest['contest_name'])

        #show names
        for cb in cb_list:
            self._paint_name_on_image(image, cb['cX'], cb['cY'], cb['candidate'] )
            #paint inside CB itself
            show_choice_box_on_image(image, cb['cX'], cb['cY'], (255,0,0)) #color is (BGR)

        return image

    #fix me - probably should be moved to image_processing_lib?
    def _paint_name_on_image(self, img, cX, cY, name):
        ul_x, ul_y, lr_x, lr_y = calc_choice_box_scoring_coords(cX, cY)
        h2 = int(ACTUAL_CHOICE_BOX_HEIGHT / 2) #rows -> y axis

        max = 35
        display = f"{name}"
        if len(display) > max:
            h_extra = int( (len(display) - max)/2 )
            mid = int(len(display)/2)
            show = display[0:mid-h_extra] + " ... " + display[mid+h_extra:]
        else:
            show = display
        
        cv2.putText(img, show, (lr_x + 300, ul_y + h2), 
                    cv2.FONT_HERSHEY_SIMPLEX,1.2, (0, 255, 0), 2)
        return        


    #new for V1.5
    #NO LONGER NEEDED 
    def _deduce_and_assign_columns(self, results):
        #gets a list of choiceboxes. There can be from 1 to 3 columns.
        #figure out how many columns there are (from cX values) and assign CB to columns in order
        #assumes a new column is when two xC values are more than width of CB apart
        params = CB_select_constraints() #theres got to be a better way...
        cb_external_width = params.inner_cb_width + (2 * params.cb_line_width)

        #sort cols by cX
        cb_sort_by_cx = sorted(results, key=lambda cb: cb.cX, reverse=False) #ascending
        cur_col = 1 #first col will be #1
        col_counts = np.zeros(4, dtype=np.int)
        col_counts[cur_col] += 1 #first one
        cur_cb = cb_sort_by_cx[0]
        cur_cb.column = cur_col
        
        for next_cb in cb_sort_by_cx[1:]:
            if next_cb.cX > (cur_cb.cX + cb_external_width):
                cur_col += 1
                next_cb.column = cur_col
                col_counts[cur_col] += 1
                cur_cb = next_cb
            else:
                next_cb.column = cur_col
                col_counts[cur_col] += 1
        
        logging.info(f"form {self.path_to_template.name} has {cur_col} columns with counts {col_counts[1]} {col_counts[2]} {col_counts[3]}")
        
        #sort CB list into ascending order, by column # and cY
        sorted_results = sorted(cb_sort_by_cx, key=lambda cb: (cb.column, cb.cY)) #both ascending
        #print(f"INFO - sorted CB = {sorted_results}")
        
        return sorted_results
    
    #V1.5 - modified to use assigned columns
    #NO LONGER USED - WAS A BAD IDEA anyway
    def _clean_up_choice_box_centers(self, results):
        #replace the noisy choice box centers with the median of all the centers, for x
        #not sure there's any way to clean up Y?

        #probably should re-write this as 2D numpy array
        x_col_1 = [ cb.cX for cb in results if cb.column == 1 ]
        x_col_2 = [ cb.cX for cb in results if cb.column == 2 ]
        x_col_3 = [ cb.cX for cb in results if cb.column == 3 ] #assumes no more than 3 columns!
        
        x_col_1_med = int(np.median(np.array(x_col_1)))
        x_col_2_med = int(np.median(np.array(x_col_2))) if len(x_col_2) > 0 else 0.0
        x_col_3_med = int(np.median(np.array(x_col_3))) if len(x_col_3) > 0 else 0.0
        
        for cb in results:
            if cb.column == 1:
                cb.cX = x_col_1_med
            elif cb.column == 2:
                cb.cX = x_col_2_med
            else:
                cb.cX = x_col_3_med
                
        return results

    def convert_to_json(self, choiceboxes, scan_date, operator):
        #converts the choice box structure to JSON, but does not write it out!

        top = {'precinct': self.precinct, 'page':self.page, 'ul_barcode': self.ul_bc, 'll_barcode': self.ll_bc, 
            'scan_date':scan_date, 'operator': operator}

        #V15 - add affine M matrix, to remember how this template was adjusted
        top['M_matrix'] = self.affine_matrix_M.tolist()
        
        contests = []
        cur_contest_num = -1

        for cb in choiceboxes:
            if cb.contest_num != cur_contest_num:
                #new contest
                cur_contest_num = cb.contest_num
                new_contest = {}
                new_contest['contest_name'] = cb.contest_name
                new_contest['votes_allowed'] = cb.votes_allowed
                new_contest['column'] = cb.column
                
                contests.append(new_contest)
                
                choices = []
                for cb2 in choiceboxes:
                    if cb2.contest_num == cur_contest_num:
                        new_choice = {}
                        new_choice['cX'] = cb2.cX
                        new_choice['cY'] = cb2.cY
                        new_choice['candidate'] = cb2.candidate_name
                        choices.append(new_choice)

                new_contest['choice_boxes'] = choices

        top['contests'] = contests
        return json.dumps(top, sort_keys=False, indent=2)


