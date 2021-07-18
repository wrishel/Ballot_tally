import cv2
from pathlib import Path
import time

from image_logger import ImageLogger #image_logger.py needs to be in the same directory as this program


def an_image_annotator(img_path, precinct, some_data):

    test_image = cv2.imread(str(img_path)) #open image
    sub_image = test_image[0:400, 0:800] #extract desired sub image
    cv2.putText(sub_image, f"{some_data}",(200,200), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0,0,255), 2)

    #create a optional message describing the annotation
    message = f"This is image: {img_path.stem}\n"
    message += f"This is precinct: {precinct}"
    return sub_image, message


path_to_image_log_file = Path("../errors/test_image_logger.html")


if __name__ == "__main__":

    #instantiate an image logger
    imlog = ImageLogger(path_to_image_log_file, 20)  #set default scale to 20% of original

    #get a path to an image
    image_path = Path("../wr_ballot_7.jpg")

    #call the annotator as you work thru the images

    for i in range(10):

        #annotate an image somehow
        annotated_image, message = an_image_annotator(image_path, "1S--2", "some arbitrary additional data")

        #add the annotated image to the logger
        #image_path is the path to the image, if you want a click to open that file, or pass as None for no linking
        imlog.log_image(annotated_image, 35, time.time(), image_path, message )  #scale this to 15% of original

    print("done")