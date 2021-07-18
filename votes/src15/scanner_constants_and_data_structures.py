#NOTE - many of these are obsolete or are overridden locally
#PLEASE FIXME!

from dataclasses import dataclass

UPPER_LEFT_BAR_CODE_X = 20 #get close, not exact
UPPER_LEFT_BAR_CODE_Y = 120
UPPER_LEFT_BAR_CODE_WIDTH = 300
UPPER_LEFT_BAR_CODE_HEIGHT = 800

LOWER_LEFT_BAR_CODE_X = 20
LOWER_LEFT_BAR_CODE_Y = 3400
LOWER_LEFT_BAR_CODE_WIDTH = 300
LOWER_LEFT_BAR_CODE_HEIGHT = 750

#what we'll except as legit choice box from counter extraction
MIN_CHOICE_AREA = 4000
MAX_CHOICE_AREA = 5900

#what we'll except as legit choice box from counter extraction
MIN_CHOICE_BOX_WIDTH = 85
MAX_CHOICE_BOX_WIDTH = 110

#what we'll except as legit choice box from counter extraction
MIN_CHOICE_BOX_HEIGHT = 50
MAX_CHOICE_BOX_HEIGHT = 65

MIN_CHOICE_BOX_ANGLE = 88
MAX_CHOICE_BOX_ANGLE = 92

CHOICE_BOX_COUNT_INSET = 13 #pix to inset from choice rectange when counting human's marks

#the lines are about 8-9 pixels wide
ACTUAL_CHOICE_BOX_WIDTH = 100 #what about thickness of lines??
ACTUAL_CHOICE_BOX_HEIGHT = 54
INNER_CHOICE_BOX_WIDTH = 80
INNER_CHOICE_BOX_HEIGHT = 34

COL_SPLIT_X_VALUE = 1000

X_OFFSET_FOR_NAME = 8
Y_OFFSET_FOR_NAME = 10
WIDTH_NAME = 600
HEIGHT_NAME =80

LOW_THRESHOLD  = 1.0  #must have >= this much non-blank to be considered as a possible mark
HIGH_THRESHOLD = 3.0  #must have >= this to actually count as a vote

@dataclass
class ChoiceBox:  #v1.5 changes
    cnum: int = -1
    area: float = 0.0
    w: int = 0
    h: int = 0
    cX: int = -1
    cY: int = -1
    angle: float = 180.
    parent: int = -1
    column: int = -1
    contest_num: int = -1
    candidate_name: str = ""
    contest_name: str = ""
    votes_allowed: int = -1
    error_score: float = 0
    contest_type = "" #should be either "regular" or "proposition"


#added for V1.5
#goal is to drop references to the old global constants and use these instead
#these can be optimized for special cases 

@dataclass
class CB_select_constraints:
    # a set of default contraints that I can access by name
    min_cb_area: int = 5000 #big enough to exclude inner contour?
    max_cb_area: int = 6500
    min_cb_width: int = 85
    max_cb_width: int = 110
    min_cb_height: int = 50
    max_cb_height: int = 65
    min_cb_angle: float = 88.0
    max_cb_angle: float = 92.0
    inner_cb_width: int = 80
    inner_cb_height: int = 34
    cb_line_width: int = 10