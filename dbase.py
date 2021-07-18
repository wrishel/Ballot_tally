"""Interface to MySQL database.

"""

from collections.abc import Iterable
import os
# import sys
# from pathlib import Path
# sys.path.append(fr'{os.path.dirname(__file__)}/util')

from collections.abc import Iterable
import csv
import random
import sys
import mysql.connector as connector
import logging
import re
import time
from timer import timer

from comparison_rpt import ElectionRpt
import GLB_globs
GLB = GLB_globs.GLB_globs()

RETRY_MAX = 5

class DBerror(IOError):
    """Error raised by the dbase module."""
    ...

class TransactionError(DBerror):
    def __init__(self, message):
        self.message = message

def flatten_sql(s):
    return re.sub(r'\s+', ' ', s)



# passwords are buried here rather than being in the .ini file --
# somewhat pointless, I know

dbconfig = {
    "user": "etp",
    "password": "Hetp2020",
    "database": "HETP"
}
test_dbconfig = {
    "user": "tevs",
    "password": "tevs",
    "database": "HETPtesting"
}

# todo: polishing: should be an enum for testing or production rather then sloppy strings

class ETPdb():
    """Interface to MySQL database.

       As a general rule, rows are returned as namedtuples."""

    def __init__(self):
        ...

    def connect(self, db_choice, autocommit=True):
        """Create connection.

           db_choice says whether to use the test or production database."""

        if db_choice == 'testing':
            db_credentials = test_dbconfig
        elif db_choice == 'production':
            db_credentials = dbconfig
        else:
            assert False, f'unknown database choice: "{db_choice}"'

        self.cnx = connector.connect(**db_credentials)
        autoc = 'ON' if autocommit else 'OFF'
        sql = f'SET AUTOCOMMIT = {autoc}'
        self.exe(sql)
        logging.info(f'db: {db_choice}; {flatten_sql(sql)}')
        self.in_transaction = False


    # -------------------------------  Server interactions  -------------------------------

    def exe(self, sql, indata=None, multi=False):
        """Execute sql with no return values.."""

        logging.debug(flatten_sql(sql))
        if indata:
            logging.debug(indata)
        cursor = self.cnx.cursor(named_tuple=True)
        if indata:
            ret = cursor.execute(sql, indata, multi)
        else:
            ret = cursor.execute(sql)
        cursor.close()
        return ret

    def exe_many(self, sql, indata):
        """Execute sql indata and commit."""

        logging.debug(flatten_sql(sql))
        logging.debug(indata)
        cursor = self.cnx.cursor(named_tuple=True)
        ret = cursor.executemany(sql, indata)
        cursor.close()
        return ret

    def tx_commit(self):
        """commit the current connection if really is true"""

        logging.debug('COMMIT')
        if self.in_transaction:
            self.cnx.commit()
            self.in_transaction = False

        else:
            raise TransactionError("Commit not in transaction.")

    def tx_rollback(self):
        """Roll back the current connection if really is true"""

        logging.debug('ROLLBACK')
        if self.in_transaction:
            self.cnx.rollback()
            self.in_transaction = False

        else:
            raise TransactionError("Rollback not in transaction.")

    def tx_start(self):

        logging.debug('START TX')
        if self.in_transaction:
            raise TransactionError("start transaction within transaction")
        self.exe('START TRANSACTION')
        self.in_transaction = True

    def retrieve(self, sql):
        """Execute sql and return list of dicts."""

        logging.debug(flatten_sql(sql))
        cursor = self.cnx.cursor()
        try:
            cursor.execute(sql)
        except Exception as e:
            print(f'exception in retireve{e}, sql={sql}')
            raise e
        res = cursor.fetchall()
        cursor.close()
        return res

    def retrieve_named_tuples(self, sql:str):  # Todo: convert retrieve and eliminate this
        return self.retrieve_many(sql)

    def retrieve_many(self, sql, params=None, style='tuple')->list:
        """Execute sql to retrieve many rows. Style indicates
           the type of objects in which to return the rows."""

        logging.debug(flatten_sql(sql))
        if style == 'tuple':
            cursor = self.cnx.cursor(named_tuple=True)
        elif style =='dict':
            cursor = self.cnx.cursor(dictionary=True)
        else:
            assert False,  f"'{style}' not a recognized cursor type"

        try:
            cursor.execute(sql, params=params)
        except Exception as e:
            print(f'exception in retrieve{e}, sql={sql}')
            raise e
        res = cursor.fetchall()
        cursor.close()
        return res

    def _prepare_column_map(self, column_map):
        """Unpack shorthand for tansfers between an
           object and a database row.

           Column_map is a  strings of the form
                "obj column name 1:table column name 1\n
                 dct column name 2:table column nam 2
                 ...
"""
        cm = column_map.split('\n')
        if cm[-1] == '': del cm[-1]
        obj_cols = list()
        db_cols = list()
        for line in cm:
            try:
                dct_name, dbname = line.split(':')
            except ValueError:
                dct_name = dbname = line

            obj_cols.append(dct_name.strip())
            db_cols.append(dbname.strip())

        return obj_cols, db_cols

    def _make_insert_sql_from_columnmap(self, table_name: str, cols: list):
        sql_colnames = ', '.join(cols)
        placeholders = ', '.join('%s' for x in cols)
        return f"""INSERT IGNORE INTO {table_name} ({sql_colnames}) 
                   VALUES ({placeholders})"""

    def insert_contests_for_tabulation(self, dicts:list[dict]):
        """Insert image rows from multiple dicts.

           Dicts may not have all columns needed for insert."""

        ld = dicts.copy()  # avoid creating side effect
        if type(ld) == dict:
            ld = (ld,)

        sql = """INSERT INTO img_contest(
                sub_id,
                image_number,
                contest_name,
                overvoted,
                undervoted,
                validcount,
                votes_allowed,
                underthreshold,
                tot_scores,
                overvoted_by_pct,
                undervoted_by_pct,
                suspicion_by_pct,
                found)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

        value_rows = []
        for d in ld:
            # set default values for missing columns
            value_row = []
            for c in ('sub_id',
                    'image_number',
                    'contest_name',
                    'overvoted',
                    'undervoted',
                    'validcount',
                    'votes_allowed',
                    'underthreshold',
                    'tot_scores',
                    'overvoted_by_pct',
                    'undervoted_by_pct',
                    'suspicion_by_pct',
                    'found'):
                value_row.append(d.get(c, None))  # default values
            value_rows.append(value_row)

        self.exe_many(sql, value_rows)

    def insert_choices_for_tabulation(self, dicts:list[dict]):
        """Insert image rows from multiple dicts.

           Dicts may not have all columns needed for insert."""

        ld = dicts.copy()  # avoid creating side effect
        if type(ld) == dict:
            ld = (ld,)

        sql = """INSERT INTO img_choice
                   (id,
                    image_number,
                    img_contest_subid,
                    choice_name,
                    score,
                    comment,
                    marked,
                    marked_by_pct,
                    upper_threshold,
                    location_ulcx,
                    location_ulcy,
                    location_lrcx,
                    location_lrcy,
                    lower_threshold)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""

        value_rows = []
        for d in ld:
            # set default values for missing columns
            value_row = []
            for c in (  'id',
                        'image_number',
                        'img_contest_subid',
                        'choice_name',
                        'score',
                        'comment',
                        'marked',
                        'marked_by_pct',
                        'upper_threshold',
                        'location_ulcx',
                        'location_ulcy',
                        'location_lrcx',
                        'location_lrcy',
                        'lower_threshold'):
                value_row.append(d.get(c, None))  # default values
            value_rows.append(value_row)

        self.exe_many(sql, value_rows)

    def update_images_for_tabulation(self, dicts):
        """Update selected columns image rows.

           Columns not present in the dict will receive
           a null value."""

        d = dicts.copy()  # avoid creating side effect
        assert d['image_number'] is not None
        for c in  ('undecodable_reason',
                   'date_time_tabulated',
                   'H_matrix',
                   'processing_success',
                   'flipped_form'):
            d[c] = d.get(c, None)   # default values

        # fudge to get a real Null in the database
        if d['H_matrix'] == 'null':
            d['H_matrix'] = None

        sql = '''UPDATE images
                     SET undecodable_reason=%s,
                         processing_comment=%s,
                         date_time_tabulated=%s,
                         H_matrix=%s,
                         processing_success=%s,
                         flipped_form=%s,
                         assigned_to_pid=NULL
                     WHERE image_number=%s'''
        data = (d['undecodable_reason'],
                d['processing_comment'],
                d['date_time_tabulated'],
                d['H_matrix'],
                d['processing_success'],
                d['flipped_form'],
                d['image_number'])
        self.exe(sql, data)

    def update_from_dict(self, table_name: str, keys: list[str],
                         vals:dict):
        """Create and execute an  ypdate statenent,.
           Keys must be in vals."""

        vd = (vals).copy()  # avoid side effect
        if type(keys) == str:
            keys=(keys,)

        nullfix = lambda z: repr(z) if z is not None else 'Null'
        # create pairs for the  WHERE clause
        keyvals = list()
        for key in keys:
            keyval = repr(vd.pop(key))
            keyvals.append(f'{key}={keyval}')

        where_pairs = ' AND '.join(keyvals)

        # create the assignments for SET
        assg_list = ', '.join(
            [f'{x} = {nullfix(y)}' for x, y in vd.items()])

        sql = f"""UPDATE {table_name} SET {assg_list}
                   WHERE {where_pairs}"""
        return self.exe(sql)

    def insert_from_dataframe(self, table_name, column_map, df):
        """Construct and execute sql to insert into table_name data
           from selected columns of df."""

        dfcols, dbcols = self._prepare_column_map(column_map)

        reduced_df = df[dfcols]
        reduced_df = reduced_df.where(df.notnull(), None)
        data = reduced_df.values.tolist()

        sql = self._make_insert_sql_from_columnmap(table_name, dbcols)
        return self.exe_many(sql, data)




    # -----------------------------  Application services  ----------------------------

    def add_all_elec_results(self, results_df):
        """Populate the elec_results table with the pandas dataframe results_df"""

        try:
            self.exe("TRUNCATE elec_results")
            column_map = \
                """Precinct:pct
                   Ballots Cast:ballots_cast
                   Contest Title:contest
                   Choice Name:choice
                   Total Votes:num_votes
                   Total Overvotes:num_overvotes
                   Total Undervotes:num_undervotes
                   Total Invalid Votes:num_invalids"""

            # commit comes here
            return self.insert_from_dataframe('elec_results',
                                              column_map, results_df)

        except Exception as e:
            logging.exception('Unable to add all election results')
        return

    def add_image_nums(self, elections_batch_num:str,
                       image_nums):
        """Add a new row to Images with only the image_number and elections_batch_num.

           elections_batch_num: str
           image_nums:  int, str or iterable of ints and strs"""

        if not isinstance(image_nums, Iterable):
            image_nums = (image_nums,)
        data = list()
        for item in image_nums: data.append((int(item), elections_batch_num))
        sql =  """INSERT INTO Images (image_number, elections_batch_num) VALUES (%s, %s)"""
        r = None
        try:
            r = self.exe_many(sql, data)
        except Exception as e:
            print('error exception:', e)
        return r

    def add_images(self, data:list):
        """Insert images into table.

        Call with data as a list of tuples
            (image number, precinct, page_number, elections_batch_num, ETP_batch_num"""

        sql =  """INSERT INTO Images 
               (image_number, precinct, page_number, elections_batch_num, ETP_batch_num) 
               VALUES (%s, %s, %s, %s, %s)"""
        return self.exe_many(sql, data)

    def accept_tabulation(self, image:dict,
                          contests: list[dict], choices: list[dict]):
        """Update an image row and insert contest and choices."""

        num_tries = 0
        while num_tries < RETRY_MAX:
            self.tx_start()
            try:
                self.update_images_for_tabulation(image)
                # delete before insert to maintain idempotence
                self.exe(f'''DELETE FROM img_contest
                             WHERE image_number = %s''',
                          (image['image_number'],))
                self.exe(f'''DELETE FROM img_choice
                             WHERE image_number = %s''',
                          (image['image_number'],))

                self.insert_contests_for_tabulation(contests)
                self.insert_choices_for_tabulation(choices)
                self.tx_commit()
                break   # successful execution

            except connector.errors.InternalError as e:
                # 213 (40001): Deadlock found when trying to get lock; try restarting transaction
                print(f'{os.getpid()} deadlock numtries={num_tries}',
                      file=sys.stderr)
                # logging.exception(e)
                logging.error(f'Retrying after deadlock {num_tries}; {str(e)}')
                self.tx_rollback()
                time.sleep(random.random()/4)
                num_tries += 1

            except Exception as e:
                print(repr(e))
                logging.exception(e)
                self.tx_rollback()
                raise e

    def delete_images(self, data):
        """Delete a list of images from the table.

           data: an interable of image_number"""

        if not isinstance(data, Iterable):
            data = (data,)
        d = tuple(data)
        num_list = ','.join((str(x) for x in d))
        sql =  f"""DELETE from Images WHERE image_number in ({num_list})"""
        r = None
        try:
            r = self.exe(sql)
        except Exception as e:
            r = e
            print('error exception in connector:', e, file=sys.stderr)
        return r

    def fix_orphaned_rows(self):
        """Abnormal shutdown scenarios can leave rows checked out for get_images_for_barcode(). Run
           this once when nothing else is accessing the database to reset those rows."""

        sql = f'''UPDATE Images SET assigned_to_pid = NULL
                        WHERE assigned_to_pid IS NOT NULL'''
        # sql = f'''UPDATE Images SET assigned_to_pid = NULL
        #                 WHERE assigned_to_pid IS NOT NULL AND precinct IS NULL'''

        return self.exe(sql)

    def get_barcodes(self):
        """Return the known barcode rows"""

        sql = "SELECT * FROM precinct"
        return self.retrieve_named_tuples(sql)

    def get_all_image_numbers(self):
        """Return all image numbers, not necessarily in order."""
        sql = f"SELECT image_number FROM Images"
        return self.retrieve(sql)

    def get_choices_for_remarking(self, remark_column: str,
                                  imagnums:tuple=None) -> list:
        """Return all choices that have a null in remarked_column"""

        if imagnums and not isinstance(imagnums, Iterable):
            imagnums = (imagnums,)

        if imagnums:
            imgnstr = ','.join([str(imn) for imn in imagnums])
            where_clause = f'WHERE ico.image_number IN ({imgnstr})'
        else:
            where_clause = f'WHERE {remark_column} IS NULL'

        sql = f"""SELECT 
                    max(votes_allowed)                  votes_allowed, 
                    SUM(score)                          tot_scores,
                    GROUP_CONCAT(ich.id)                choice_ids,
                    GROUP_CONCAT(score)                 scores,
                    GROUP_CONCAT(ich.choice_name)       choices,
                    MAX(ico.contest_name)               contest_name, # for debugging
                    ico.sub_id                          cont_subid, 
                    ich.image_number                    imgnum
                 FROM img_choice ich INNER JOIN img_contest ico
                    on  ich.image_number = ico.image_number
                    and ich.img_contest_subid = ico.sub_id
                {where_clause}
                GROUP BY ich.image_number, ico.sub_id
                ORDER BY ich.image_number, ico.sub_id"""

        return self.retrieve_named_tuples(sql)


    def get_images(self, iterable):
        """Return a list of image IDs"""

        t = tuple(iterable)
        sql = f"SELECT * FROM Images WHERE image_number IN {str(iterable)}"
        return self.retrieve(sql)

    def get_images_for_barcode(self, pid, num):
        """Get rows from Images that need the precinct ID.

           To enable parallel processing this finds candidate rows and locks them
           by putting the process ID in assigned_to_pid. Once this is done, parallel
           calls to this routine should skip rows."""

        # self.retrieve_named_tuples(s)         # clear the cursor
        # cursor = self.cnx.cursor(named_tuple=True)
        sql = f'''UPDATE Images SET assigned_to_pid = {pid}
                        WHERE assigned_to_pid IS NULL 
                          AND (precinct IS NULL OR page_number IS NULL)
                        LIMIT {num}'''

        self.exe(sql)
        sql = f'SELECT * FROM Images WHERE assigned_to_pid = {pid}'
        return self.retrieve_named_tuples(sql)

    def get_images_for_tabulation(self, pid:int, quantity:int,
                                  imgnum:int=None):
        """Get rows from Images that need the precinct ID.

           To enable parallel processing this finds candidate rows and locks them
           by putting the process ID in assigned_to_pid. Once this is done, parallel
           calls to this routine should skip rows.

           If imgnum is present only the row for that image number
           is returned."""

        if imgnum is not None:
            # For debugging retrieve the specified row even if
            # date_time_tablulated is not null (i.e., reprocess the image
            # if necessary).
            if type(imgnum) is int:
                imgnum = (imgnum,)
            imglist = ','.join([str(x) for x in imgnum])
            sql = f'''UPDATE Images SET assigned_to_pid = {pid}
                            WHERE image_number in ({imglist})'''

        else:
            sql = f'''UPDATE Images SET assigned_to_pid = {pid}
                            WHERE assigned_to_pid IS NULL 
                              AND date_time_tabulated IS NULL
                            LIMIT {quantity}'''
        self.exe(sql)
        sql = f'SELECT image_number, page_number, precinct FROM Images ' \
              f'WHERE assigned_to_pid = {pid}'
        return self.retrieve_many(sql)

    def get_image_nums(self):
        """Return the image numbers in Images """

        sql = """SELECT image_number FROM Images"""
        return self.retrieve_named_tuples(sql)

    def get_highest_image_num(self) -> int:

        sql = f"""select max(image_number) from Images"""
        try:
            x = self.retrieve(sql)
        except Exception as e:
            raise e
        rv =  x[0][0]
        if rv is None: rv = -1
        return rv

    def get_imgnum_pct(self):
        sql  = """SELECT image_number, precinct FROM Images
                  ORDER BY image_number, precinct"""
        return self.retrieve_named_tuples(sql)

    def get_page_report(self):
        """Get the data for the pages report."""

        sql = """drop table if exists temp_counts"""
        self.exe(sql)
        sql = """
        CREATE TABLE temp_counts AS
            select precinct,
                COUNT(if(page_number = '1', 1, NULL)) as page_1,
                COUNT(if(page_number = '2', 1, NULL)) as page_2,
                COUNT(if(page_number = '3', 1, NULL)) as page_3,
                COUNT(if(page_number = '4', 1, NULL)) as page_4,
                COUNT(if(page_number = 'UNK', 1, NULL)) as unrecognized,
                COUNT(if(page_number = 'MSG', 1, NULL)) as other_error,
                COUNT(if(page_number IS NULL, 1, NULL)) as not_processed,
                group_concat(distinct elections_batch_num) as elections_nums
            from Images
            group by precinct"""
        self.exe(sql)

        sql = """
            select precinct, page_1, page_2, page_3, page_4,
               unrecognized, other_error, not_processed,
               page_1 + page_2 + page_3 + page_4 +
               unrecognized + other_error + not_processed as total_pages,
               elections_nums
            from temp_counts
            order by precinct;"""
        return self.retrieve_named_tuples(sql)

    def recreate_images(self):
        """Drop and redefine the images table."""

        assert False
        self.exe("""DROP TABLE IF EXISTS Images""")
        self.exe("""CREATE TABLE `images` (
          `image_number` mediumint NOT NULL,
          `precinct` varchar(7) DEFAULT NULL,
          `page_number` varchar(3) DEFAULT NULL,
          `elections_batch_num` varchar(6) DEFAULT NULL,
          `ETP_batch_num` varchar(6) DEFAULT NULL,
          `assigned_to_pid` mediumint DEFAULT NULL,
          `barcode` varchar(14) DEFAULT NULL,
          `comments` varchar(254) DEFAULT NULL COMMENT 'Comments should include notations where a row was edited by hand or using an ad hoc program, such as "2020-11-24 Edited by WR to create precinct and page_number because barcodes obscured."',
          `lower_barcode` varchar(14) DEFAULT NULL,
          PRIMARY KEY (`image_number`)
)           ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
""")

    def report_ballots_by_precinct(self):
        """Retrieve data with total row at bottom."""

        sql = """SELECT precinct, count(image_number)  as "images" 
                 from images group by precinct
                 union select "  TOTAL", count(image_number) 
                 from images;"""
        return self.retrieve_named_tuples(sql)

    def report_pages_by_precinct(self):
        sql = """select precinct,
                       sum(if(page_number = 1, 1, 0))                  as "Page 1",
                       sum(if(page_number = 2, 1, 0))                  as "Page 2",
                       sum(if(page_number = 3, 1, 0))                  as "Page 3",
                       sum(if(page_number = 4, 1, 0))                  as "Page 4",
                       sum(if(page_number = 'UNK', 1, 0))              as "Unknown",
                       sum(if(page_number in (1, 2, 3, 4, 'UNK'),1,0)) as "Total"
                    from images
                    group by precinct
                union
                select "TOTAL",
                       sum(if(page_number = 1, 1, 0))                  as "Page 1",
                       sum(if(page_number = 2, 1, 0))                  as "Page 2",
                       sum(if(page_number = 3, 1, 0))                  as "Page 3",
                       sum(if(page_number = 4, 1, 0))                  as "Page 4",
                       sum(if(page_number = 'UNK', 1, 0))              as "Unknown",
                       sum(if(page_number in (1, 2, 3, 4, 'UNK'),1,0)) as "Total"
                    from images
                    order by precinct;"""

        return self.retrieve_named_tuples(sql)

    def report_comparison_newer(self):
        """Return two tsv files that compares our counts to election results.
        
           One of them will be post-processed in a spreadsheet for the report.
           The other will be imported back into the database for furhter analysis.

            Merge the official results from table elec_results with
            our results grouped by precinct/contest/choice, which
            have been put in table t_our_count."""

        sql = """SELECT * from elec_res_matchable
                 ORDER BY pct, contest, choice"""
        elec_results = self.retrieve_named_tuples(sql)

        sql = """SELECT * from t_our_count
                 ORDER BY precinct, contest_name, choice_name"""
        our_results = self.retrieve_named_tuples(sql)

        rpt = ElectionRpt()
        with open(r'rpts/comparison.tsv', 'w', newline='') as csvfile:
            spamwriter = csv.writer(csvfile, dialect=csv.excel,
                                    delimiter='\t')
            spamwriter.writerow(rpt.header_line())
            for oline in rpt.run(elec_results, our_results):
                spamwriter.writerow(oline)
                
        with open(r'rpts/comparison.tsv', 'r', newline='') as tsv_in:
            with open(r'rpts/comparison_db.tsv', 'w', newline='') as tsv_out:
                headings = tsv_in.readline().split('\t')
                new_headings = []
                for h in headings:
                    h = h.replace(' ', '_')
                    h = h.replace('.', '')
                    h = h.replace('_-_', '_less_')
                    h = h.replace('#', 'num')
                    h = h.replace('-', '')
                    new_headings.append(h)
                tsv_out.write('\t'.join(new_headings))

                # remove blanks lines. If first column is null the
                # line is blank.
                for line in tsv_in.readlines():
                    if line[0] != '\t':
                        tsv_out.write(line)

    def update_unscanned_images(self, update_data):
        """Update the images that were previousy unscanned.

           Call with tuples of (precinct, barcode, image_number)"""

        sql = "UPDATE Images SET precinct = %s, " \
                                "barcode = %s, " \
                                "assigned_to_pid = NULL, " \
                                "lower_barcode = %s, " \
                                "page_number = %s " \
              "WHERE image_number = %s"
        self.exe_many(sql, update_data)

    def clear_recorded_votes(self):
        """Prepare to start over recording votes. Does not
           reset barcode evaluation."""

        self.exe("""truncate table img_choice;""")
        self.exe("""truncate table img_contest;""")
        self.exe("""UPDATE images
            SET assigned_to_pid = NULL,
              undecodable_reason = NULL,            
              date_time_tabulated = NULL,            
              H_matrix = NULL,            
              M_matrix = NULL,            
              processing_success = NULL,            
              flipped_form = NULL,
              processing_comment = NULL
            WHERE image_number = image_number""")
        return

    def create_t_our_count(self):
        """Create summary at precinct-contest level.
        """

        tmr = timer()

        # precinct/contests with at least one suspicious ballot
        tmr.switch_to('t_suspicious')
        self.exe("""drop table if exists t_suspicious""")
        self.exe("""
        create table t_suspicious as
        select distinct concat(ico.contest_name, "|",
            ico.image_number) AS dud
        from (img_contest ico
        join images img using (image_number))
        where suspicion_by_pct != 0""")
        print(tmr)

        # save the data to compute the ratio of marked to choices for unsuspicious contests
        tmr.switch_to('t_marked_ratio')
        self.exe("""drop table if exists t_marked_ratio""")
        self.exe("""
        create table t_marked_ratio as
        select precinct, contest_name, sum(marked) marked,
               count(score) cnt_unsuspic  # count of unsuspicious ballots
        from img_con_cho
        where concat(contest_name, '|', image_number) 
                not in (select dud from t_suspicious)
        group by precinct, contest_name""")
        print(tmr)

        # our data summed to precinct/contest level
        tmr.switch_to('t_contest_level')
        self.exe("""drop table if exists t_contest_level""")
        self.exe("""create table t_contest_level as
                (select precinct, contest_name,
                sum(undervoted_by_pct) undervotes_by_pct,
                sum(suspicion_by_pct) suspicion_by_pct,
                count(DISTINCT i.image_number) num_images,
                i.page_number page_number
                 from img_contest
                 join images i on img_contest.image_number = i.image_number
                 group by precinct, contest_name)""")
        print(tmr)

        # more of our data at precinct/contest/choice level
        tmr.switch_to('t_otherstats')
        self.exe("""drop table if exists t_otherstats""")
        self.exe("""create table t_otherstats as
                (select precinct,
                contest_name,
                if (locate("Write In", choice_name) > 0,
                    "(WRITE IN)", choice_name) as choice_name,
                cast(sum(marked_by_pct) as signed) votes_by_pct,
                count(marked_by_pct) as our_ballots_counted,
                sum(overvoted_by_pct) overvotes_by_pct,
                votes_allowed
            from img_con_cho
            group by precinct, contest_name, choice_name)""")
        # print(tmr)

        # merge it all together at precinct/contest/cnoice level
        tmr.switch_to('t_our_count')
        self.exe("""drop table if exists t_our_count""")
        self.exe("""create table t_our_count as
                    (select  toth.precinct precinct,
                             toth.contest_name contest_name,
                             tcl.num_images,
                             choice_name,
                             votes_by_pct,
                             overvotes_by_pct,
                             tcl.suspicion_by_pct,
                             undervotes_by_pct,
                             votes_allowed,
                             tcl.page_number,
                             marked,
                             cnt_unsuspic
                     from t_otherstats toth
                     join t_contest_level tcl
                         on  toth.contest_name = tcl.contest_name
                         and toth.precinct = tcl.precinct
                     join t_marked_ratio tmr
                        on  tmr.precinct = tcl.precinct
                        and tmr.contest_name = tcl.contest_name
                    )
            """)
        tmr.switch_to()
        # self.exe("""drop table if exists t_contest_level""")
        # self.exe("""drop table if exists t_otherstats""")
        # self.exe("""drop table if exists t_suspicious""")
        # self.exe("""drop table if exists t_marked_ratio""")
        for x in tmr.get_times():
            print(x)
        logging.info(str(tmr))


