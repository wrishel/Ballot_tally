#library routines for template extraction from sample form using mostly OCR tools
#V1.5

from numpy.core.numeric import True_
import pytesseract
import cv2
import numpy as np
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

import logging

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [10, 10]


#new for V1.5
def extract_candidates_and_contests_using_CB_and_metadata(img, img_rgb, results, metadat, path_to_template):
    #new for V1.5 - we have CB's in order and in columns.
    #multiple pass approach.

    cb_sorted = sorted(results, key = lambda cb: (cb.column, cb.cY))
    
    ####
    #first pass - complete all 100% match for candidates, contests
    #    and flag all potential write-ins as [EMPTY] 
    #    flag non-matched candidate names as [NOMATCH] 
    #    also flag potential yes/no as [YES] [NO]
    #####
    
    #--psm 7 = Treat the image as a single text line (works best for yes/no?)
    #--oem 3 = LSTM version
    
    #ocr_params = r'--oem 3' #force LSTM, use default parse logic (tested one line and it didn't work well)
    cb_num = 0
    
    #try smoothing the image - seems to improve most of the OCR results
    img_rgb_blur = cv2.medianBlur(img_rgb,3)

    for cb in cb_sorted:
        cb_num += 1

        #extract sliver of image focused on where first line of candidate name is
        #try multiple types of OCR 
        #but first, see if we can defer processing the blank "write-in" boxes - cause HUGE noise in OCR
        score = score_inside_candidate_name_next_to_cb(img_rgb_blur, cb.cX, cb.cY)
        logging.debug(f"Form:{path_to_template.name} Pixel non-zero score for candidate name box = {score}")
        if score <0.1:
            logging.debug(f"Form:{path_to_template.name} pixel score will be classified as EMPTY - possible write-in")
            cb.candidate_name = "[EMPTY]" #probably a write-in, will check below
            cb.contest_name = "" #null is flag used in assigning write-ins, see below
            cb.contest_type = "regular"
            continue

        #initial search for yes/no/bonds
        whitelist_letters = '''\\ YesNoBnd'''
        n1, n2 = extract_and_OCR_for_whitelist(img_rgb_blur, cb.cX, cb.cY, whitelist_letters, True)
        logging.debug(f"Form:{path_to_template.name} initial OCR for possible yes/no/bonds returns: |{n1}|")

        #initial parse - pick off a potential yes/no and Bonds Yes / Bonds No
        status = search_for_good_enough_match("Yes", [n1, n2], 85)
        if status:
            cb.candidate_name = "[YES]"
            continue
        status = search_for_good_enough_match("Bonds Yes", [n1, n2], 85)
        if status:
            cb.candidate_name = "[BONDSYES]"
            continue

        status = search_for_good_enough_match("No", [n1, n2], 85)
        if status:
            cb.candidate_name = "[NO]"
            continue
        status = search_for_good_enough_match("Bonds No", [n1, n2], 85)
        if status:
            cb.candidate_name = "[BONDSNO]"
            continue
        
        #try whitelist search for candidate names - uppercase plus some punct and space
        #note the double escape for the " character, due to python's use of shlex eats first one
        #candidate names do well on regular OCR so skip the inverted tries
        whitelist_letters = '''\\ \\-\\'ABCDEFGHIJKLMNOPQRSTUVWXYZ.\\"'''
        n1, n2 = extract_and_OCR_for_whitelist(img_rgb_blur, cb.cX, cb.cY, whitelist_letters, True)
        logging.debug(f"Form:{path_to_template.name} Whitelisted OCR for candidate name gets |{n1}| and |{n2}|")
        #this should be a regular candidate - get >90% match if possible (first result)
        #(candidate, contest, score) = metadat.get_contests_for_candidate(n1)[0]
        (first_candidate, full_candidate, contest, score) = metadat.fuzzy_match_first_candidate(n1)[0]
        if score >= 80:
            logging.debug(f"Form:{path_to_template.name} Success - best fuzzy candidate name match = |{first_candidate}| score:{score}")
            #OK - high quality match, regular candidate name, at least for first line of candidate
            cb.candidate_name = full_candidate  #the full formal name from metadata
            cb.contest_name = contest  #full contest name from metadata
            cb.contest_type = "regular"
            continue
        else:
            logging.debug(f"Form:{path_to_template.name} Failed candidate match. Best was |{first_candidate}| score:{score} - flagging name as EMPTY")
            cb.candidate_name = "[EMPTY]" #probably a write-in, will check below
            cb.contest_name = "" #null is flag used in assigning write-ins, see below
            cb.contest_type = "regular"
            continue

        #else consider this to be probably a write-in, for processing later on
        #cb.candidate_name = "[EMPTY]"

    #####
    #pass 2 - resolve Yes/No proposition and measure "candidates"
    #treat these as mandatory pairs, starting with either the Yes or the No
    #if either one is present, force the other one to be there, even if missing
    #####
    
    cb_list = cb_sorted.copy()
    cur_pos = 0
    
    while True:
        if cur_pos + 1 >= len(cb_list):
            break
            
        first_cb = cb_list[cur_pos]
        
        if first_cb.candidate_name == "[YES]":
            
            other_cb = cb_list[cur_pos + 1]

            if other_cb.candidate_name == "[NO]":
                #we have a good Yes,No pair
                logging.debug(f"Form:{path_to_template.name} Found a good YES/NO pair")
                first_cb.candidate_name = "Yes"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate_name = "No"
                other_cb.contest_name = "[PROP-OR-MEASURE]"
            else:
                logging.debug(f"Form:{path_to_template.name} FORCING a No to match the found yes")
                first_cb.candidate_name = "Yes"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate_name = "No"
                other_cb.contest_name = "[PROP-OR-MEASURE]"                    
            
            first_cb.contest_type = "proposition"
            first_cb.votes_allowed = 1
            other_cb.contest_type = "proposition"    
            other_cb.votes_allowed = 1    
            cur_pos += 2 #skip to next search point"
 
        elif first_cb.candidate_name == "[NO]":
            #see if we can resolve the full No and find a matching Yes
            other_cb = cb_list[cur_pos - 1]
            if other_cb.candidate_name == "[YES]":
                logging.debug(f"Form:{path_to_template.name} Found a good NO/YES pair")
                #we have a good No, Yes pair
                first_cb.candidate = "No"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate = "Yes"
                other_cb.contest_name = "[PROP-OR-MEASURE]"
            else:
                logging.debug(f"Form:{path_to_template.name} FORCING a Yes to match the found no")
                first_cb.candidate = "No"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate = "Yes"
                other_cb.contest_name = "[PROP-OR-MEASURE]"              
           
            first_cb.contest_type = "proposition"
            first_cb.votes_allowed = 1
            other_cb.contest_type = "proposition"    
            other_cb.votes_allowed = 1    
            cur_pos += 2 #skip to next search point"

        elif first_cb.candidate_name == "[BONDSYES]":
            
            other_cb = cb_list[cur_pos + 1]

            if other_cb.candidate_name == "[BONDSNO]":
                logging.debug(f"Form:{path_to_template.name} Found a good BONDSYES / BONDSNO pair")
                first_cb.candidate_name = "Bonds Yes"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate_name = "Bonds No"
                other_cb.contest_name = "[PROP-OR-MEASURE]"
            else:
                logging.debug(f"Form:{path_to_template.name} FORCING a Bonds No to match the found Bond yes")
                first_cb.candidate_name = "Bonds Yes"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate_name = "Bonds No"
                other_cb.contest_name = "[PROP-OR-MEASURE]"                    
            
            first_cb.contest_type = "proposition"
            first_cb.votes_allowed = 1
            other_cb.contest_type = "proposition"    
            other_cb.votes_allowed = 1              
            cur_pos += 2 #skip to next search point"
 
        elif first_cb.candidate_name == "[BONDSNO]":
            other_cb = cb_list[cur_pos - 1]
            if other_cb.candidate_name == "[BONDSYES]":
                logging.debug(f"Form:{path_to_template.name} Found a good Bonds NO / Bonds YES pair")
                first_cb.candidate = "Bonds No"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate = "Bonds Yes"
                other_cb.contest_name = "[PROP-OR-MEASURE]"
            else:
                logging.debug(f"Form:{path_to_template.name} FORCING a Bonds Yes to match the found Bonds No")
                first_cb.candidate = "Bonds No"
                first_cb.contest_name = "[PROP-OR-MEASURE]"
                other_cb.candidate = "Bonds Yes"
                other_cb.contest_name = "[PROP-OR-MEASURE]"              

            first_cb.contest_type = "proposition"
            first_cb.votes_allowed = 1
            other_cb.contest_type = "proposition"    
            other_cb.votes_allowed = 1            
            cur_pos += 2        
        
        else:
            cur_pos += 1
        
    #####
    #pass 3 - assign contest numbers
    #####
    
    cb_sorted = assign_contest_numbers(cb_sorted)

    #####
    #pass 4 - capture write-ins using a set of expanded OCR queries looking for phrase "write in" below line
    #####
    
    #remember the previous contest name to assign to one or two optional write-in CBs
    prior_contest_name = "[UNKNOWN]"
    prev_write_in_contest_num = -1
    write_in_count = 0

    for cb in cb_sorted:

        if len(cb.contest_name) > 0:
            prior_contest_name = cb.contest_name
            
        if cb.candidate_name == "[EMPTY]":

            name_block, name_block_binary = extract_and_OCR_writein(img_rgb_blur, cb.cX, cb.cY)
            logging.debug(f"Form:{path_to_template.name} OCR for phrase 'writein' returns: |{name_block}| and |{name_block_binary}|")
            #seems like common result is "Write-in xxxxxxxx" where xxxx is random junk
            #so lets first try a direct hit, and then fall back to broader search
            #we only come here if this is HIGHLY likely to be a write-in so we can be generous
            if name_block.find("Writ") > -1:
                status = True
            else:
                status = search_for_good_enough_match("Write-in", [name_block, name_block_binary], 50)
            
            if status:

                if prev_write_in_contest_num == cb.contest_num:
                    write_in_count += 1 
                else:
                    write_in_count = 1 #first write in == 1
                    prev_write_in_contest_num = cb.contest_num

                cb.candidate_name = f"(Write In {write_in_count})"
                cb.contest_name = prior_contest_name  #writeins belong to contest above
                cb.contest_type = "regular"
            else:
                cb.candidate_name = "[UNKNOWN CANDIDATE NAME]"
                cb.contest_name = "[UNKNOWN CONTEST NAME]"
                cb.contest_type = "regular"


    
    #####
    #pass 5 - use contour analysis to extract REGULAR contest headers to pull of "votes_allowed" data
    #####

    cur_contest = -1
    cb_list = cb_sorted.copy()
    target_cb_num = -1
    while len(cb_list) > 0:
        cb = cb_list.pop(0)
        target_cb_num += 1
        if cb.contest_num != cur_contest and cb.contest_type == "regular":
            #process this regular contest
            #top_cb = cb
            sub_image = extract_regular_contest_header_using_cb_offsets(img_rgb_blur, cb_sorted, target_cb_num)
            #plt.imshow(sub_image)
            #plt.show()
            contest_name, votes_allowed = extract_regular_contest_name_and_votes_with_OCR(sub_image)
            if (cb.contest_name != contest_name):
                logging.warning("Form:{} WARNING metadata-based contest name {} does not match OCRd contest name {}".format( \
                    path_to_template.name, cb.contest_name, contest_name))
            cb.votes_allowed = int(votes_allowed)
            #update the other rows in the choice-box array for this contest with this votes_allowed number
            for cb2 in cb_sorted:
                if cb2.contest_num == cb.contest_num:
                    cb2.votes_allowed = cb.votes_allowed
            cur_contest = cb.contest_num
        else:
            continue

    #####
    #pass 6 - use contour analysis to extract proposition/measure headers to identify the proposition/measure
    #####

    cur_contest = -1
    cb_num = -1
    cb_list = cb_sorted.copy()
    while len(cb_list) > 0:
        cb = cb_list.pop(0)
        cb_num += 1
        if cb.contest_num != cur_contest and cb.contest_type == "proposition":
            #process this proposition or measure
            top_cb = cb
            #sub_image = extract_proposition_contest_header_image(img_rgb_blur, top_cb.cX, top_cb.cY)
            sub_image = extract_proposition_or_measure_header_using_cb_offsets(img_rgb_blur, cb_sorted, cb_num)
            prop_or_meas_name, isMeasure = extract_proposition_or_measure_contest_identifier_with_OCR(sub_image, metadat)
            if isMeasure:
                #cb.contest_name = metadat.fuzzy_match_measure_name(temp_name)
                cb.contest_name = prop_or_meas_name
                #cover the "no" option as well
                next_cb = cb_list.pop(0)
                cb_num += 1
                next_cb.contest_name = prop_or_meas_name
                cur_contest = cb.contest_num
            else:
                #so far, propositions are only named by their number??
                #fixme - needs some prop text to make this more robust!
                cb.contest_name = prop_or_meas_name
                #cover the "no" option as well
                next_cb = cb_list.pop(0)
                cb_num += 1
                next_cb.contest_name = prop_or_meas_name
                cur_contest = cb.contest_num
        else:
            continue
    
    return cb_sorted

