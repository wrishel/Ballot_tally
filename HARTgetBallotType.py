""" Obtain the ballot type ID from a HART ballot by bar-code or, optical recognition.

    March 2020 -- Humboldt country has newly implemented the Hart Intercivic Verity system.

    This code was written for the Humboldt Election Transparency Project and is licensed
    but under the MIT License and the Beer License.

    Modified March 2020 for new HARTS format, where party and precinct don't
    seem to be discrete fields in the barcode.

    Todo: consider OCR-ing the precinct ID and party from the ballot directly.
"""

# Performance measured on PowerBook (2015) MacOS Jan 17, 2020
#
# time in pyzbar starts at .0059 and grows slowly       todo: why?
# total elapsed time starts at .245 seconds. Most of the difference is opening and
# subsetting the image in PIL



# import tesseract
from PIL import Image
from PIL import ImageFile  # fix for IOError('image file is truncated ...
ImageFile.LOAD_TRUNCATED_IMAGES = True
from pyzbar.pyzbar import decode, ZBarSymbol
import codecs
import os
import re
import sys
import time
from election_paramaters.pctids_2018_11 import pctids_2018_11
# import logging        # logging commented out, should be used by caller if wanted

def b2str(binbytes):
    """Convert binary octets to Python3 string.

       Currently required for pyzbar output. If arg is None, return None"""

    if binbytes is None: return None
    return ''.join(chr(x) for x in binbytes)

def pct_id(barcode):
    if barcode is None: return None
    return barcode[3:9]  # 4th through 9th characters

def party_id(barcode):
    if barcode is None: return None
    return barcode[9:11]  # 10th and 11th characters

def page_num(barcode):
    """Call with lower barcode. Return the page number as an integer"""

    if barcode is None: return None
    return int(barcode[7])     # 8th car, lower barcode

class Image_juggler:
    '''Hold a Pillow image but don't invert unless asked.'''

    def __init__(self, image):
        self.img = image
        self.inverted_img = None

    def image(self):
        return self.img

    def inverted(self):
        if self.inverted_img is None:
            self.inverted_img = self.img.transpose(Image.ROTATE_180)
        return self.inverted_img


class HARTgetBallotType:
    """Get a HART ballot precinct ID (six digits) and page number from the barcode.

       There is code commented out here that would use tesseract to OCR the information
       if pyzbar fails. But pyzbar is working well and tesseract is yet another library
       to load and maintain versions. The code was tested and worked, at one time"""

    def __init__(self, dpi):
        """barcode_data format {barcode: (precinct, party)}"""

        self.DPI = dpi  # todo: get make an argument
        inchToPx = lambda x: int(float(x) * self.DPI + .5)

        # Hart Intercivic Verity Ballot Locations
        #
        # Barcodes run vertically in the left margin.
        #
        # The lower barcode contains the page number (1 - N) of the ballot
        #

        class bc_params: pass
        self.lower_bc = bc_params()
        self.lower_bc.TOP_LEFT_X_PX = inchToPx(0.15)
        self.lower_bc.TOP_LEFT_Y_PX = inchToPx(11.4)
        self.lower_bc.BOT_RIGHT_X_PX = inchToPx(0.7)
        self.lower_bc.BOT_RIGHT_Y_PX = inchToPx(13.8)
        self.lower_bc.validate = re.compile(r'^\d{12}$')

        # The upper barcode identifies the precinct and (for primaries) the party.
        #
        self.upper_bc = bc_params()
        self.upper_bc.TOP_LEFT_X_PX = inchToPx(0.15)
        self.upper_bc.TOP_LEFT_Y_PX = inchToPx(.05)
        self.upper_bc.BOT_RIGHT_X_PX = inchToPx(0.7)   # this is actually pretty tight
        self.upper_bc.BOT_RIGHT_Y_PX = inchToPx(3.5)
        self.upper_bc.validate = re.compile(r'^\d{14}$')

    def getBallotBarcodes(self, file):
        """Return the barcodes used to identify the attributes of a ballot.

           These can be further interpreted using functions precinct_id(), party_id(),
           and page_num().

           Handles the possibility that the image is upside down.

            :param  fd          path to file
            :return (str, str)  the upper and lower barcodes
        """

        self.upsideDownImage = None
        # logging.info(file)
        # print(f'file={file}')
        image = Image.open(file)
        image.load()
        imjuglr = Image_juggler(image)
        inverted = False
        barcode_upper = self._scanBarcode(imjuglr.image(), self.upper_bc)
        if barcode_upper is None:
            barcode_upper = self._scanBarcode(imjuglr.inverted(), self.upper_bc)
            inverted = barcode_upper is not None

        if inverted:
            barcode_lower = self._scanBarcode(imjuglr.inverted(), self.lower_bc)
        else:
            barcode_lower = self._scanBarcode(imjuglr.image(), self.lower_bc)

        return (barcode_upper, barcode_lower)

    # # This class is is used with the With statement, although this is
    # # not necessary since we removed Tesseract
    # #
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # self.tessAPI.End()
        return False        # todo: if terminated by exception raise it now

    def _scanBarcode(self, image, bc_params):
        """Capture the ballot ID from the barcode.

        :param Image image:  a Pillow image of the full scanned ballot side.
        :param an object with info for locating and validating the barcode
        :return string: the bar code digits or None
        """
        if False:
            image.show()
            image.save(f'/Users/Wes/Desktop/{self.output_image_cntr}.jpg')
            self.output_image_cntr += 1
        # image.save('/Users/Wes/Desktop/fullimage.jpg')
        bcimage = image.crop((bc_params.TOP_LEFT_X_PX,
                            bc_params.TOP_LEFT_Y_PX,
                            bc_params.BOT_RIGHT_X_PX,
                            bc_params.BOT_RIGHT_Y_PX))
        bcimage.load()   # over ride lazy op
        # bcimage.save('/Users/Wes/Desktop/barcode.jpg')
        if False:
            bcimage.show()
            bcimage.save(f'/Users/Wes/Desktop/{self.output_image_cntr}.jpg')
            self.output_image_cntr += 1

        barcodes = decode(bcimage, symbols=[ZBarSymbol.I25])

        # Pyzbar can return some ghost barcodes.
        #
        for i in reversed(range(len(barcodes))):
            bcd = barcodes[i]
            bcd_data = bcd.data.decode("utf-8")
            if bcd.rect.width == 0 or not bc_params.validate.match(bcd_data):
                del barcodes[i]

        if len(barcodes) == 1:
            return b2str(barcodes[0].data)
        return None
