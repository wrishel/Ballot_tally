from stand_alone_image_logging import an_image_annotator
import mysql.connector
from mysql.connector import errorcode
import time
import json

class DatabaseUpdater():
    def __init__(self) -> None:
        #fake for testing
        self.contest_name_to_id = { 'PRESIDENT AND VICE PRESIDENT':1 , 'THIS IS FAKE' : 2 }
        
    def connect(self, username, password):
        try:
            self.cnx = mysql.connector.connect(user=username,password=password, database='election')
            return True
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Database does not exist")
            else:
                print(err)
            return False

    def start_transactions(self, batchsize=1):
        self.batchsize = batchsize
        self.cursor = self.cnx.cursor(prepared=False)

    def insert_or_update_one_form(self, form_json_as_dict):
        
            status = self._update_images_table(form_json_as_dict)
            if status and form_json_as_dict.get('processing_success') == True:
                status = self._update_img_contest_table(form_json_as_dict)
                if status:
                    status = self._update_img_choice_table(form_json_as_dict)
            return status

    def insert_json(self, form_json_as_dict):
            status = self._insert_as_json(form_json_as_dict)
            return status
            
    def rollback_transactions(self):
        if self.cnx:
            self.cnx.rollback()

    def finish(self):
        if self.cnx:
            self.cnx.commit()

        #self.cnx.close()
        return


    def _update_contest_table(self, contest_name):
        #see if contest_name exists, and if so, return the id (most common outcome)
        #if not, add new contest name and return the new id
        
        try:
            query = "SELECT id from election.contest WHERE contest_name = %s"
            self.cursor.execute( query, (contest_name,) )
            result = self.cursor.fetchone()

            #if here, see if we got a value
            if (result is not None):
                #print("tried query and row exists, returning ", result)
                return result[0]

        #unexpected exceptions here - NOTE that finding a query empty set is NOT an exception!
        except mysql.connector.Error as err:
            print(f"tried query - got this error = {err}")
            return None

        #fall thru to here if contest_name not present

        insert_new_contest = "INSERT into election.contest (contest_name) values (%s)"

        try:
            self.cursor.execute(insert_new_contest, (contest_name,))

            #if successful, get and return the ID of the row just inserted
            #print("tried insert and SUCCESS with lastrowid = ", self.cursor.lastrowid)
            return self.cursor.lastrowid[0]
    
        except mysql.connector.Error as err:
            print("tried insert - got this FAILED error = ", err)
        
        return None

    def _update_choice_table(self, contest_id, choice_name):
        #see if choice_name exists, and if so, return the id (most common outcome)
        #if not, add new (contest_id, choice name) and return the new choice_id
        
        try:
            query = "SELECT id from election.choice WHERE contest_id = %s and choice_text = %s"
            self.cursor.execute( query, (contest_id, choice_name,) )
            result = self.cursor.fetchone()

            #if here, see if we got a value
            if (result is not None):
                #print("tried choice name query and row exists, returning ", result)
                return result[0]

        #unexpected exceptions here - NOTE that finding a query empty set is NOT an exception!
        except mysql.connector.Error as err:
            print(f"tried choice name query - got this error = {err}")
            return None

        #fall thru to here if contest_name not present

        insert_new_choice = "INSERT into election.choice (contest_id, choice_text) values (%s, %s)"

        try:
            self.cursor.execute(insert_new_choice, (contest_id, choice_name))

            #if successful, get and return the ID of the row just inserted
            #print("tried insert and SUCCESS with lastrowid = ", self.cursor.lastrowid)
            return self.cursor.lastrowid
    
        except mysql.connector.Error as err:
            print("tried insert into Choice - got this FAILED error = ", err)
        
        return None


    def _update_images_table(self, form_json_as_dict):

        insert_or_update_images = """
            INSERT into election.images (image_number, precinct, page_number, barcode,
            comments, lower_barcode, undecodable_reason, H_matrix, M_matrix, processing_success, flipped_form) values
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) as new_image
            ON DUPLICATE KEY UPDATE 
                comments = new_image.comments,
                undecodable_reason = new_image.undecodable_reason, 
                H_matrix = new_image.H_matrix,
                M_matrix = new_image.M_matrix,
                processing_success = new_image.processing_success, 
                flipped_form = new_image.flipped_form
        """

        image_number = form_json_as_dict.get('image_number')

        if form_json_as_dict.get('processing_success') == True:
            precinct =          form_json_as_dict.get('precinct')
            page_number =       form_json_as_dict.get('page')
            barcode =           None
            comments =          form_json_as_dict.get('processing_comment')
            lower_barcode =     None
            undecodable_reason = form_json_as_dict.get('processing_comment')
            H_matrix =          json.dumps(form_json_as_dict.get('H_matrix'))
            M_matrix =          json.dumps(form_json_as_dict.get('M_matrix'))
            processing_success = True
            flipped_form =      True if (form_json_as_dict.get('flipped_form') == True) else False
        else:
            precinct = None
            page_number = None 
            barcode = None
            comments = None
            lower_barcode = None
            undecodable_reason = form_json_as_dict.get('processing_comment')
            H_matrix = None
            M_matrix = None
            processing_success = False
            flipped_form = None

        data_for_images = (image_number, precinct, page_number, barcode, comments, lower_barcode, \
                                undecodable_reason, H_matrix, M_matrix, processing_success, flipped_form )

        try:
            self.cursor.execute(insert_or_update_images, data_for_images)
            return True
        
        except mysql.connector.Error as err:
            print(err)
            return False

    
    def _update_img_contest_table(self, form_json_as_dict):

        insert_or_update_img_contest = """
            INSERT into election.img_contest (sub_id, image_number, contest_name, 
                    overvoted, undervoted, validcount, votes_allowed, underthreshold, 
                    img_contest_sub_id, img_contest_image_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) as new_img_contest
            ON DUPLICATE KEY UPDATE 
                contest_name = new_img_contest.contest_name,
                overvoted = new_img_contest.overvoted,
                undervoted = new_img_contest.undervoted, 
                validcount = new_img_contest.validcount, 
                votes_allowed = new_img_contest.votes_allowed,
                underthreshold = new_img_contest.underthreshold
        """

        # alternative = """
        #     INSERT into election.img_contest (sub_id, image_number, contest_name,
        #     overvoted, undervoted, validcount, votes_allowed, underthreshold,
        #     img_contest_sub_id, img_contest_image_number) 
        #       SELECT ( %s, %s, id, %s, %s, %s, %s, %s, %s, %s ) from election.contest 
        #        where election.contest.contest_name = %s
        # """

        image_number = form_json_as_dict.get('image_number')

        #if form_json_as_dict.get('processing_success') != True:
        #    print(f"Form: {image_number} did not have processing_data")
        #    return False  #fix me!

        data_for_img_contest = []
        #alternative_data_for_img_contest = []

        #decode contests out of json
        for i, contest in enumerate(form_json_as_dict['contests']):
            contest_name = contest['contest_name']
            overvoted = contest['overvoted']
            undervoted = contest['undervoted']
            validcount = contest['validcount']
            votes_allowed = contest['votes_allowed']
            underthreshold = contest['underthreshold']

            #fetch the contest_name ID from contest table
            contest_id = self._update_contest_table(contest_name)
            #contest_id = self.contest_name_to_id.get(contest_name)

            data_for_img_contest.append( (i, image_number, contest_id, #contest_name
                overvoted, undervoted, validcount, votes_allowed, underthreshold, i, image_number) )

            # alternative_data_for_img_contest.append( (i, image_number, 
            #     overvoted, undervoted, validcount, votes_allowed, underthreshold, i, image_number, contest_name) )

        try:
            self.cursor.executemany(insert_or_update_img_contest, data_for_img_contest)
            #self.cursor.executemany(alternative, alternative_data_for_img_contest)
            return True
        
        except mysql.connector.Error as err:
            print(err)
            return False
        
        return True

    def _update_img_choice_table(self, form_json_as_dict):

        insert_or_update_img_choice = """
            INSERT into election.img_choice (image_number, img_contest_subid, choice_name, score,
                marked, upper_threshold, lower_threshold, location_ulcx, location_ulcy, location_lrcx, location_lrcy)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) as new_img_choice
            ON DUPLICATE KEY UPDATE 
                score = new_img_choice.score,
                marked = new_img_choice.marked,
                upper_threshold = new_img_choice.upper_threshold,
                lower_threshold = new_img_choice.lower_threshold,
                location_ulcx = new_img_choice.location_ulcx,
                location_ulcy = new_img_choice.location_ulcy,
                location_lrcx = new_img_choice.location_lrcx,
                location_lrcy = new_img_choice.location_lrcy
        """
        image_number = form_json_as_dict.get('image_number')

        if form_json_as_dict.get('processing_success') != True:
            #print(f"Form: {image_number} did not have processing_data")
            return False  #fix me!

        data_for_img_choice = []

        #decode contests and choices out of json
        for i, contest in enumerate(form_json_as_dict['contests']):
            
            contest_name = contest['contest_name']
            contest_id = self._update_contest_table(contest_name)
            
            for choice in contest['choices']:
                choice_name = choice['choice_name']

                #convert choice_name into choice table ID (fetch or add and fetch)
                choice_name_id  = self._update_choice_table(contest_id, choice_name)

                score = choice['score']
                marked = choice['marked']
                upper_threshold = choice['upper_threshold']
                lower_threshold = choice['lower_threshold']
                location_ulcx = choice['location_ulcx']
                location_ulcy = choice['location_ulcy']
                location_lrcx = choice['location_lrcx']
                location_lrcy = choice['location_lrcy']

                data_for_img_choice.append( (image_number, i, choice_name, score,
                marked, upper_threshold, lower_threshold, location_ulcx, location_ulcy, location_lrcx, location_lrcy) )

        try:
            self.cursor.executemany(insert_or_update_img_choice, data_for_img_choice)
            return True
        
        except mysql.connector.Error as err:
            print(err)
            return False
        
        return True

    def _insert_as_json(self, form_json_as_dict):
        #lets play with JSON datatypes!

        insert_json_result  = """
            INSERT into election.results (image_number, form)
            VALUES (%s, %s)
        """

        image_number = form_json_as_dict.get('image_number')

        if form_json_as_dict.get('processing_success') != True:
            print(f"Form: {image_number} did not have processing_dat - SKIPPING JSON insert")
            return True  #fix me!

        data_for_json = (image_number, json.dumps(form_json_as_dict))

        try:
            self.cursor.execute(insert_json_result, data_for_json)
            return True
        
        except mysql.connector.Error as err:
            print(err)
            return False
        