#some constants used for template extraction
#similar constants in ballot scanner - may be slightly different for sensitivity/specificity tradeoffs
#fixme - resolve these!
TMPLT_ACTUAL_CHOICE_BOX_WIDTH = 100 #what about thickness of lines??
TMPLT_ACTUAL_CHOICE_BOX_HEIGHT = 54

#TMPLT_COL_SPLIT_X_VALUE = 1000

TMPLT_X_OFFSET_FOR_NAME = 6  #propositions
TMPLT_Y_OFFSET_FOR_NAME = 10
TMPLT_WIDTH_NAME = 900   # fixme - make this func of number of columns! was 600
TMPLT_HEIGHT_NAME =70 #propositions


#new for V1.5
#not used anymore?
def extract_and_OCR_name(img_rgb, cX, cY, ocr_params):
    
    #fix me - should these be adjusted for column width? Number of columns???
    
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    y_up = int(cY - (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) - (TMPLT_HEIGHT_NAME / 2) + TMPLT_Y_OFFSET_FOR_NAME)
    y_dn = y_up + TMPLT_HEIGHT_NAME
    
    name_image = img_rgb[ y_up:y_dn, x_left:x_right, :]
    #name_gray = cv2.medianBlur(name_image,5)
    
    name = pytesseract.image_to_string(name_image, lang='eng', config=ocr_params)
    return name #let caller apply filtering, etc