#
#  -----------------------------------------  Unit Test  -----------------------------------------
#
global bc_count, bc_proctime, ocr_count, ocr_proctime
bc_count, bc_proctime, ocr_count, ocr_proctime = 0, 0.0, 0, 0.0

if __name__== '__main__':
    import fnmatch
    barcode_data = {
        '000000.jpg': ('15317000107106', '170001', '07', '1'),
        '000001.jpg': ('15317000107106', '170001', '07', '2'),
        '000002.jpg': ('15317000101104', '170001', '01', '1'),
        '000004.jpg': ('15317000102101', '170001', '02', '1'),
        '000042.jpg': ('15317000103108', '170001', '03', '1'),
        '000284.jpg': ('15317000104105', '170001', '04', '1'),
        '000690.jpg': ('15317000205109', '170002', '05', '1'),
        '001030.jpg': ('15317000405103', '170004', '05', '1'),
        '002502.jpg': ('15317001306102', '170013', '06', '1'),
        '012934.jpg': ('15317008808104', '170088', '08', '1')
    }
    images_path = f'{os.path.dirname(os.path.abspath(__file__))}\\test_data\\HARTgetBalloType'
    pths = []

    with HARTgetBallotType(300) as hgbt:
        for filename in sorted(barcode_data.keys()):
            try:
                (barc_upper, barc_lower) = hgbt.getBallotBarcodes(f'{images_path}\\{filename}')
                pctid = pct_id(barc_upper)
                partyid = party_id(barc_upper)
                pagenum = page_num(barc_lower)
                t = (barc_upper, pctid, partyid, pagenum)
                if barcode_data[filename] != t:
                    print(f'error: {filename}: {t}', file=sys.stderr)

            except Exception as e:
                sys.stderr.write("Exception on file '{}'\n{}\n".format(filename, repr(e)))
                continue

# code formerly used t0 get the ballt id with OCR.
        # Printed number runs vertically in left margin. These crops
        # allow for misalignment but aren't too generous because the OCR
        # algorithm is sensitive to dirt on the page.
        #
        # self.OCR_TOP_LEFT_X_PX = inchToPx(0.075)
        # self.OCR_TOP_LEFT_Y_PX = inchToPx(3.1)
        # self.OCR_BOT_RIGHT_X_PX = inchToPx(0.53)
        # self.OCR_BOT_RIGHT_Y_PX = inchToPx(5.0)
        # self.OCR_DELTA_X_PX = inchToPx(0.1)
        # self.OCR_DELTA_Y_PX = inchToPx(0.1)


    # def _ocrBallotID(self, image, deltaX=0, deltaY=0, upsideDown=False):
    #     """OCR the number that indicates the ballot format
    #        and contains the key to the precinct.
    #
    #     :param Image image:  a Pillow image of the full scanned ballot side.
    #     :param int deltaX: a cushion around the target number when scanning upside down.
    #     :param int deltaY: a cushion around the target number when scanning upside down.
    #     :return string: the OCR'pct_tots digits or None
    #
    #     """
    #
    #     # The error rate could probably be improved here by thresholding all
    #     # pixels of the cropped image with substantial color (i.e., not white or
    #     # black) to white. Performance penalty would be small
    #     # because most pages are handled with bar codes.
    #     #
    #     if upsideDown:
    #         if not self.upsideDownImage:
    #             self.upsideDownImage = image.transpose(Image.ROTATE_180)
    #         cropped = self.upsideDownImage.crop(
    #             (self.OCR_TOP_LEFT_X_PX - self.OCR_DELTA_X_PX,
    #              self.OCR_TOP_LEFT_Y_PX,
    #              self.OCR_BOT_RIGHT_X_PX,
    #              self.OCR_BOT_RIGHT_Y_PX + self.OCR_DELTA_Y_PX)).transpose(Image.ROTATE_270)
    #
    #     else:
    #         cropped = image.crop((self.OCR_TOP_LEFT_X_PX,
    #                               self.OCR_TOP_LEFT_Y_PX,
    #                               self.OCR_BOT_RIGHT_X_PX,
    #                               self.OCR_BOT_RIGHT_Y_PX)).transpose(Image.ROTATE_270)
    #
    #     self.tessAPI.SetImage(cropped)
    #     txt = tesserocr.image_to_text(image)
    #     # logging.info(txt)
    #
    #     # Ignore embedded spaces in OCR'pct_tots text. Even thought we specify only digits Tesseract
    #     # may embed spaces in the text.
    #     #
    #     txt = txt.replace(' ', '')
    #     # logging.info(txt)
    #     if self.goodnum.match(txt):
    #         self.successfulMode = 'o'
    #         # logging.info(txt)
    #         return txt
    #     if upsideDown:
    #         logging.info('try upside down')
    #         return None  # already tried upside down, so give up
    #     return self._ocrBallotID(image, deltaX, deltaY, True)  # try upside down
