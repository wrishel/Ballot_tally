from pyzbar import pyzbar
import cv2
import logging
from pathlib import Path
from scanner_constants_and_data_structures import *

def check_for_flipped_form(img, form_path):
    #this is a hack to see if the form might be upside down.
    #this ONLY GETS CALLED when we already know the form's precinct and page
    # so we only need to try for the UL barcode
    # return False if no flip needed or True if flip required

    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.medianBlur(img_gray,5)
        
    upper_left = \
        img_gray[UPPER_LEFT_BAR_CODE_Y: UPPER_LEFT_BAR_CODE_Y + UPPER_LEFT_BAR_CODE_HEIGHT , \
            UPPER_LEFT_BAR_CODE_X: UPPER_LEFT_BAR_CODE_X + UPPER_LEFT_BAR_CODE_WIDTH ]
    try:
        ul_bars = pyzbar.decode(upper_left, symbols=[pyzbar.ZBarSymbol.I25])
    except:
        ul_bars = None

    if ul_bars and select_good_barcode(ul_bars, 14):
        #we are fine with no flip
        return False

    else:    
        #try flipped version of image
        flipped_img = cv2.flip(img, -1)
        upper_left = \
            flipped_img[UPPER_LEFT_BAR_CODE_Y: UPPER_LEFT_BAR_CODE_Y + UPPER_LEFT_BAR_CODE_HEIGHT , \
            UPPER_LEFT_BAR_CODE_X: UPPER_LEFT_BAR_CODE_X + UPPER_LEFT_BAR_CODE_WIDTH ]
        try:
            ul_bars = pyzbar.decode(upper_left, symbols=[pyzbar.ZBarSymbol.I25])
        except:
            ul_bars = None

        if ul_bars and select_good_barcode(ul_bars, 14):
            #flip fixed our problem - return true
            return True    
    
    return False #we can't tell, so don't try


def extract_bar_codes(img, form_path):
    #return barcode info for top left and lower left
    #uses the constants to define the vertical stripes
    #img can be gray or color
    #IF EITHER bar code is missing, we will FAIL (in caller)
    
    #lets try pre-processing the image to reduce errors?
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_gray = cv2.medianBlur(img_gray,5)
    
    #thresholding to binary did NOT WORK!
    #img_bw = cv2.threshold(img_gray, 127, 255, cv2.THRESH_OTSU)[1]
    
    upper_left = \
        img_gray[UPPER_LEFT_BAR_CODE_Y: UPPER_LEFT_BAR_CODE_Y + UPPER_LEFT_BAR_CODE_HEIGHT , \
            UPPER_LEFT_BAR_CODE_X: UPPER_LEFT_BAR_CODE_X + UPPER_LEFT_BAR_CODE_WIDTH ]
    
    lower_left = \
        img_gray[LOWER_LEFT_BAR_CODE_Y: LOWER_LEFT_BAR_CODE_Y + LOWER_LEFT_BAR_CODE_HEIGHT , \
            LOWER_LEFT_BAR_CODE_X: LOWER_LEFT_BAR_CODE_X + LOWER_LEFT_BAR_CODE_WIDTH ]
    try:
        ul_bars = pyzbar.decode(upper_left, symbols=[pyzbar.ZBarSymbol.I25])
    except:
        ul_bars = None
    
    try:
        ll_bars = pyzbar.decode(lower_left, symbols=[pyzbar.ZBarSymbol.I25])
    except:
        ll_bars = None
    
    #pass errors to the caller by returning NONE
    
    ul_data = select_good_barcode(ul_bars, 14)
    
    #if ul_data is None:
    #    logging.warning("Form: {} BAR CODE FAIL - upper left".format(form_path.name))
     
    ll_data = select_good_barcode(ll_bars, 12)
    
    #if ll_data is None:
    #    logging.warning("Form: {} BAR CODE FAIL - lower left".format(form_path.name))
        
    if ul_data is None or ll_data is None:
        return None, None
    else:
        return ul_data, ll_data

def select_good_barcode(bar_matches, expected_length):
    #zbar can return partial matches or other noisy codes.
    #if there is at least one code that passes tests, we'll use that one
    #return bc decoded data if good, None if nothing passes
    
    for bc in bar_matches:
        if bc.type != 'I25':
            continue
        data = bc.data.decode("utf-8")
        if len(data) != expected_length:
            continue
        #if we get here, we have a good candidate
        return(data)
    #if we get here, nothing passed
    return None