#new for V1.5
def extract_and_OCR_writein(img_rgb, cX, cY):
    #see if we can find the words Write-in below the dotted line
    #fix me - should these be adjusted for column width? Number of columns???
    #we try several OCR methods and return several parses
    
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    
    y_up = int(cY + (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) + 15)
    y_dn = y_up + TMPLT_HEIGHT_NAME
    
    name_image = img_rgb[ y_up:y_dn, x_left:x_right, :] #a view
    
    #make a binary image for another test
    #NOTE - better results with NON-inverted binary - black letters on white background
    binary_img = np.copy(name_image)
    binary_img = cv2.cvtColor(binary_img, cv2.COLOR_RGB2GRAY)
    
     #occasionally works better with a manual threshold instead of OTSU => less noise?
    #_, binary_img = cv2.threshold(binary_img, 200, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    _, binary_img = cv2.threshold(binary_img, 175, 255, cv2.THRESH_BINARY)

    #plt.imshow(name_image)
    #plt.show()
    #plt.imshow(binary_img, cmap='gray')
    #plt.show()
    
    #this white list works pretty well so drop the two "single line" tests
    white_list_config = r'-c tessedit_char_whitelist=Write-in --psm 6'

    name_block = pytesseract.image_to_string(name_image, lang='eng', config=white_list_config) #standard block
    name_block_binary = pytesseract.image_to_string(binary_img, lang='eng', config=white_list_config) #standard block  BEST ALTERNATIVE??
    
    return name_block.strip(), name_block_binary.strip() #let caller decide

