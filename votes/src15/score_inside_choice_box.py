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
    
    # version 1.5 code
    # sub_area = img_binary[ul_y:lr_y, ul_x:lr_x] #do I need +1?
    # score = cv2.countNonZero(sub_area)
    
    #try a new version that converts fainter gray marks into black (better threshold)
    sub_area = img[ul_y:lr_y, ul_x:lr_x]
    sub_area_gray = cv2.cvtColor(sub_area, cv2.COLOR_BGR2GRAY)
    sub_area_inv_binary = cv2.threshold(sub_area_gray, 200, 255, cv2.THRESH_BINARY_INV)[1]
    score = cv2.countNonZero(sub_area_inv_binary)

    return (score/area) * 100, ul_x, ul_y, lr_x, lr_y