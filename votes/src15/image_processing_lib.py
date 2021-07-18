
import cv2
import time
import numpy as np
import logging
import math
import copy
from pathlib import Path

import pytesseract

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [10, 10]

from scanner_constants_and_data_structures import *


#new V1.5 version uses constraints parameter instead of hard-coded constants
#moved here from template_extractor.py so it could be shared by ballot_scanner to detect empty forms

#V1.5 - changed so you have to fail BOTH w and h to be skipped
def extract_candidate_choice_box_contours(contours, constraints):
    #spin through all contours, extracting all between specified area measures
    #return list of candidate CBs
    #USE: cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    
    results = []
    number_rejected = 0
    for cnum, cnt in enumerate(contours): #cnt is the actual contour data
        
        area = cv2.contourArea(cnt) #respects actual shape, even if at an angle
        if area >= constraints.min_cb_area and area <= constraints.max_cb_area:
            M = cv2.moments(cnt)
            cX = int(M["m10"] / M["m00"]) #centroid of the moment of the rect
            cY = int(M["m01"] / M["m00"])
            
            x,y,w,h = cv2.boundingRect(cnt) #these are parallel to axis, not rotated
            if (w < constraints.min_cb_width or w > constraints.max_cb_width) and \
                (h < constraints.min_cb_height or h > constraints.max_cb_height):
                #logging.warning(f"Form:{self.path_to_template.name} warning rejecting contour {cnum} - box width {w} or height {h} was outside range")
                number_rejected += 1
                continue

            (x2,y2),(MA,ma), angle = cv2.fitEllipse(cnt) #these can be rotated
            if angle < constraints.min_cb_angle or angle > constraints.max_cb_angle:
                #logging.warning(f"Form:{self.path_to_template.name} warning rejecting contour={cnum} - box angle {angle} outside range")
                number_rejected += 1
                continue
                
            #get first parent - probably not useful anymore
            #parent = hierarchy[0,cnum,3]
            
            #'cnum area cX cY angle parent column contest_num'
            new_cb = ChoiceBox()
            new_cb.cnum = cnum
            new_cb.area = area
            new_cb.cX = cX
            new_cb.cY = cY
            new_cb.w = w
            new_cb.h = h
            new_cb.angle = angle

            results.append(new_cb)
            
    return results, number_rejected


#alignImages modified from https://www.learnopencv.com/image-alignment-feature-based-using-opencv-c-python/
#aligns a form against a pre-arranged template
#after alignment, the offsets calculated against the template can be applied to the scanned form. Magic.

MAX_FEATURES = 1000
GOOD_MATCH_PERCENT = 0.25

def OLDalignImages(im1, im2, form_name_path):
    # Convert images to grayscale
    im1Gray = cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY)
    im2Gray = cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY)

  # Detect ORB features and compute descriptors.
    orb = cv2.ORB_create(MAX_FEATURES)
    keypoints1, descriptors1 = orb.detectAndCompute(im1Gray, None)
    keypoints2, descriptors2 = orb.detectAndCompute(im2Gray, None)
  
    # Match features.
    matcher = cv2.DescriptorMatcher_create(cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING)
    matches = matcher.match(descriptors1, descriptors2, None)
    
    # Sort matches by score
    matches.sort(key=lambda x: x.distance, reverse=False)
    
    # Remove not so good matches
    numGoodMatches = int(len(matches) * GOOD_MATCH_PERCENT)
    matches = matches[:numGoodMatches]
    
    # turn this on only if debugging
    # Draw top matches
    #imMatches = cv2.drawMatches(im1, keypoints1, im2, keypoints2, matches, None)
    #cv2.imwrite("{}_matches.jpg".format(form_name_path.stem), imMatches)

    # Extract location of good matches
    points1 = np.zeros((len(matches), 2), dtype=np.float32)
    points2 = np.zeros((len(matches), 2), dtype=np.float32)

    for i, match in enumerate(matches):
        points1[i, :] = keypoints1[match.queryIdx].pt
        points2[i, :] = keypoints2[match.trainIdx].pt
   
    # Find homography
    h, mask = cv2.findHomography(points1, points2, cv2.RANSAC)

    # Use homography
    height, width, channels = im2.shape
    im1Reg = cv2.warpPerspective(im1, h, (width, height))
    
    return im1Reg, h