if __name__ == '__main__':
    db = ETPdb()
    db.connect('testing')
    # db.create_t_our_count()
    db.report_comparison_newer()
    exit(0)
    assert False, "Unit testing Needs to be rewritten to use unit-test schema"
    db.clear_recorded_votes()
    # db.clear_recorded_votes()  # move this in front of the assert if you really want to do it
    from random import randint, seed
    import collections

    # Named tuple for a result of selection from Images
    #
    Exp_img_row = collections.namedtuple('Exp_img_row',
                                         'image_number precinct page_number '
                                         'elections_batch_num ETP_batch_num '
                                         'assigned_to_pid barcode')

    seed(2)         # initiallze random for repeatable test results
    db.tracing_sql = False      # omit this to see all SQL statements executed

    # test add_image_nums
    db.recreate_images()        # create a blank Images table
    db.add_image_nums(12345, (1,'2'))  # elections batch numbers + 2 image numbers
    db.add_image_nums(12346, 3)
    db.add_image_nums(12346, '4')

    sql = '''SELECT * FROM IMAGES'''
    ret = db.retrieve(sql)
    assert len(ret) == 4
    indxs = range(4)
    for i in indxs:
        assert ret[i][0] == i + 1   # image numbers as expected

    db.delete_images((2,))
    sql = '''SELECT * FROM IMAGES'''
    ret = db.retrieve(sql)
    assert len(ret) == 3            # one fewer images
    assert ret[0][0] == 1           # image 2 is missing
    assert ret[1][0] == 3
    assert ret[2][0] == 4

    db.delete_images(('1',4))
    sql = '''SELECT * FROM IMAGES'''
    ret = db.retrieve(sql)
    assert len(ret) == 1            # only image # 3 is left now
    assert ret[0][0] == 3

    # test add_images
    db.recreate_images()        # create a blank Images table
    data = []
    for x in range(15):
        data.append((
            x,
            ('2-CS', '1-CS4', 'ABCD-1','2-CS', '1-CS4', 'ABC', 'UNKNOWN')[randint(0,6)],
            (1, 2, 3, 4, 1, 2, 3, 4, 'UNK')[randint(0,8)],
            '31',
            '5'))

    for x in range(16, 19):
        data.append((x, None, None, None, None))

    db.add_images(data)     # add 16 images


    # expected result for random data with seed == 2
    #

    # verify  updating images after scanning barcode
    #
    update_list = []
    for i in (0, 14):
        row = list()
        row.append('UPD-2')         # show that the precinct was updated
        row.append('123412341234')  # barcode
        row.append(data[i][0])      # image number to be changed
        update_list.append(row)

    db.update_unscanned_images(update_list)
    x = db.get_images((0, 14, 18))  # check updates worked and null rows arrived
    expected_value = list()
    expected_value.append(Exp_img_row(0, 'UPD-2', '1', '31', '5', None, '123412341234'))
    expected_value.append(Exp_img_row(14,'UPD-2', '3', '31', '5', None, '123412341234'))
    expected_value.append(Exp_img_row(18, None, None, None, None, None, None))
    assert x == expected_value

    x = db.get_page_report()
    expected_value = [(None,      0, 0, 0, 0, 0, 0, 3, 3, None),
                      ('1-CS4',   1, 0, 1, 0, 0, 0, 0, 2, '31'),
                      ('2-CS',    0, 1, 1, 0, 1, 0, 0, 3, '31'),
                      ('ABC',     1, 0, 0, 0, 0, 0, 0, 1, '31'),
                      ('ABCD-1',  1, 0, 1, 2, 1, 0, 0, 5, '31'),
                      ('UNKNOWN', 1, 0, 0, 0, 1, 0, 0, 2, '31'),
                      ('UPD-2',   1, 0, 1, 0, 0, 0, 0, 2, '31')]

    assert x == expected_value
    db.recreate_images()    # leave database empty after testing;

