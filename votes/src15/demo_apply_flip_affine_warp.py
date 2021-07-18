import cv2
import numpy as np
from pathlib import Path
import json

import matplotlib.pyplot as plt
plt.rcParams['figure.figsize'] = [8, 10]

def align_and_warp_image(image, M_matrix, H_matrix):
    #applies an affine transformation to the image, using the M matrix
    #then if H_matrix is not None, then applies a warpPerspective transformation
    #returns a new transformed image.
    #H_ and M_ matrices should be numpy arrays
    
    #assumes image is (rows, cols, colors) but could easily be made to work with gray or binary images
    
    rows, cols, _ = image.shape
    
    aligned_image = cv2.warpAffine(image, M_matrix, (cols,rows))    

    #aligned_image = image
    
    if H_matrix is not None:
        aligned_warped_image = cv2.warpPerspective(aligned_image, H_matrix, (cols, rows))
        return aligned_warped_image
    else:
        return aligned_image


def show_choiceboxes(image, image_dict):
    #quick hack to paint choicebox coords onto the flipped, aligned and warped image for verification
    for contest in image_dict['contests']:
        for cb in contest['choices']:
            ulcx = cb['location_ulcx']
            ulcy = cb['location_ulcy']
            lrcx = cb['location_lrcx']
            lrcy = cb['location_lrcy']

            cv2.rectangle(image, (ulcx, ulcy), (lrcx, lrcy), (255,0,0), 2)

if __name__ == "__main__":

    path_to_image = Path("/Volumes/Data/david-data/Dropbox/david/random2/246500.jpg")
    path_to_json = Path("/Volumes/Data/david-data/Dropbox/PythonProjects-dpm/Ballot_tests/246500.json")

    #load image
    original_image = cv2.imread(str(path_to_image))

    #load corresponding JSON (or pull it from DB somewhere)
    with open(path_to_json) as f:
        raw_json = f.read()
        
    #convert JSON to python data structs
    image_dict = json.loads(raw_json)
        
    #extract M and maybe H matrices
    M_matrix = np.array(image_dict.get("M_matrix"))

    if image_dict.get("H_matrix"):
        H_matrix = np.array(image_dict['H_matrix'])
    else:
        H_matrix = None
        
    #IMPORTANT - see if image needs to be flipped. Alignement depends on image being upright
    if image_dict.get('flipped_form') == True:
        image = cv2.flip(original_image, -1) # -1 means flip both H and V, should give 180
    else:
        image = original_image

    #apply align_and_warp
    aligned_image = align_and_warp_image(image, M_matrix, H_matrix)

    #mark the choiceboxes to verify that it's working
    show_choiceboxes(aligned_image, image_dict)

    #show it, compared to original
    fig, ax = plt.subplots(1,2, figsize=(18,12))
    ax[0].imshow(original_image)
    ax[1].imshow(aligned_image)
    fig.tight_layout()
    plt.imshow(aligned_image)
    plt.show()