##### new version of alignImages that does not require a feature/descriptor detector
# uses choice box locations, extracted by contour recogntion to create direct pairings of feature points
# then use homology and warpPerspective to align
# this is now the "fallback" approach if the new template-match method doesn't work for some ballots
#
def alignImages(form_img, template_img, template_choices_dict, form_name_path):
    # will attempt to morph FORM onto the TEMPLATE, so that FORM can be vote-extracted 
    # NOTE that this will not process an upside-down image - make sure those have been flipped before calling this
    # NOTE uses the existing template choices dictionary rather than re-scaning the template image
    # V1.5 changes - add use of two or three barcodes to keypoints. Do the CB homology first, then tack on barcodes
    # Consider adding OCR of text at upper right

    #FIXME - we are ignoring the return of M ??
    aligned_form_image, m = align_form_using_barcode_stripes(form_img, form_name_path)
    #aligned_form_image = form_img

    form_keypoints  = extract_keypoints_for_alignment(aligned_form_image, form_name_path)
    # we now pull this from choice_dict --> template_keypoints = extract_keypoints_for_alignment(template_img, form_name_path)
    
    #pull keypoints out of the template's contests dictionary
    template_x_y_pairs = []
    for contest in template_choices_dict['contests']:
        for cb in contest['choice_boxes']:
            template_x_y_pairs.append(( cb['cX'], cb['cY'] ))
    #and convert to an array of floating points
    #NOTE these points will NOT be in proper order, so use the distance-matching to align
    template_keypoints = np.array(template_x_y_pairs, dtype=np.float32)

    visually_log_after_homology_message = "" #add a message if this image should be visually logged

    if len(form_keypoints) == len(template_keypoints):
        template_keypoints = match_alignment_points(template_keypoints, form_keypoints)

    elif len(form_keypoints) < len(template_keypoints):
        logging.warning("Warning {} - form has fewer keypoints {} than template {} - will subselect points from template and try homologize".format(
            form_name_path.stem, len(form_keypoints), len(template_keypoints)))
        
        reduced_template = match_alignment_points(template_keypoints, form_keypoints)
        if ( abs(len(form_keypoints) - len(template_keypoints)) > 5):
            visually_log_after_homology_message += "Form-to-template keypoint match was unusually large - please inspect form for accurate HOMOLOGY\n"

        if reduced_template is None:
            logging.warning("Warning - {} could not accomplish match alignment so will use OLDER homology routine".format(form_name_path.stem))
            form_img_registered, h = OLDalignImages(form_img, template_img, form_name_path)
            visually_log_after_homology_message += "Older less precise form-to-template HOMOLOGY was used. Please inspect\n"
            return form_img_registered, h, visually_log_after_homology_message

        else:
            template_keypoints = reduced_template
            pass
    else: 
        logging.warning("Warning {} - form/template keypoint lengths can't be reconcilded (T:{} VS F:{}) in alignImages - SO use OLDER homology routine!".format(
                form_name_path.stem, len(template_keypoints),len(form_keypoints)))

        #FIXME - is this still necessary?  What about failure returns?
        form_img_registered, h = OLDalignImages(form_img, template_img, form_name_path)
        visually_log_after_homology_message += "Older less precise form-to-template HOMOLOGY was used. Please inspect\n"
        return form_img_registered, h, visually_log_after_homology_message 

    #####
    #V1.5 - add in more match points from barcodes. Try all three, but use whichever can be obtained
    ######
    ul_f_centroids, ll_f_centroids, lr_f_centroids = extract_barcode_centroids_from_form(aligned_form_image, form_name_path)
    ul_t_centroids, ll_t_centroids, lr_t_centroids = extract_barcode_centroids_from_form(template_img, form_name_path)

    #for each barcode where both form and template have good data, add data pairs onto end of existing keypoints
    if len(ul_f_centroids) > 0 and len(ul_t_centroids) > 0:
        ul_f_data = np.array(ul_f_centroids, dtype=np.float32)
        ul_f_top = ul_f_data[0] #use top bar
        ul_f_bot = ul_f_data[-1] #and bottom bar

        ul_t_data = np.array(ul_t_centroids, dtype=np.float32)
        ul_t_top = ul_t_data[0] #use top bar
        ul_t_bot = ul_t_data[-1] #and bottom bar

        #add on
        form_keypoints     = np.concatenate((    form_keypoints, np.array([ul_f_top, ul_f_bot])), axis=0)
        template_keypoints = np.concatenate((template_keypoints, np.array([ul_t_top, ul_t_bot])), axis=0)


    if len(ll_f_centroids) > 0 and len(ll_t_centroids) > 0:
        ll_f_data = np.array(ll_f_centroids, dtype=np.float32)
        ll_f_top = ll_f_data[0] #use top bar
        ll_f_bot = ll_f_data[-1] #and bottom bar

        ll_t_data = np.array(ll_t_centroids, dtype=np.float32)
        ll_t_top = ll_t_data[0] #use top bar
        ll_t_bot = ll_t_data[-1] #and bottom bar

        #add
        form_keypoints     = np.concatenate((    form_keypoints, np.array([ll_f_top, ll_f_bot])), axis=0)
        template_keypoints = np.concatenate((template_keypoints, np.array([ll_t_top, ll_t_bot])), axis=0)
       
    #LR barcode is problematic - ensure that we got ALL of the barcode on both forms   
    if len(lr_f_centroids) > 0 and  len(lr_f_centroids) == len(lr_t_centroids):
        lr_f_data = np.array(lr_f_centroids, dtype=np.float32)
        lr_f_top = lr_f_data[0] #use top bar
        lr_f_bot = lr_f_data[-1] #and bottom bar

        lr_t_data = np.array(lr_t_centroids, dtype=np.float32)
        lr_t_top = lr_t_data[0] #use top bar
        lr_t_bot = lr_t_data[-1] #and bottom bar

        #add
        form_keypoints     = np.concatenate((    form_keypoints, np.array([lr_f_top, lr_f_bot])), axis=0)
        template_keypoints = np.concatenate((template_keypoints, np.array([lr_t_top, lr_t_bot])), axis=0)
    
    elif len(lr_f_centroids) > 0 and len(lr_t_centroids) > 1:
        #LR is not complete so try to use the top data point, even if lower point was clipped off the form 
        lr_f_data = np.array(lr_f_centroids, dtype=np.float32)
        lr_f_top = lr_f_data[0] #use top bar only

        lr_t_data = np.array(lr_t_centroids, dtype=np.float32)
        lr_t_top = lr_t_data[0] #use top bar only

        #add
        form_keypoints     = np.concatenate((    form_keypoints, np.array([lr_f_top])), axis=0)
        template_keypoints = np.concatenate((template_keypoints, np.array([lr_t_top])), axis=0)
    else:
        logging.warning("Form:{form_name_path.name} was not able to use lower right barcode for alignment")        
    
    #finally, use homography to find a map between the images
    #first try least-squares, and if that fails retry with RANSAC
    
    #V1.5 - try perfect match mode 0, then fall back to RANSAC
    h, mask = cv2.findHomography(form_keypoints, template_keypoints, cv2.RANSAC, 8)  #increase RANSAC threshold from 3 to 8
    #print(f"Mask = {mask}")
    if h is None:
        h, mask = cv2.findHomography(form_keypoints, template_keypoints, 0)
        if h is None:
            logging.error(f"Form: {form_name_path.stem} - fails to produce H matrix and thus cannot be warped! ")
            visually_log_after_homology_message += "Form was unable to be aligned onto template. Will not be scored!\n"
            return (None, h, m, visually_log_after_homology_message)

    #apply H matrix to warp the form onto the template
    height, width, _ = template_img.shape
    form_img_registered = cv2.warpPerspective(aligned_form_image, h, (width, height))

    ############debugging - uncomment to see images and scores
    # draw_points(template_img, template_keypoints)
    # draw_points(aligned_form_image, form_keypoints)
    # for contest in template_choices_dict['contests']:
    #     for cb in contest['choice_boxes']:

    #         show_choice_box_on_image(template_img, cb['cX'], cb['cY'], (0,0,255))
    #         temp_img_gray = cv2.cvtColor(form_img_registered, cv2.COLOR_BGR2GRAY)
    #         ret, temp_img_binary = cv2.threshold(temp_img_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    #         score, ul_x, ul_y, lr_x, lr_y = score_inside_choice_box(form_img_registered, temp_img_binary, cb['cX'], cb['cY'])
    #         show_score_on_image(form_img_registered, cb['cX'], cb['cY'], score, (0,0,255))
    #         show_choice_box_on_image(temp_img_binary, cb['cX'], cb['cY'], (255,0,0))
    #         show_choice_box_on_image(form_img_registered, cb['cX'], cb['cY'], (0,0,255))


    # fig, ax = plt.subplots(1,4, figsize=(22,12))
    # ax[0].imshow(template_img)
    # ax[1].imshow(aligned_form_image)
    # ax[2].imshow(form_img_registered)
    # ax[3].imshow(temp_img_binary, cmap='gray')    
    # plt.show()
    ####################

    #return the registered image for processing
    return(form_img_registered, h, m, visually_log_after_homology_message)