def OCR_name_multiple_methods_find_good_enough_match(img_rgb, cX, cY, find_me, threshold ):
    #combines several of the below methods to be more efficient with slow OCR
    #keep trying methods until match criteria is met, then return status
    
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    y_up = int(cY - (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) - (TMPLT_HEIGHT_NAME / 2) + TMPLT_Y_OFFSET_FOR_NAME)
    y_dn = y_up + TMPLT_HEIGHT_NAME
    
    name_image = img_rgb[ y_up:y_dn, x_left:x_right, :] #a view

    #first try standard OCR parameters on regular RGB image
    name_block = pytesseract.image_to_string(name_image, lang='eng', config=r'') #standard block OCR
    status = search_for_good_enough_match(find_me, [name_block], threshold)
    if status:
        return True

    #then try "line mode" OCR parameters on regular RGB image
    name_line = pytesseract.image_to_string(name_image, lang='eng', config=r'--psm 7') #one line OCR
    status = search_for_good_enough_match(find_me, [name_line], threshold)
    if status:
        return True   

    #then make a binary image for an alternate test
    #NOTE - get better results with NON-inverted binary - black letters on white background
    binary_img = np.copy(name_image)
    binary_img = cv2.cvtColor(binary_img, cv2.COLOR_RGB2GRAY)
    _, binary_img = cv2.threshold(binary_img, 200, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

    name_block_binary = pytesseract.image_to_string(binary_img, lang='eng', config=r'') #standard block binary 
    status = search_for_good_enough_match(find_me, [name_block_binary], threshold)
    if status:
        return True 

    name_line_binary =  pytesseract.image_to_string(binary_img, lang='eng', config=r'--psm 7') #single line binary
    status = search_for_good_enough_match(find_me, [name_line_binary], threshold)
    if status:
        return True

    return False #all methods failed :( 
    
#new for V1.5
def extract_and_OCR_multiple_methods(img_rgb, cX, cY):
    #reading candidate and yes/no space
    #try multiple methods and return all answers to caller
    #fix me - should these be adjusted for column width? Number of columns???
    #fix me - we could stop trying OCRs if we knew we had a match!
    
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    y_up = int(cY - (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) - (TMPLT_HEIGHT_NAME / 2) + TMPLT_Y_OFFSET_FOR_NAME)
    y_dn = y_up + TMPLT_HEIGHT_NAME
    
    name_image = img_rgb[ y_up:y_dn, x_left:x_right, :] #a view
    
    #make a binary image for an alternate test
    #NOTE - better results with NON-inverted binary - black letters on white background
    binary_img = np.copy(name_image)
    binary_img = cv2.cvtColor(binary_img, cv2.COLOR_RGB2GRAY)
    _, binary_img = cv2.threshold(binary_img, 200, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    
    #plt.imshow(name_image)
    #plt.show()
    #plt.imshow(binary_img, cmap='gray')
    #plt.show()
    
    name_line =  pytesseract.image_to_string(name_image, lang='eng', config=r'--psm 7') #single line
    name_block = pytesseract.image_to_string(name_image, lang='eng', config=r'') #standard block
    name_line_binary =  pytesseract.image_to_string(binary_img, lang='eng', config=r'--psm 7') #single line
    name_block_binary = pytesseract.image_to_string(binary_img, lang='eng', config=r'') #standard block  
    
    return name_block.strip(), name_line.strip(), \
        name_line_binary.strip(), name_block_binary.strip() #let caller decide

#V1.5 - optimize to leverage whitelist method
def extract_and_OCR_for_whitelist(img_rgb, cX, cY, whitelist_letters, skip_alternatives):
    #try two methods and return both answers to caller
    #fix me - should these be adjusted for column width? Number of columns???
    
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    y_up = int(cY - (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) - (TMPLT_HEIGHT_NAME / 2) + TMPLT_Y_OFFSET_FOR_NAME)
    y_dn = y_up + TMPLT_HEIGHT_NAME
    
    name_image = img_rgb[ y_up:y_dn, x_left:x_right, :] #a view
    
    white_list_config = r'-c tessedit_char_whitelist={} --psm 6'.format(whitelist_letters)
    name_block = pytesseract.image_to_string(name_image, lang='eng', config=white_list_config) #standard block   
    #plt.imshow(name_image)
    #plt.show()

    if skip_alternatives:
        return name_block.strip(), ""
    
    #make a binary image for an alternate test
    #NOTE - better results with NON-inverted binary - black letters on white background
    binary_img = np.copy(name_image)
    binary_img = cv2.cvtColor(binary_img, cv2.COLOR_RGB2GRAY)
    #occasionally works better with a manual threshold instead of OTSU => less noise?
    #_, binary_img = cv2.threshold(binary_img, 200, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    _, binary_img = cv2.threshold(binary_img, 175, 255, cv2.THRESH_BINARY_INV)
    
    name_block_binary = pytesseract.image_to_string(binary_img, lang='eng', config=white_list_config) #inverted standard block  
    
    return name_block.strip(), name_block_binary.strip() #let caller decide

#new for V1.5
def search_for_good_enough_match(find_me, ocr_results, threshold):
    #find string find_me among list[ocr_results], at least over threshold (0-100)
    #return True if we found something
    #FIX ME - integrate this with OCR to no waste OCR calls?
    
    for result in ocr_results:
        #print(f"comparing :{find_me}: to :{result}:")
        if find_me == result:
            return True
        if find_me.lower() == result.lower():
            return True
        if fuzz.ratio(find_me, result) > threshold:
            return True
        if fuzz.ratio(find_me.lower(), result.lower()) > threshold:
            return True
        
    return False

#new for V1.5
def assign_contest_numbers(choiceboxes):
    #assumes columns are assigned, and uses SPACING of cY to determine contests
    #assumes these are SORTED!
    
    cur_cb = choiceboxes[0]
    cur_contest_num = 1 #start with 1 not zero
    cur_col = 1
    cur_cb.contest_num = cur_contest_num
    
    cur_gap = choiceboxes[1].cY - choiceboxes[0].cY #assume 1 and 2 are same contest!
    cb_list = choiceboxes.copy() #shallow copy
    
    #print(f"gap:{cur_gap} mean del:{mean_delta} std del:{std_delta}")
    
    while True:
        if len(cb_list) == 0:
            break
        next_cb = cb_list.pop(0) #take from front
        if next_cb.column != cur_col:
            #handle new column
            #print("start new col")
            #reset gap with new column - peek ahead but don't pop
            if len(cb_list) <= 0:
                #oops - something is wrong, probably a missed CB contour
                return choiceboxes
            peek_cb = cb_list[0]
            cur_gap = peek_cb.cY - next_cb.cY
            #FIX ME - assume new col means new contest for now - fix me - add check for contest_name?
            next_cb.contest_num = cur_cb.contest_num + 1
            cur_cb = next_cb
            cur_col += 1
            #fix me update gap
            continue
        #test if we are into next contest. Cur_gap is regular candidates, second write-in adds +35
        #try larger number for start of next contest - 60
        if (next_cb.cY - cur_cb.cY) <= cur_gap + 60:
            #next_cb is in same contest
            #print("same contest")
            next_cb.contest_num = cur_cb.contest_num
            cur_cb = next_cb
            #fix me update gap
            continue
        else:
            #starts a new contest
            #print("new contest")
            next_cb.contest_num = cur_cb.contest_num + 1
            #reset gap with each new contest - peek ahead but don't pop
            if len(cb_list) <= 0:
                #oops - something is wrong, probably a missed CB contour
                return choiceboxes
            peek_cb = cb_list[0]
            cur_gap = peek_cb.cY - next_cb.cY
            cur_cb = next_cb
            continue  
    return choiceboxes

def score_inside_candidate_name_next_to_cb(img_RGB, cX, cY):
    #calc the area beside choicebox and see how empty it is
    #binarize the subset of the img
    #return the percent of non-black pixels - low score means "empty"
    
    #same constants used for OCR - fixme!
    x_left = int(cX + (TMPLT_ACTUAL_CHOICE_BOX_WIDTH / 2) + TMPLT_X_OFFSET_FOR_NAME)
    x_right = x_left + TMPLT_WIDTH_NAME
    y_up = int(cY - (TMPLT_ACTUAL_CHOICE_BOX_HEIGHT / 2) - (TMPLT_HEIGHT_NAME / 2) + TMPLT_Y_OFFSET_FOR_NAME)
    y_dn = y_up + TMPLT_HEIGHT_NAME

    name_image = img_RGB[ y_up:y_dn, x_left:x_right, :] #a view
    binary_img = np.copy(name_image)
    binary_img = cv2.cvtColor(binary_img, cv2.COLOR_RGB2GRAY)
    
    #be sure to use inverted binary but do NOT use OTSU - set thresh at 175 works well
    _, binary_img = cv2.threshold(binary_img, 175, 255, cv2.THRESH_BINARY_INV)
    area = binary_img.shape[0] * binary_img.shape[1]
    #calculate the mark score by counting non-black pixels.
    count = cv2.countNonZero(binary_img)
    
    #plt.imshow(binary_img, cmap='gray')
    #plt.show()
    
    return (count/area) * 100

#goal is to clip the area above a contest that defines the contest itself
# as well as the ONE, TWO, or THREE vote count rule
#fix me these constants are a pain
LEFT_EDGE_FROM_CX = 75
COLUMN_WIDTH = 1066 #fix me to be function of number of columns
BOTTOM_EDGE_ABOVE_CY = 30
HEIGHT_HEADERS = 300

def extract_regular_contest_header_using_cb_offsets(img, choiceboxes, target_cb_num):
    #alternative take - pick of the header text by using location of the "above" choice box
    #does NOT work for first CB in either column - SO drop back to contour method

    cb = choiceboxes[target_cb_num]
    if target_cb_num == 0:
        return extract_regular_contest_header_image(img, cb.cX, cb.cY)
    above_cb = choiceboxes[target_cb_num - 1]
    if cb.column != above_cb.column:
        return extract_regular_contest_header_image(img, cb.cX, cb.cY)
    
    left_edge = cb.cX - LEFT_EDGE_FROM_CX
    right_edge = left_edge + COLUMN_WIDTH + 10 #try a bit wider
    bottom_edge = cb.cY - 40 #bottom is lower on the page, just above lower CB
    top_edge = above_cb.cY + 40 #top is higher on the page, just below upper CB
    
    #first cut - clip a large area that contains more than we want
    sub_header_img = np.copy(img[top_edge:bottom_edge, left_edge:right_edge, : ])  #copy to prevent overwrite on base img

    #debug
    #plt.imshow(sub_header_img)
    #plt.show()

    return sub_header_img

def extract_regular_contest_header_image(img, cX, cY):
    #this works for regular contests, not for propositions.
    #cx cy should be the center of the top-most choice box of a given contest
    #returns a copy of the subset of the img that is ready for OCR
    #subset contains BOTH the contest definition as well as the NUMBER of votes allowed
    #this fails when contests are abutted top to bottom, so only use at top of columns!
    
    left_edge = cX - LEFT_EDGE_FROM_CX
    right_edge = left_edge + COLUMN_WIDTH
    bottom_edge = cY - BOTTOM_EDGE_ABOVE_CY
    top_edge = bottom_edge - HEIGHT_HEADERS
    
    #first cut - clip and copy a large area that contains more than we want
    headers = img[top_edge:bottom_edge, left_edge:right_edge, : ].copy()
    #print("shape of headers ", headers.shape)
    
    #draw a fake boundary across the bottom so that contour recog works better
    #this separates the bottom of the headers from the choice area (not a line on the actual forms)
    (rws, cls, _) = headers.shape
    cv2.line(headers,(0,rws-5),(cls-5,rws-5),(0,0,0),5)

    #try a line across the top as well? - did not help :(
    #cv2.line(headers,(0,0),(0,rws),(0,0,0),5)
    
    #find the contours in the clipped area
    headers_gray = cv2.cvtColor(headers, cv2.COLOR_BGR2GRAY)
    #note that OTSU did NOT help here
    #NOTE that we did better with threshold at 150, vs 127 default
    _, head_thresh = cv2.threshold(headers_gray, 150, 255, cv2.THRESH_BINARY_INV) 
    head_contours, _ = cv2.findContours(head_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    
    #plt.imshow(head_thresh, cmap='gray')
    #plt.show()
 
    #now find the largest contour - which hopefully is just the headers
    areas = [(i, cv2.contourArea(cnt)) for i,cnt in enumerate(head_contours)]
    sorted_areas = sorted(areas, key = lambda x:x[1], reverse=True)
    #for c, area in sorted_areas[0:10]:
    #    x,y,w,h = cv2.boundingRect(head_contours[c])
    #    print(f"c:{c} has area:{area} and w:{w}, h:{h}")

    #fix me - add more safety checks here
    #if the largest contour has exact same height as the actual image, then it's probably wrong (external contour clipped to this)
    #also, empirically, the h must be at least 100 pixels, else reject it
    for cnum, area in sorted_areas[0:10]:
        cnt = head_contours[cnum]
        x,y,w,h = cv2.boundingRect(cnt)
        if h == headers.shape[0] or h < 100:
            continue #skip this one -- too tall or too short
        else:
            break
    #print(f"selected cnum:{cnum} x:{x} y:{y} w:{w} h:{h}")
    #cnt will be the best guess contour
    
    #debug show all contours on a copy
    #headers_copy = headers.copy()
    #withcont = cv2.drawContours(headers_copy, head_contours, -1, (0,255,0), 3)
    #plt.imshow(withcont)
    #plt.show() 
    
    #get bounding rectange for the largest contour and then sub-select enclosed area from the image
    x,y,w,h = cv2.boundingRect(cnt)
    #print("yields bounding rect ", x, y, w, h)
    #force the bounding rect to go all the way to the "bottom" of the extracted image - stops some errors
    #sub_header_img = headers[y:y+h, x:x+w, :]
    sub_header_img = headers[y:, x:x+w, :]
    
    #return the color image, since that's what tesseract seems to want
    return sub_header_img

def extract_regular_contest_name_and_votes_with_OCR(img):
    #for REGULAR contests only (not propositions)
    #img is a color image subset that contains both the contest name (one or more lines)
    # and the phrase "Vote for no more than ONE (1)" where ONE, TWO, THREE, etc are allowed
    # return the contest name and the number of votes allowed
    
    block = pytesseract.image_to_string(img, lang='eng')
    logging.debug("Ocr block returns (first 50):{}".format(block[0:50]))
    
    #remove extra newlines
    #block = re.sub(r'\n\s*\n', '\n', block)
    #remove all lower case (assume ONE TWO THREE will always be UPPER)
    block = re.sub('[^A-Z0123456789\(\)\n]+', ' ', block)
    #break into lines by newline. Toss empty lines
    lines = [l.rstrip() for l in block.split('\n') if len(l)>1]
    
    if len(lines) <= 0:
        #major parse problem - propbably invalid CB recognition
        logging.warning("Unable to extract contest name OR vote total from OCR text: {}".format(block))
        vote_limit = -1
        return "", vote_limit       
    #last line should have number votes allowed
    vote_line = lines[-1]
    nums = ['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'TEN']
    vote_limit_A = -1
    vote_limit_B = -2
    for i, text in enumerate(nums):
        if vote_line.find(text) > 0:
            vote_limit_A = i + 1
            break
    #try alternate regex method on "(x)" to double check
    match = re.search(r'\([1234567890\s]+\)', vote_line)
    if match is None:
        #major parse problem - propbably invalid CB recognition
        logging.warning("Unable to extract contest name OR vote total from OCR text: {}".format(block))
        vote_limit = -1
        return "", vote_limit
    if (len(match.group(0)) == 3):
        #pattern is (n)
        vote_limit_B = int(match.group(0)[1:2])
    if vote_limit_A != vote_limit_B:
        logging.warning("Unable to extract vote total from {}".format(vote_line))
        vote_limit = -1
        #plt.imshow(img)
        #plt.show()
    else:
        vote_limit = vote_limit_A
        
    #form the contest name as the other lines (except last)
    contest_name = " ".join(lines[0:-1])
    return contest_name, vote_limit

def extract_proposition_contest_header_image(img, cX, cY):
    #customized for propositions.
    #cx cy should be the center of the top-most choice box of a given proposition
    #returns subset of the img that is ready for OCR
    #image subset contains BOTH the proposition text and the proposition or measure title
    
    #fixme - image constants again!
    HEIGHT_HEADERS_PROPOSITION = 1000
    MIN_HEIGHT_PROPOSITION = 200  #filter out contours too short to be the proposition contest text
    
    left_edge = cX - LEFT_EDGE_FROM_CX
    right_edge = left_edge + COLUMN_WIDTH + 10 #try a bit wider
    bottom_edge = cY - BOTTOM_EDGE_ABOVE_CY
    top_edge = bottom_edge - HEIGHT_HEADERS_PROPOSITION
    
    #first cut - clip a large area that contains more than we want
    headers = np.copy(img[top_edge:bottom_edge, left_edge:right_edge, : ])  #copy to prevent overwrite on base img
    
    #draw a fake boundary across the bottom so that contour recog works better
    #this separates the bottom of the headers from the choice area (not a line on the actual forms)
    (rws, cls, _) = headers.shape
    #cv2.line(headers,(0,rws-5),(cls-5,rws-5),(0,0,0),5)
    cv2.line(headers,(0,rws-5),(cls-1,rws-5),(0,0,0),5)
    
    #find the contours in the clipped area
    headers_gray = cv2.cvtColor(headers, cv2.COLOR_BGR2GRAY)
    #note that OTSU did NOT help here
    #NOTE that we did better with threshold at 200, vs 127 default
    #NOTE that we did better with threshold at 150, vs 127 default

    #_, head_thresh = cv2.threshold(headers_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU) 
    #head_contours, head_hierarchy = cv2.findContours(head_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    _, head_thresh = cv2.threshold(headers_gray, 150, 255, cv2.THRESH_BINARY_INV) 
    head_contours, _ = cv2.findContours(head_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
 
    #debug
    #print("threshold image looks like this:")
    #plt.imshow(head_thresh, cmap='gray')
    #plt.show() 
    
    #now find the largest contour that meets expected column width - should be the proposition box
    #areas = [(i, cv2.contourArea(cnt)) for i,cnt in enumerate(head_contours)]
    #sorted_areas = sorted(areas, key = lambda x:x[1], reverse=True)
    
    #fix me - make this depend on number of columns
    res = []
    for cnum, cnt in enumerate(head_contours):
        x,y,w,h = cv2.boundingRect(cnt)
        area = cv2.contourArea(cnt)
        #print(f"considering contour: w:{w} and h:{h} and area:{area}")
        if w > 900 and w < 1200 and h > MIN_HEIGHT_PROPOSITION:  #filter out wrong w and too short
            res.append((cnum, x, y, w, h, area))
    
    #of the right widths, select the one with the shortest height
    #this fails - see below
    ##heights = sorted(res, key=lambda x:x[4]) #sort by height, ascending
    ##cnum, x, y, w, h, area = heights[0]
    ## 0    1  2  3  4   5


    #of the right widths, select the contour that touches the bottom of the headers extraction
    # because a small contour at the bottom will capture the measure if the measure is short
    rows, _ = headers_gray.shape
    
    ##closest_to_bottom = sorted(res, key=lambda ct: abs(rows - (ct[2]+ct[4])))
    #alternate try - throw away any that are not very close to the bottom, then find shortest
    closest_to_bottom = [ ct for ct in res if abs(rows - (ct[2]+ct[4])) < 20 ]

    #take the closest to bottom, and find the shortest one
    shortest_close = sorted(closest_to_bottom, key=lambda ct: ct[4])
    #print(f"Found {len(shortest_close)} contours close to the bottom")
    cnum, x, y, w, h, area = shortest_close[0]

    #debug
    #withcont = cv2.drawContours(headers, head_contours, cnum, (0,255,0), 3)
    #print("fitted with best contour")
    #plt.imshow(withcont)
    #plt.show() 
    
    #get bounding rectange for the largest contour and then sub-select enclosed area from the image
    x,y,w,h = cv2.boundingRect(head_contours[cnum])
    sub_header_img = headers[y:y+h, x:x+w, :]
    
    #return the color image, since that's what tesseract seems to want
    return sub_header_img

def extract_proposition_or_measure_header_using_cb_offsets(img, choiceboxes, target_cb_num):
    #alternative take - pick of the header text by using location of the "above" choice box
    #does not work for first CB in either column - drop back to contour method

    cb = choiceboxes[target_cb_num]
    if target_cb_num == 0:
        return extract_proposition_contest_header_image(img, cb.cX, cb.cY)
    above_cb = choiceboxes[target_cb_num - 1]
    if cb.column != above_cb.column:
        return extract_proposition_contest_header_image(img, cb.cX, cb.cY)
    
    left_edge = cb.cX - LEFT_EDGE_FROM_CX
    right_edge = left_edge + COLUMN_WIDTH + 10 #try a bit wider
    bottom_edge = cb.cY - 40 #bottom is lower on the page, just above lower CB
    top_edge = above_cb.cY + 40 #top is higher on the page, just below upper CB
    
    #first cut - clip a large area that contains more than we want
    sub_header_img = np.copy(img[top_edge:bottom_edge, left_edge:right_edge, : ])  #copy to prevent overwrite on base img

    #debug
    #plt.imshow(sub_header_img)
    #plt.show()

    return sub_header_img


def extract_proposition_or_measure_contest_identifier_with_OCR(header_image, metadata):
    #for propositions and measures only
    #img is a color image subset that contains both the proposition name,
    # and lots of proposition text
    # ideally, we use the text to get the prop number but for now, just parse the number as best we can
    # or grab the measure letter (capital letter A B C, etc)
    #returns the proposition or measure full name, plus "isMeasure" = True for Measure
    #returns 
    
    #lets try OCR while we're here
    custom_config = r''
    prop_name_stuff = pytesseract.image_to_string(header_image, lang='eng', config=custom_config)
    logging.debug("OCR returns (first 50):->{}<-: ".format(prop_name_stuff[0:50]))    

    target = prop_name_stuff.strip()
    _, _, prop_or_meas_name, score = metadata.get_best_proposition_or_measure_from_text(target)
    #print(f"metadata match returns {p1}={s1}, {p2}={s2}")
    isMeasure = ("Measure" in prop_or_meas_name)
    return prop_or_meas_name, isMeasure

    #lets skip this method - fuzzy match is good enough.
    #try regex method on "(x)" to extract prop number
    match = re.search(r'Proposition ([1234567890\s]+)', target)
    if match is not None and len(match.group(1)) >= 1:
        #pattern is nn
        print("proposition extract match = {}".format(match.group(1)))
        prop_number = int(match.group(1)) 
        return prop_number, False
    match = re.search(r'Measure ([ABCDEFGHIJKLMNOPQRSTUVWXYZ]+)', target)
    if match is not None and len(match.group(1)) >= 1:
        #pattern is A
        print("measure extract match = {}".format(match.group(1)))
        measure_letter = match.group(1).strip()
        return measure_letter, True    
    print("WARNING - unable to extract proposition or measure ID")

    return "", False