def extract_keypoints_for_alignment(image, form_name_path):
    #fixme - should this use TIGHT or LOOSE constraints? 
    #USE TIGHT constraints because a false positive will screw up the homology!!
    #create a list of keypoints that can be used to align this image
    #keypoints are based on centroids of the choice boxes - might not work for other kinds of forms!!
    #image should be a GBR image opened by cv2.imread()

    # Convert image to grayscale
    image_gray     = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # binarize the images for contour detection
    _, image_binary = cv2.threshold(image_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)

    #extract contours
    contours, _ = cv2.findContours(image_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    #filter to the contours that we think are choice-boxes.
    #uses same globals used eleswhere which might not be right?

    #override some of those to keep this constrained to only valid CB!!
    #MIN_CHOICE_BOX_WIDTH
    MAX_CHOICE_BOX_WIDTH = 160
    #MIN_CHOICE_BOX_HEIGHT
    MAX_CHOICE_BOX_HEIGHT = 100
    min_area = 5000
    max_area = 5400


    results = []

    for cnum, cnt in enumerate(contours):

        area = cv2.contourArea(cnt)
        #if (area > 4000 and area < 6000):
        #    print(f"Area: {area}")
        #set a tight constraint - we can afford to miss a few, but a false-positive is very harmful to homology
        if area >= min_area and area <= max_area:
            #Mmt = cv2.moments(cnt)
            #cX = int(Mmt["m10"] / Mmt["m00"])
            #cY = int(Mmt["m01"] / Mmt["m00"])

            x,y,w,h = cv2.boundingRect(cnt)
            if (w < MIN_CHOICE_BOX_WIDTH or w > MAX_CHOICE_BOX_WIDTH) or (h < MIN_CHOICE_BOX_HEIGHT or h > MAX_CHOICE_BOX_HEIGHT) :
                #print("warning {} rejecting contour={} - box width {} a/or height {} with area {} out of range".format(form_name_path.stem, cnum, w, h, area))
                continue
            
            (x2,y2),(MA,ma), angle = cv2.fitEllipse(cnt)
            if angle < MIN_CHOICE_BOX_ANGLE or angle > MAX_CHOICE_BOX_ANGLE:
                #print("warning {} keeping contour={} - box angle {} and area {} outside range".format(form_name_path.stem, cnum, angle, area))
                #continue
                pass
            
            #use choicebox as convenient way to name and hold stuff
            cb = ChoiceBox()
            cb.cnum = cnum
            cb.area = area
            cb.cX = x2
            cb.cY = y2
            cb.angle = angle
            
            results.append(cb)
    
    #FIXME - we have better column tools now - update this?
    #assign a column to the choiceboxes, based on left-half vs right-half of image
    for cb in results: cb.column = (1 if cb.cX < (image.shape[1]/2) else 2)

    #sort by col and then by cY so we can match to the other image's similar sort
    results = sorted(results, key=lambda cb:(cb.column, cb.cY))
    points = [ (cb.cX, cb.cY) for cb in results ]
    keypoints = np.array( points, dtype=np.float32)
    return keypoints

def distance(p1, p2):
    return np.sqrt(np.sum((p1 - p2) ** 2))
    
def match_alignment_points(template_points, form_points):
    #attempt to align form keypoints to template keypoints, assuming that form may be missing some choice boxes
    #after match, returns a new template with potentially fewer entries that match the form
    
    if len(form_points) > len(template_points):
        logging.warning("Cannot align form and template match points if form has more points than template")
        return None
    
    #loop thru form points and find the "closest" template point, use that one
    
    out_template = form_points.copy()
    in_template = template_points.copy()
    done = set()
    for f, fpt in enumerate(form_points):
        close = 1e10
        loc = -1
        for t, tpt in enumerate(in_template):
            if t in done: continue
            d = distance(fpt, tpt)
            if d < close:
                close = d
                loc = t
        #assign close, and remove pt from template
        #print(f"mapping form pt: {f} {out_template[f]} to template pt: {loc} {template_points[loc]}")
        out_template[f] = template_points[loc]
        done.add(loc)
        

    return out_template

##########
# try doing homology using the three barcodes? 
# is the lower right BC always present?
##########

def get_barcode_bar_centroids_from_form(bc_img, offset):
    #extract contours from binarized images - works well for barcodes
    
    min_barcode_width = 74
    max_barcode_width  = 77
    max_barcode_height  = 18

    image_gray = cv2.cvtColor(bc_img, cv2.COLOR_BGR2GRAY)
    _, image_binary = cv2.threshold(image_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(image_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE, None, None, offset)
    #filter all contours to eliminate non-barcode contours - critical to get these parameters right
    centroids = []
    for cnt in contours:
        _,_,w,h = cv2.boundingRect(cnt)
        if w < min_barcode_width or w > max_barcode_width or h > max_barcode_height:
            continue #skip the ones that don't fit expectation
        #we want the centroids of the bounding rectangles
        M = cv2.moments(cnt)
        cX = int(M["m10"] / M["m00"]) #centroid of the moment of the rect
        cY = int(M["m01"] / M["m00"])
        centroids.append([cX, cY])
    return centroids

def extract_barcode_centroids_from_form(form_img, path_to_form):
    #return lists of sorted centroids for each barcode region
    #note that barcode centroids could be null if barcode was partially clipped
    #centroid x,y values are referenced to full image (see "offset" on cv2.findContours)
    
    RIGHT_UL_BC = 280
    BOT_UL_BC = 900
    TOP_LL_BC = 3400
    TOP_LR_BC = 3000

    rows, cols, _ = form_img.shape #y, x, colors

    #clip barcodes from a form
    ulbc_form =         form_img[0:BOT_UL_BC       , 0:RIGHT_UL_BC, :].copy()  #img[rows, cols]
    llbc_form =         form_img[TOP_LL_BC:rows    , 0:RIGHT_UL_BC, :].copy()
    lrbc_form =         form_img[TOP_LR_BC:rows    , cols-RIGHT_UL_BC: cols, :].copy()

    #find contours, get centroid of barcode bars, apply offset to whole image, then sort ascending by cY
    ul_f_centroids = sorted(get_barcode_bar_centroids_from_form(ulbc_form, (0,0)), key = lambda p: p[1])   #offset is w/r to centroids, thus (x-offset, y-offset)
    ll_f_centroids = sorted(get_barcode_bar_centroids_from_form(llbc_form, (0, TOP_LL_BC)), key = lambda p: p[1])
    lr_f_centroids = sorted(get_barcode_bar_centroids_from_form(lrbc_form, (cols-RIGHT_UL_BC, TOP_LR_BC)), key = lambda p: p[1])

    if len(ul_f_centroids) <= 0 or len(ll_f_centroids) <= 0 or len(lr_f_centroids) < 0:
        logging.warning(f"FORM {path_to_form.name} DOES NOT HAVE ALL BARCODES present for contouring. Will use what's available")

    return ul_f_centroids, ll_f_centroids, lr_f_centroids

#no longer used - save for debugging
def barcode_homology(form_img, template_img, path_to_form):
    #extract the three barcode regions

    RIGHT_UL_BC = 280
    BOT_UL_BC = 900
    TOP_LL_BC = 3400
    TOP_LR_BC = 3000

    min_barcode_width = 74
    max_barcode_width  = 77
    max_barcode_height  = 18
    
    rows, cols, _ = form_img.shape #y, x, colors

    do_OCR = False
    if (do_OCR):
        #test pytesseract finding "Page" at top left - FORM
        page_img = form_img[0:400, 0:cols]
        d = pytesseract.image_to_data(page_img, lang='eng', config=r'', output_type=pytesseract.Output.DICT)
        offset = [e[0] for e in enumerate(d['text']) if e[1] == 'Page'] #find offset for 'Page'
        form_top_x = form_left_y = -1
        
        if len(offset) == 1:
            ndx = offset[0]
            form_top_y = d['top'][ndx]
            form_left_x = d['left'][ndx]
            print(f"FORM page offset = {form_left_x},{form_top_y}")
            #now do Template
            d2 = pytesseract.image_to_data(template_img[0:400, 0:cols], lang='eng', config=r'', output_type=pytesseract.Output.DICT)
            offset = [e[0] for e in enumerate(d2['text']) if e[1] == 'Page'] #find offset for 'Page'

            if len(offset) == 1:
                ndx = offset[0]
                templ_top_y = d2['top'][ndx]
                templ_left_x = d2['left'][ndx]
                print(f"Template page offset = {templ_left_x},{templ_top_y}")
            else: 
                print("Unable to parse Page text at top of template!!")
        else: 
            print("Unable to parse Page text at top of form or template!")


    ulbc_form = form_img[0:BOT_UL_BC                 , 0:RIGHT_UL_BC, :].copy()  #img[rows, cols]
    llbc_form = form_img[TOP_LL_BC:rows              , 0:RIGHT_UL_BC, :].copy()
    lrbc_form = form_img[TOP_LR_BC:rows              , cols-RIGHT_UL_BC: cols, :].copy()

    ulbc_template = template_img[0:BOT_UL_BC                 , 0:RIGHT_UL_BC, :].copy()  #img[rows, cols]
    llbc_template = template_img[TOP_LL_BC:rows              , 0:RIGHT_UL_BC, :].copy()
    lrbc_template = template_img[TOP_LR_BC:rows              , cols-RIGHT_UL_BC: cols, :].copy()

    ul_f_centroids = sorted(get_centroids(ulbc_form, (0,0)), key = lambda p: p[1])   #offset is w/r to centroids, thus (x-offset, y-offset)
    ll_f_centroids = sorted(get_centroids(llbc_form, (0, TOP_LL_BC)), key = lambda p: p[1])
    lr_f_centroids = sorted(get_centroids(lrbc_form, (cols-RIGHT_UL_BC, TOP_LR_BC)), key = lambda p: p[1])

    if len(ul_f_centroids) <= 0 or len(ll_f_centroids) <= 0 or len(lr_f_centroids) < 0:
        logging.warning(f"FORM {path_to_form.name} DOES NOT HAVE ALL BARCODES present for contouring")

    ul_t_centroids = sorted(get_centroids(ulbc_template, (0,0)), key = lambda p: p[1])
    ll_t_centroids = sorted(get_centroids(llbc_template, (0, TOP_LL_BC)), key = lambda p: p[1])
    lr_t_centroids = sorted(get_centroids(lrbc_template, (cols-RIGHT_UL_BC, TOP_LR_BC)), key = lambda p: p[1])

    if len(ul_t_centroids) <= 0 or len(ll_t_centroids) <= 0 or len(lr_t_centroids) < 0:
        logging.warning(f"TEMPLATE for {path_to_form.name} DOES NOT HAVE ALL BARCODES present for contouring")

    ul_f_data = np.array(ul_f_centroids, dtype=np.float32)
    ul_f_top = np.median(ul_f_data[0:4], axis=0) #first 3
    ul_f_bot = np.median(ul_f_data[-4:], axis=0) #last 3

    ll_f_data = np.array(ll_f_centroids, dtype=np.float32)
    ll_f_top = np.median(ll_f_data[0:4], axis=0) 
    ll_f_bot = np.median(ll_f_data[-4:], axis=0) 

    if len(lr_f_centroids) > 0:
        lr_f_data = np.array(lr_f_centroids, dtype=np.float32)
        lr_f_top = np.median(lr_f_data[0:4], axis=0) 
        lr_f_bot = np.median(lr_f_data[-4:], axis=0)
    else:
        lr_f_data = None
        lr_f_top = None 
        lr_f_bot = None           

    ul_t_data = np.array(ul_t_centroids, dtype=np.float32)
    ul_t_top = np.median(ul_t_data[0:4], axis=0) 
    ul_t_bot = np.median(ul_t_data[-4:], axis=0) 

    ll_t_data = np.array(ll_t_centroids, dtype=np.float32)
    ll_t_top = np.median(ll_t_data[0:4], axis=0) 
    ll_t_bot = np.median(ll_t_data[-4:], axis=0) 

    if len(lr_t_centroids) > 0:
        lr_t_data = np.array(lr_t_centroids, dtype=np.float32)
        lr_t_top = np.median(lr_t_data[0:4], axis=0) 
        lr_t_bot = np.median(lr_t_data[-4:], axis=0) 
    else:
        lr_t_data = None
        lr_t_top = None 
        lr_t_bot = None         

    if lr_f_data is not None and lr_t_data is not None:
        form_points     = np.array([ul_f_top, ul_f_bot, ll_f_top, ll_f_bot, lr_f_top, lr_f_bot])
        template_points = np.array([ul_t_top, ul_t_bot, ll_t_top, ll_t_bot, lr_t_top, lr_t_bot])
    else:
        form_points     = np.array([ul_f_top, ul_f_bot, ll_f_top, ll_f_bot])
        template_points = np.array([ul_t_top, ul_t_bot, ll_t_top, ll_t_bot])        

    h, mask = cv2.findHomography(form_points, template_points, 0)
    if h is None:
        print(f"H was NONE - mask = {mask}")
        return
    
    #apply H matrix to warp the form onto the template
    height, width, _ = template_img.shape
    form_img_registered = cv2.warpPerspective(form_img, h, (width, height))



    # draw_points(template_img, template_points)
    # draw_points(form_img, form_points)
    # fig, ax = plt.subplots(1,3, figsize=(16,9))
    # ax[0].imshow(template_img)
    # ax[1].imshow(form_img)
    # ax[2].imshow(form_img_registered)    
    # #plt.imshow(form_img_registered)
    # plt.show()

    return form_img_registered, h, ""

def draw_points(image, points_iter):
    for xx, yy in points_iter:
        x = int(xx)
        y = int(yy)
        cv2.rectangle(image, (x-2, y-2), (x + 4, y + 4), (255, 0, 0), 2)
    return

##########
# new alignment process - uses barcodes to generate alignment data
# probably could replace some existing code with this?
##########

def align_form_using_barcode_stripes(image_bgr, path_to_form):
    #V15 - changed to align and translate to "standard position"
    # defined as center width of top left barcode to be 120 pixels from left edge of scan
    #  and top line of top-left barcode to be 175 pixels from top of scan
    #assumes image has been opened in cv2.COLOR_BGR2GRAY mode
    #path_to_form used for logging only
    #V15 - also return the M matrix for addition to choices.json in some cases

    image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    rows, cols, _ = image_bgr.shape #y, x, colors
    
    #extract a subset of the image, including both left-sided barcodes
    #grab the entire left strip, top to bottom

    BAR_CODE_STRIP_WIDTH = 350
    min_barcode_width = 74
    max_barcode_width  = 77
    max_barcode_height  = 18
    min_barcode_height = 5  #there are 5's but anything 4 or less is a problem

    #these will be views, not copies
    left_strip_gray = image_gray[0:rows, 0: BAR_CODE_STRIP_WIDTH]

    #extract contours from binarized images - works well for barcodes
    _, image_binary = cv2.threshold(left_strip_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(image_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    #filter all contours to eliminate non-barcode contours - critical to get these parameters right
    centroids = []
    top_y_value = 1e10

    for cnt in contours:

        x,y,w,h = cv2.boundingRect(cnt)
        
        if w < min_barcode_width or w > max_barcode_width or h > max_barcode_height or h < min_barcode_height:
            continue #skip the ones that don't fit expectation
        
        #print(f"after filter x:{x} y:{y} w:{w} h:{h}")
    
        #we want the centroids of the bounding rectangles
        M = cv2.moments(cnt)
        cX = int(M["m10"] / M["m00"]) #centroid of the moment of the rect
        cY = int(M["m01"] / M["m00"])

        top_y_value = min(top_y_value, cY) #remember topmost barcode offset from top of form
        centroids.append([cX, cY])
        
    #fit least squares line to these centroids
    points = np.array(centroids, dtype=np.float32)
    vx, vy, xx, yy = cv2.fitLine(points, cv2.DIST_L2, 0, 0.01, 0.01) 

    #calculate the angle of the unit vector (vx,vy)
    line_angle = math.atan2(vy, vx) * (180/(math.pi))

    #calculate offset of X to land center of barcode at 120 pixels inset from left eldge of scan
    # and top of barcode to land 175 pixels from top of scan
    x_shift = 120 - xx[0]
    y_shift = 175 - top_y_value

    #added sanity check - these offsets are always < 100, so if greater, something went wrong
    #one cause is it finds only LL barcode, so top_y_value is way off.

    if abs(y_shift) > 100:
        y_shift = 0
    if abs(x_shift) > 100:
        x_shift = 0

    #interpreting line angle is tricky.
    #Should range from -90 (vertical up) thru 0 (x-axis to the right) to -90 (vertical down)
    correction_ang = 0
    if line_angle > 0:
        correction_ang = line_angle - 90 #needs cw rotation, negative number
    elif line_angle < 0:
        correction_ang = line_angle + 90 #need ccw rotation, positive number
    else:
        correction_ang = 0 #no correction
        
    #we expect a small number of degrees, +/-. Warn if we don't get that!
    if abs(correction_ang) > 3:
        logging.warning(f"WARNING - form: {path_to_form.stem} had unusual alignment correction angle: {correction_ang}")

    #for visual confirmation of correction, we could draw the pre-alignment vertical thru the correction points 
    #but it might mess up later barcode reading?
    #m=4000
    #cv2.line(image_bgr, (int(xx - m*vx), int(yy - m*vy)), (int(xx + m*vx), int(yy + m*vy)), (255,0,0),3)

    #de-rotate and translate
    #if correction_ang != 0:
    rows,cols,_ = image_bgr.shape
    #postive angle rotates CCW (top to the left) (because we are upside down??)
    #negative angle rotates CW (top to the right)
    M = cv2.getRotationMatrix2D((cols/2,rows/2), correction_ang, 1) #rotate about center, no scaling
    #add in the translation for x and y (linear, so can add onto rotation)
    M[0,2] += x_shift
    M[1,2] += y_shift
    corrected_image = cv2.warpAffine(image_bgr, M, (cols,rows))
    logging.info(f"Info - form: {path_to_form.stem} alignment was corrected by angle: {correction_ang:.2f} and offset: {int(x_shift)},{int(y_shift)}")
    #print(f"Info - form: {path_to_form.stem} alignment was corrected by angle: {correction_ang:.2f} and offset: {int(x_shift)},{int(y_shift)}")

    #else:
    #    corrected_image = np.copy(image_bgr)

    return corrected_image, M 

def apply_affine_to_image(img, M):
    #apply the affine transformation to the image
    rows,cols,_ = img.shape
    corrected_image = cv2.warpAffine(img, M, (cols,rows))    
    return corrected_image

#######
#routines that process features on a ballot form
#######

def calc_choice_box_scoring_coords(choice_box_center_x, choice_box_center_y):
    
    #w2 = int(ACTUAL_CHOICE_BOX_WIDTH / 2) #cols -> x axis
    #h2 = int(ACTUAL_CHOICE_BOX_HEIGHT / 2) #rows -> y axis
    
    #ul_x = choice_box_center_x - w2 + CHOICE_BOX_COUNT_INSET
    #ul_y = choice_box_center_y - h2 + CHOICE_BOX_COUNT_INSET
    #lr_x = choice_box_center_x + w2 - CHOICE_BOX_COUNT_INSET
    #lr_y = choice_box_center_y + h2 - CHOICE_BOX_COUNT_INSET
    
    w2 = int(INNER_CHOICE_BOX_WIDTH / 2) #cols -> x axis
    h2 = int(INNER_CHOICE_BOX_HEIGHT / 2) #rows -> y axis
    
    ul_x = choice_box_center_x - w2 + 4
    ul_y = choice_box_center_y - h2 + 4 #try without this nudge + 2 #nudge this down a bit - seems to work better
    lr_x = choice_box_center_x + w2 - 4
    lr_y = choice_box_center_y + h2 - 4
    
    return ul_x, ul_y, lr_x, lr_y

def score_inside_choice_box(img, img_binary, choice_box_center_x, choice_box_center_y):
    #center_x gives the COL, center_y gives the ROW, from the image POV
    #count non-zero pixels inside binarized rectangle (subset of the image)
    #use img for printing ballot to inspect area and score
    #h and w depend on the ballot box size, in pixels, outer edge measured in PS
    
    #return score as a percent of pixels non-zero (range 0-100)
    
    ul_x, ul_y, lr_x, lr_y = calc_choice_box_scoring_coords(choice_box_center_x, choice_box_center_y)
    area = (lr_x - ul_x) * (lr_y - ul_y)
    #calculate the mark score by counting non-black pixels.
    #NOTE that we have to use the BINARY INVERTED IMAGE for this!
    
    sub_area = img_binary[ul_y:lr_y, ul_x:lr_x] #do I need +1?
    score = cv2.countNonZero(sub_area)
    
    
    return (score/area) * 100, ul_x, ul_y, lr_x, lr_y


def show_choice_box_on_image(img, choice_box_center_x, choice_box_center_y, color):
    #mark the full color 'img' to show where a choice box inset will be
    #color is triplet (G, B, R) 0-255

    ul_x, ul_y, lr_x, lr_y = calc_choice_box_scoring_coords(choice_box_center_x, choice_box_center_y)
    
    #draw on img for visual inspection
    cv2.rectangle(img, (ul_x, ul_y), (lr_x, lr_y), color, 2)
    
    return

def show_score_on_image(img, choice_box_center_x, choice_box_center_y, score, color):
    #color is (G, B, R)

    ul_x, ul_y, lr_x, lr_y = calc_choice_box_scoring_coords(choice_box_center_x, choice_box_center_y)
    h2 = int(ACTUAL_CHOICE_BOX_HEIGHT / 2) #rows -> y axis
    
    cv2.putText(img, "{:.2f}".format(score),(lr_x + 600, ul_y + h2), 
                cv2.FONT_HERSHEY_SIMPLEX,1.2, color, 2)
    return

def draw_circle_around_choice_box(img, cX, cY, color):
    #elipse, actually
    center_coordinates = (cX, cY) 
    axesLength = (85, 50) 
    angle = 0
    startAngle = 0
    endAngle = 360
    # Line thickness of 5 px 
    thickness = 4
    image = cv2.ellipse(img, center_coordinates, axesLength, 
               angle, startAngle, endAngle, color, thickness) 
    return

def show_contest_num_on_image(image, cb):
    #just put contest number out past score
    ul_x, ul_y, lr_x, lr_y = calc_choice_box_scoring_coords(cb.cX, cb.cY)
    h2 = int(ACTUAL_CHOICE_BOX_HEIGHT / 2) #rows -> y axis
    
    cv2.putText(image, "contest:{}".format(cb.contest_num),(lr_x + 750, ul_y + h2), 
                cv2.FONT_HERSHEY_SIMPLEX,1.2, (0, 255, 0), 3)
    return   

def show_contest_name__and_votes_allowed_on_image(image, cX, cY, name, votes):
    #display contest_name (votes allowed) above the cX,cY paur
    #shorted to max 40 chars (plus ... ) by chopping from middle
    max = 30
    display = f"{name} v:{votes}"
    if len(display) > max:
        h_extra = int( (len(display) - max)/2)
        mid = int(len(display)/2)
        show = display[0:mid-h_extra] + " ... " + display[mid+h_extra:]
    else:
        show = display

    w2 = int(ACTUAL_CHOICE_BOX_WIDTH / 2) #rows -> y axis
    
    cv2.putText(image, show, (cX - w2, cY - 35), 
        cv2.FONT_HERSHEY_SIMPLEX,1.6, (150, 150, 20), 3)
    return 

def show_precinct_page_on_image(image, precinct, page):
    #display contest_name (votes allowed) above the cX,cY paur
    #shorted to max 40 chars (plus ... ) by chopping from middle

    display = f"Precinct: {precinct} Page:{page}"
    
    cv2.putText(image, display, (1200,300), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 3)
    return 

def show_proposition_name_on_image(image, cX, cY, name):
    max = 26
    display = f"{name}"
    if len(display) > max:
        h_extra = int( (len(display) - max)/2)
        mid = int(len(display)/2)
        show = display[0:mid-h_extra] + " ... " + display[mid+h_extra:]
    else:
        show = display
    cv2.putText(image, show, (cX + 50, cY - 25), 
        cv2.FONT_HERSHEY_SIMPLEX, 2, (150, 150, 20), 3)
    return

def draw_proposed_contours(img, contours, results):
    #draw the bounding rectangle for the qualifying contours
    #img is the full color image
    #for (cnum, area, cX, cY, angle, parent) in results:
    for cb in results:
        cnt = contours[cb.cnum]
        x,y,w,h = cv2.boundingRect(cnt)
        cv2.rectangle(img, (x, y), (x+w, y+h), (255,0,0), 2)

    return

def score_and_annotate_image(img, img_binary, results):
    #for (cnum, area, cX, cY, angle, parent) in results:
    for cb in results:
        show_choice_box_on_image(img, cb.cX, cb.cY, (0,0,255))
        score, ul_x, ul_y, lr_x, lr_y = score_inside_choice_box(img, img_binary, cb.cX, cb.cY)
        show_score_on_image(img, cb.cX, cb.cY, score, (0,255,0))
        if cb.contest_num != -1:
            show_contest_num_on_image(img, cb)
        
    return

#fixme - these assumptions won't work for propostions and measures?
CONTEST_LEFT_EDGE_FROM_CX = 95
CONTEST_COLUMN_WIDTH = 1100
CONTEST_BOTTOM_EDGE_BELOW_CY = 180
CONTEST_HEIGHT_HEADERS = 320

def extract_contest_frame(img, choices_dict, contest_name, box_color):
    #pass in choices and contest_name
    #use contest_name to find all the contained choices boxes for that contest
    #find top and bottom choice boxes and their centers
    #guess a surrounding bounding box based on constants for these ballots (!!)
    #find the large contour that has width and height as appropriate
    #paint the contest contours with box_color and return the out guesstimate as image

    #fixme - these assumptions won't work for propostions and measures?
    
    contests = choices_dict['contests']
    #match by exact match on contest name
    our_contest = [c for c in contests if c['contest_name'] == contest_name][0]
    
    #find the choice boxes for this contest, and isolate the top and bottom choices
    contest_boxes = [cb for cb in our_contest['choice_boxes']]
    sorted_boxes = sorted(contest_boxes, key=lambda cb:cb['cY'] ) #sorts ascending by cY
    top_box = sorted_boxes[0]
    bottom_box = sorted_boxes[-1]
    
    #extract a subset of the image based on offsets from top and bottom choices
    #these might change with PROPOSITIONS?
    left_x = top_box['cX'] - CONTEST_LEFT_EDGE_FROM_CX
    top_y = top_box['cY'] - CONTEST_HEIGHT_HEADERS
    right_x = left_x + CONTEST_COLUMN_WIDTH 
    bottom_y = bottom_box['cY'] + CONTEST_BOTTOM_EDGE_BELOW_CY
    
    #first cut - clip a large area that contains more than we want
    #image is rows, cols -> y, x
    guessed_img = img[top_y:bottom_y, left_x:right_x, : ]
    
    #V1.5 - just return the guessed image, without this contour stuff, which often fails?
    paint_around_extract = False

    if paint_around_extract == True:
        #find the contours in the clipped area
        guessed_img_gray = cv2.cvtColor(guessed_img, cv2.COLOR_BGR2GRAY)
        #note that OTSU did NOT help here
        #NOTE that we did better with threshold at 150, vs 127 default
        _, guessed_thresh = cv2.threshold(guessed_img_gray, 150, 255, cv2.THRESH_BINARY_INV) 
        contours, hierarchy = cv2.findContours(guessed_thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    

        #now find the largest contours - which hopefully includes the contest box!
        areas = [(i, cv2.contourArea(cnt)) for i,cnt in enumerate(contours)]
        sorted_areas = sorted(areas, key = lambda x:x[1], reverse=True)
        
        res = []
        #only consider the top few
        for cnum, cnt in enumerate(contours):
            x,y,w,h = cv2.boundingRect(cnt)
            if w > 1000 and w < 1080:  #expected width of a regular contest!
                res.append((cnum, x, y, w, h))

        if len(res) < 1:
            logging.debug("contour search failed to find contest boundary, so just return the guessed margins")
            return guessed_img
        
        #of the right widths, select the one with the shorted height
        heights = sorted(res, key=lambda x:x[4]) #sort by height, ascending
        _, x, y, w, h = heights[0]
        
        #paint a nice color rect around the contour of the contest box that we found
        cv2.rectangle(guessed_img, (x, y), (x+w,y+h), box_color, 2 )
            

    return guessed_img

##################
### new routines that use template_matching to extract choicebox information
### used by both template generation and by ballot scanner
################

@dataclass
class ScoredRect: #Scored Rectangle - used internally by template matching stuff. Not externally.
    score: float = 0 #range 0-1
    tlx: int = -1  #top left x
    tly: int = -1
    brx: int = -1  #bottom right x
    bry: int = -1


####
# this is the main entrypoint for finding all choiceboxes using a mix of contour-finding and template-matching
# NOTE that this routine assumes you do NOT have a "choices.json" file to guide you
# therefore this is most useful for building new form templates, where there is NO "choices" data available
# it is slower than pure contour-based CB discovery, but is MUCH more accurate
####

def find_all_choiceboxes_using_contour_and_template_match(template_extractor):
    #use a combination of contour-based search to find columns
    # then template_match search on narrow vertical strips of the image to find the actual CB
    # returns sorted list of all cX,cY that can be found (cX,cY,column)
    
    #fixme - can we save time by using an existing gray/binary image?
    #image_gray     = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    #image_gray = template_extractor_class.
    #_, image_binary = cv2.threshold(image_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(template_extractor.template_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    #these need to be very selective and not overly sensitive, so use tight parameters
    #fixme - convert to global parameters about this class of forms?
    
    MAX_CHOICE_BOX_WIDTH = 160
    MAX_CHOICE_BOX_HEIGHT = 100
    MIN_CHOICE_BOX_WIDTH = 85
    MIN_CHOICE_BOX_HEIGHT = 50
    MIN_WIDTH_BETWEEN_COLUMNS = 200
    MAX_NUMBER_COLUMNS_EXPECTED = 3
    COLUMN_HALF_WIDTH_FOR_CHOICEBOX_SEARCH = 100
    TEMPLATE_MATCH_THRESHOLD = 0.7  #using checkerboard pattern requires this to be fairly low
    MIN_CB_IN_A_COLUMN = 1  #parsed templates can sometimes only recongize ONE CB in a column!!
    
    MIN_AREA = 5000
    MAX_AREA = 5400

    results = []

    start = time.time()

    cf = ColumnFinder(MAX_NUMBER_COLUMNS_EXPECTED, MIN_WIDTH_BETWEEN_COLUMNS)  #accumulates how many columns we discover

    for cnum, cnt in enumerate(contours):

        area = cv2.contourArea(cnt)
        
        #set a tight constraint - we can afford to miss a few, but a false-positive is bad
        if area >= MIN_AREA and area <= MAX_AREA:

            x,y,w,h = cv2.boundingRect(cnt)
            if (w < MIN_CHOICE_BOX_WIDTH or w > MAX_CHOICE_BOX_WIDTH) or \
                (h < MIN_CHOICE_BOX_HEIGHT or h > MAX_CHOICE_BOX_HEIGHT) :
                #print("warning {} rejecting contour={} - box width {} a/or height {} with area {} out of range".format(form_name_path.stem, cnum, w, h, area))
                continue

            M = cv2.moments(cnt)
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
                        
            #use choicebox as convenient way to name and hold stuff tho these get replaced later with "real" CB
            cb = ChoiceBox()
            cb.cnum = cnum
            cb.area = area
            cb.cX = cX
            cb.cY = cY
            
            cf.add_sample(cb.cX) #counts columns found
            results.append(cb)
    
    #results = deduce_and_assign_columns(results)
    #print(f"Elapsed time for contouring = {time.time() - start}")

    logging.debug(f"Initial contour-based choicebox extraction - column finder finds {cf.how_many_columns(MIN_CB_IN_A_COLUMN)} columns")
    #print(f"Initial choicebox extraction - column finder finds {cf.how_many_columns(MIN_CB_IN_A_COLUMN)} columns")
    
    start = time.time()
 
    #Second step - for each column, generate a vertical stripe of choiceboxes, and use template matching to find them
    
    cbf = ChoiceBoxTemplateMatcher(template_extractor.metadata)
    
    all_cb = []
    range = COLUMN_HALF_WIDTH_FOR_CHOICEBOX_SEARCH #search this many pix on either size of cX value
    rows, _, _ = template_extractor.template_image.shape # .shape returns (rows, cols, colors)

    for column_num, cX in cf.column_cX_iter(MIN_CB_IN_A_COLUMN):
        x = int(cX)
        #column goes from top to bottom, but is very narrow
        found = cbf.search_for_choiceboxes(column_num, template_extractor.template_image, x-range, 0 ,x+range, rows, TEMPLATE_MATCH_THRESHOLD)
        
        all_cb.extend(found)

    #print(f"Elapsed time for template_matching = {time.time() - start}")        
    #print(f"Done finding total of {len(all_cb)} choiceboxes")
    
    sorted_results = sorted(all_cb, key=lambda cb: (cb.column, cb.cY)) #both ascending
    return sorted_results #note these only have cY, cY, and column - nothing else yet

#####
## this is the main entry point for ballot-scanning's use of template-matching
###

def align_form_and_update_CB_locations(img, img_template, choices_dict, bscanner):
    #img = form, img_template = template for form (used only for debugging)
    #processing a new ballot (img) with choice_dict from reference template
    #goal is to update choices_dict to have actual cX, cY offsets of this ballot, rather than the template reference ballot
    #uses a combination of contour-mapping and template-matching to locate ALL choicesboxes, based on reference ballot

    #first, clone the template's choices_dict so we can update it with this form's actual CB locations.
    #be careful NOT to mess with the template's choices_dict

    cloned_choices_dict = copy.deepcopy(choices_dict)

    #then, vertically align form and shift x,y to "standard" position from top left
    aligned_form_image, affine_M = align_form_using_barcode_stripes(img, bscanner.form_path)

    ##debug_display_images((img,'before align'),(aligned_form_image, 'after align'))

    #first find as many CB contours as possible
    temp_gray = cv2.cvtColor(aligned_form_image, cv2.COLOR_BGR2GRAY)
    _, temp_binary = cv2.threshold(temp_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(temp_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    #these need to be very selective and not overly sensitive, so use tight parameters
    #fixme - convert to global parameters about this class of forms?
    
    MAX_CHOICE_BOX_WIDTH = 160
    MAX_CHOICE_BOX_HEIGHT = 100
    MIN_CHOICE_BOX_WIDTH = 85
    MIN_CHOICE_BOX_HEIGHT = 50

    COLUMN_HALF_WIDTH_FOR_CHOICEBOX_SEARCH = 100
    TEMPLATE_MATCH_THRESHOLD = 0.7  #using checkerboard pattern requires this to be fairly low
    
    MIN_AREA = 5000
    MAX_AREA = 5400

    results = []

    start = time.time()

    for cnum, cnt in enumerate(contours):

        area = cv2.contourArea(cnt)
        
        #set a tight constraint - we can afford to miss a few, but a false-positive is bad
        if area >= MIN_AREA and area <= MAX_AREA:

            x,y,w,h = cv2.boundingRect(cnt)
            if (w < MIN_CHOICE_BOX_WIDTH or w > MAX_CHOICE_BOX_WIDTH) or \
                (h < MIN_CHOICE_BOX_HEIGHT or h > MAX_CHOICE_BOX_HEIGHT) :
                #print("warning {} rejecting contour={} - box width {} a/or height {} with area {} out of range".format(form_name_path.stem, cnum, w, h, area))
                continue

            M = cv2.moments(cnt)
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
                        
            #use choicebox as convenient way to name and hold stuff tho these get replaced later with "real" CB
            cb = ChoiceBox()
            cb.cnum = cnum
            cb.area = area
            cb.cX = cX
            cb.cY = cY

            results.append(cb)
    
    #now match reference choiceboxes to the CB we found on the form
    #build linear list of CB, counting on shallow copy to permit updates to go deeper
    unmatched_CB  = [cb for contest in cloned_choices_dict['contests'] for cb in contest['choice_boxes']]
    updated = [False for cb in unmatched_CB]  #track which ones we have done
    
    #print(f"contour matching found {len(results)} CB on ballot")
    logging.debug(f"form:{bscanner.form_path.name} contour-matching found {len(results)} CB on ballot")
    #print(f"choices dict has {len(unmatched_CB)} CB to be updated")
    logging.debug(f"form:{bscanner.form_path.name} template dict has {len(unmatched_CB)} CB to be updated")

    #changed to 70 after some very skewed forms failed at 50
    #no, leave at 50 for now.
    CLOSE_ENOUGH = 50 #70 seems to be able to handle difference between "v1" and "v2" versions of same precinct-page

    dist = lambda f, r: np.sqrt( (f.cX - r['cX'])**2 + (f.cY - r['cY'])**2   )
    distances = []
    x_gaps = [] #measured from FORM to TEMPLATE
    y_gaps = []

    #find closest one
    best_d = 100000000
    best_i = -1
    best_r_cb = None

    for f_cb in results: #the ballot form
        for i, r_cb in enumerate(unmatched_CB):  #the reference template
            if updated[i] == False:  #only consider unmatched template reference CBs
                d = dist(f_cb, r_cb)
                if d < best_d:
                    best_d = d
                    best_i = i
                    best_r_cb = r_cb
        #have best choice here so update reference CB with actual CB (reference will be stored with output JSON)
        if best_d < CLOSE_ENOUGH:
            #print(f"best distance was {best_d} - so updating reference CB {best_r_cb['cX']}, {best_r_cb['cY']} with actual CB {f_cb.cX}, {f_cb.cY}")
            x_gaps.append(best_r_cb['cX'] - f_cb.cX)
            y_gaps.append(best_r_cb['cY'] - f_cb.cY)
            best_r_cb['cX'] = f_cb.cX
            best_r_cb['cY'] = f_cb.cY
            #and flag as updated
            updated[best_i] = True
            distances.append(best_d)
            best_d = 10000000 
        else:
            distances.append(best_d)
            #print(f"closest distance {best_d} was too far - contours can't map #{best_i}")       
            logging.debug(f" Form:{bscanner.form_path.name} - closest distance: {best_d} was too far - contours can't map point #{best_i}")
    
    #at this point, only CB that were not found by contours remain updated == False
    to_do_count = len( [item for item in updated if item == False] )
    #print(f"After contour matching, {to_do_count} CB remained unmatched")
    logging.debug(f"form:{bscanner.form_path} After contour matching {to_do_count} CB remained unmatched - now try template-sliding")
    #print(f"x-gaps = {x_gaps}")
    #print(f"y-gaps = {y_gaps}")

    #for each remaining un-updated CB, we will search using template-matching
    
    cbtm = ChoiceBoxTemplateMatcher(bscanner.metadata)

    #use x and y gaps to "hedge" the search since presumably the form is linearly shifted for some reason
    if len(x_gaps) > 0 and len(y_gaps) > 0:
        avg_x_gap = np.mean(np.array(x_gaps))
        avg_y_gap = np.mean(np.array(y_gaps))
    else:
        avg_x_gap = 0
        avg_y_gap = 0

    for i, cb in enumerate(unmatched_CB):
        if updated[i] == True:
            continue
        
        #coordinates of area to search - just around where we expected the CB to be, from metadata
        SEARCH_RANGE_WIDE = 100 #search window has to be bigger than the template
        SEARCH_RANGE_HIGH = 60 #needs to be tighter going up/down to avoid finding adjacent CB

        #gaps are measured from Template to Form so a positive gap is substracted from our search center point
        search_cX = cb['cX'] - int(avg_x_gap)
        search_cY = cb['cY'] - int(avg_y_gap)

        found = cbtm.search_for_choiceboxes(-1, aligned_form_image, search_cX-SEARCH_RANGE_WIDE, search_cY-SEARCH_RANGE_HIGH,
                                                search_cX+SEARCH_RANGE_WIDE, search_cY+SEARCH_RANGE_HIGH, TEMPLATE_MATCH_THRESHOLD)
        if len(found) == 0:
            #print(f"OOPS - template match for {cb} found NO template!!")
            #fix me = add loop to select closest one!
            logging.debug(f"form: {bscanner.form_path.name} template match found NO template match for a choicebox!")            
        elif len(found) > 1:
            #print(f"OOPS - template match for {cb} found MORE than one templates for choicebox. Found: {len(found)} templates")
            #print(f"searching for :{cb} found first: {found[0]} second:{found[1]}")
            logging.debug(f"form: {bscanner.form_path.name} template match found more than 1 match. Skipping this choicebox!")
        else:
            #got a single good match so update the reference CB with the found coordinates
            cbi = found[0]
            d = dist(cbi, cb)
            #print(f"distance: {d}  - updating reference CB {cb['cX']}, {cb['cY']} with actual CB {cbi.cX}, {cbi.cY}")
            if d > CLOSE_ENOUGH:
                logging.warning(f" Form:{bscanner.form_path.name} - assigned template match for {cb['cX']},{cb['cY']} was FARTHER than expected: {d} - review form!")
            cb['cX'] = int(cbi.cX)
            cb['cY'] = int(cbi.cY)
            updated[i] = True
            distances.append(d)

    avg_distance = np.mean(np.array(distances))
    logging.debug(f" Form:{bscanner.form_path.name} - Average distance for choicebox correction was {avg_distance}")
    
    #at this point, all CB in the reference template should be updated
    #if not, then we can try the homology approach, which uses different assumptions
    to_do_count = len( [item for item in updated if item == False] )
    #print(f"Verify - After contour matching, {to_do_count} CB remained unmatched")

    #fixme add to image logger
    #debug_show_stuff(img_template, img, aligned_form_image, choices_dict, cloned_choices_dict)
    
    if to_do_count > 0:
        #print(f" Form:{bscanner.form_path.name} - UNABLE to match all choiceboxes between form and reference - left over = {to_do_count} Will try Homology next")
        logging.warning(f"Form:{bscanner.form_path.name} - Contour/slide-template failed to find all choiceboxes. Leftover = {to_do_count}")
        logging.warning(f"Form:{bscanner.form_path.name} - Will fall-back and try Homology mapping - please verify results")
        return  None, None, "", None #return Nones to signal contour/slide-template failure

    return  aligned_form_image, affine_M, "", cloned_choices_dict #return the aligned form and the updated copy of choices_dict

#used only for debugging
def debug_show_stuff(template_img, form_img, form_img_registered, template_dict, cloned_dict):
    #draw_points(template_img, template_keypoints)
    #draw_points(form_img, form_keypoints)
    for contest in template_dict['contests']:
        for cb in contest['choice_boxes']:

            show_choice_box_on_image(template_img, cb['cX'], cb['cY'], (0,0,255))

    for contest in cloned_dict['contests']:
        for cb in contest['choice_boxes']:

            #show_choice_box_on_image(template_img, cb['cX'], cb['cY'], (0,0,255))
            temp_img_gray = cv2.cvtColor(form_img_registered, cv2.COLOR_BGR2GRAY)
            _, temp_img_binary = cv2.threshold(temp_img_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
            score, ul_x, ul_y, lr_x, lr_y = score_inside_choice_box(form_img_registered, temp_img_binary, cb['cX'], cb['cY'])
            show_score_on_image(form_img_registered, cb['cX'], cb['cY'], score, (0,0,255))
            show_choice_box_on_image(temp_img_binary, cb['cX'], cb['cY'], (255,0,0))
            show_choice_box_on_image(form_img_registered, cb['cX'], cb['cY'], (0,0,255))

    fig, ax = plt.subplots(1,4, figsize=(22,12))
    ax[0].imshow(template_img)
    ax[1].imshow(form_img)
    ax[2].imshow(form_img_registered)
    ax[3].imshow(temp_img_binary, cmap='gray')    
    plt.show()

###
# this routine slides the match-seeking templates over a form to match against choiceboxes
# initially there were two templates - a solid rectangle (e.g. a filled in CB) and an open outlined CH
# but it turns out that a single "checkerboard" outline is sufficient to find both marked and unmarked CB
###
class ChoiceBoxTemplateMatcher():
    def __init__(self, metadata):
        self.metadata = metadata
        #temp_img = cv2.imread("one_choicebox.jpg")
        #temp_gray = cv2.cvtColor(temp_img, cv2.COLOR_BGR2GRAY)
        #self.open_template_binary = cv2.threshold(temp_gray, 127, 255, 
    
        temp_gray = cv2.cvtColor(self.metadata.checkerboard_match_template_image, cv2.COLOR_BGR2GRAY)
        self.checkerboard_template_binary = cv2.threshold(temp_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
        self.th, self.tw = self.checkerboard_template_binary.shape # .shape returns (rows, cols)
        #plt.imshow(self.closed_template_binary, cmap='gray')
        #plt.show()
        
    def search_for_choiceboxes(self, column_num, img, tlx, tly, brx, bry, match_threshold):
        #search in img for CB within rect tlx,tly,brx,bry
        #search with the checkerboard pattern
        #return list of found CB centroids
        #assume should only find one or at most two so start very selective and iterate?

        #template_matching is compute intensive, so we subset the img to the smallest search area caller can provide
        
        search_img = img[tly:bry, tlx:brx]  #img[rows, cols]
        search_img_offset_x = tlx #add these back in returned values to reference entire image
        search_img_offset_y = tly

        #plt.imshow(search_img)
        #plt.show()

        #fixme - can we pass in an already binary image? save some CPU?
        search_img_gray = cv2.cvtColor(search_img, cv2.COLOR_BGR2GRAY)
        search_image_binary = cv2.threshold(search_img_gray, 127, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]

        found_cbs = []

        #the key routine - using normalized cross correlation between template and image (range 0-1)
        matches_checkerboard = cv2.matchTemplate(search_image_binary, self.checkerboard_template_binary, cv2.TM_CCORR_NORMED) 
        brc_checkerboard_accum = BestMatchesAccumulator(0.1, self.tw, self.th)
        brc_checkerboard_accum.add_all_matches(matches_checkerboard, match_threshold)        
        
        for ct in brc_checkerboard_accum.centroid_iter():
            cb = ChoiceBox()
            cb.cX = int(ct[0] + search_img_offset_x) #downstream expects integers
            cb.cY = int(ct[1] + search_img_offset_y)
            cb.column = column_num

            found_cbs.append(cb)
    
        return found_cbs


class BestMatchesAccumulator():
#template matching generates lots of false-positive matches
#this class accumulates only the template rectangles with best match score, rejecting any similar rectangles lower scores

    def __init__(self, min_overlap_to_be_considered_a_new_rect, template_width, template_height):
        self.min_overlap = min_overlap_to_be_considered_a_new_rect #less than this overlap means it's a separate match
        self.best_rectangles = list() #list of ScoredRect()'s'
        self.template_width = template_width  #the width of the sliding template (an image of a single choicebox in our case)
        self.template_height = template_height

    def add_all_matches(self, template_results, template_threshold):
        #spin thru template results, filter by threshold, and accumulate the non-overlaps

        all_rect = [] #temp list pre-sort

        match_locations = np.where(template_results >= template_threshold) #select matches that are above threshold
        
        for (x, y) in zip(match_locations[1], match_locations[0]):  #note reversal to get x,y
            score = template_results[y,x]            
            new_sr = ScoredRect(score, x, y, x+self.template_width, y+self.template_height)
            all_rect.append(new_sr)
        
        sorted_sr = sorted(all_rect, key=lambda sr: sr.score, reverse=True)
        #print(f"Number rect to consider = {len(sorted_sr)}")
        
        for sr in sorted_sr:
            #add them in decreasing score order - so the best come first
            self._add_matching_rectangle(sr)
        
        
    def _add_matching_rectangle(self, new_sr):
        #NOTE - must add rects by best-score first!!
        #see if the new rectangle overlaps with existing best rectangles
        for sr in self.best_rectangles:
            #a = np.array([sr.tlx,sr.tly,sr.brx,sr.bry])
            #b = np.array([new_sr.tlx,new_sr.tly,new_sr.brx,new_sr.bry])
            iou = get_iou([sr.tlx,sr.tly,sr.brx,sr.bry], [new_sr.tlx,new_sr.tly,new_sr.brx,new_sr.bry])
            #iou = get_iou(a, b)
            #print(f" IOU = {iou}")
            if iou < self.min_overlap:
                #does not overlap (much) with this one, keep checking for overlap with others
                #print(f"iou={iou} adding new rect")
                continue
            else:
                #overlaps too much to keep, so ignore
                return
            
        #if we get here - doesn't overlap with any existing rect, so we add it as a new match
        self.best_rectangles.append(new_sr)
        return

    def rectangle_iter(self):
        return [ sr for sr in self.best_rectangles ]

    def centroid_iter(self):
        return [ (sr.tlx + (sr.brx-sr.tlx)/2, sr.tly + (sr.bry-sr.tly)/2) for sr in self.best_rectangles ]

    def how_many(self):
        return len(self.best_rectangles)

    def dump(self):
        for sr in self.best_rectangles:
            print(f"cX:{sr.tlx + (sr.brx-sr.tlx)/2} cY:{sr.tly + (sr.bry-sr.tly)/2} score:{sr.score}")
        
    def show_on_image(self, img):
        for sr in self.rectangle_iter():
            cv2.rectangle(img, (int(sr.tlx),int(sr.tly)), (int(sr.brx),int(sr.bry)), (255,0,0), 2)
        return img

#@jit(nopython=True) #this did NOT speed it up?
def get_iou(a, b, epsilon=1e-5):
    #get Intersection Of Union
    """ Given two boxes `a` and `b` defined as a list of four numbers:
            [x1,y1,x2,y2]
        where:
            x1,y1 represent the upper left corner
            x2,y2 represent the lower right corner
        It returns the Intersect of Union score for these two boxes.

    Args:
        a:          (list of 4 numbers) [x1,y1,x2,y2]
        b:          (list of 4 numbers) [x1,y1,x2,y2]
        epsilon:    (float) Small value to prevent division by zero

    Returns:
        (float) The Intersect of Union score.
    From: http://ronny.rest/tutorials/module/localization_001/iou/
    """

    # COORDINATES OF THE INTERSECTION BOX
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])

    # AREA OF OVERLAP - Area where the boxes intersect
    width = (x2 - x1)
    height = (y2 - y1)
    # handle case where there is NO overlap
    if (width<0) or (height <0):
        return 0.0
    area_overlap = width * height

    # COMBINED AREA
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    area_combined = area_a + area_b - area_overlap

    # RATIO OF AREA OF OVERLAP OVER COMBINED AREA
    #iou of 1 means total overlap
    iou = area_overlap / (area_combined+epsilon)
    return iou

####
# quick hack to discover how many columns of choiceboxes were found when searching for all choiceboxes
# and to generate the "average" location of each column (e.g. the x-axis)
# NOTE that this depends on only high-quality choicebox location data to drive it - so make the contour match very tight!
####

class ColumnFinder():
    def __init__(self, size, delta):
        self.size = size   #max num columns expected
        self.delta = delta #min pixel offset to start a new column
        self.xm = np.zeros((self.size,))
        self.cnt = np.zeros((self.size,))

    def _update_column_avg(self, x, position):
        if self.cnt[position] == 0:
            self.xm[position] = x
            self.cnt[position] = 1
        else:
            #keep running average of cX value - should we be using median?
            self.xm[position] = ((self.cnt[position] * self.xm[position]) + (x)) / (self.cnt[position] + 1)
            self.cnt[position] += 1

    def add_sample(self, x):
        #returns the column that sample was assigned to (first col = 1)
        for i in range(self.size):
            if (abs(x - self.xm[i]) < self.delta):
                self._update_column_avg(x, i)
                return i+1
            if self.cnt[i] == 0:
                self._update_column_avg(x, i)
                return i+1
        
        #if here, we overflowed
        logging.warning("ColumnFinder overflow - detected more columns than expected. Review Form!")
        return
    
    def column_cX_iter(self, threshold):
        #threshold is min number contributions to consider this a column
        #note that some columns have only TWO choiceboxes.
        #can a column have only ONE choicebox? ==>> YES, particularly if contour parsing was messed up by X-marks and check-marks!!
        #returns column number (based on 1 = first col) and average cX for that column
        return [ (i+1, self.xm[i]) for i in range(self.size) if self.cnt[i] >= threshold ]
    
    def how_many_columns(self, threshold):
        return len([self.cnt[i] for i in range(self.size) if self.cnt[i] >= threshold])
    
    def dump(self):
        for i in range(self.size):
            print(f"{i} xm:{self.xm[i]} count:{self.cnt[i]}")

def debug_display_images(*image_name_tuples, figsize=(22,12)):
    #call with variable number of (image, title) pairs
    if len(image_name_tuples) == 0:
        return
    num_plots = len(image_name_tuples)
    
    fig, ax = plt.subplots(1, num_plots, figsize=figsize, tight_layout=True)
    
    for i, tup in enumerate(image_name_tuples):
        img = tup[0]
        label = tup[1]
        ax[i].set_xlabel(label)
        if len(img.shape) == 3:
            ax[i].imshow(img)
        elif len(img.shape) == 2:
            ax[i].imshow(img, cmap='gray')
        else:
            ax[i].imshow(img)
    
    plt.show()
