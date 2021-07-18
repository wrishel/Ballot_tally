#added for V1.5
#mod to note that contests can change across precinct! NO, cannot change, but don't reflect what's on
#  the actual ballots. Metadata can include post-voting write-in resolutions
#lots of these methods are never used, sadly.

import csv
from pathlib import Path
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import cv2

import logging

class Metadata():
    def __init__(self, path_to_metadata_dir):
        self.path_to_metadata_dir = path_to_metadata_dir
        self.precinct_contest_choice_file = None
        self.proposition_text_file = None
        self.precincts = {}  #precinct -> [contest1, contest2...] (pure contest name)
        self.contests = {}   #contest  -> [candidate1, candidate2, ...] (key is precinct|contest)
        self.candidates = {} #candidate -> [contest, contest2, ...] -- hopefully only one contest per candidate?
        self.first_candidates = {} #also -> [contest], but just the first candidate if there is an 'and' in the name
        self.first_candidate_to_full_candidate = {} #first_candidate name points to full name, so templates can use full name
        self.proposition_to_text = {}  #contains both propositions and measures
        self.barcode_to_precinct = {} #maps each Upper Left barcode to a precinct name (string)
        self.checkerboard_match_template_image = None
    
    def load_all_metadata(self):
        #load all required metadata
        #load the election metadata (precinct->contests->candidates, etc)
        pcc_filepath = self.path_to_metadata_dir / Path("pct_contest_choice.tsv")
        ptt_filepath = self.path_to_metadata_dir / Path("proposition_to_text.tsv")
        mtt_filepath = self.path_to_metadata_dir / Path("measure_to_text.tsv")
        btp_filepath = self.path_to_metadata_dir / Path("full_barcode_to_precinct_map.csv")
        ckr_filepath = self.path_to_metadata_dir / Path("one_checkered_choicebox.jpg")
    
        self.load_precinct_contest_choice_data(pcc_filepath)
        self.load_proposition_text(ptt_filepath, mtt_filepath)
        self.load_barcode_to_precinct_dictionary(btp_filepath)
        self.load_template_match_images(ckr_filepath)
    
    def load_template_match_images(self, checkerboard_path):
        self.checkerboard_match_template_image = cv2.imread(str(checkerboard_path))

    def load_precinct_contest_choice_data(self, pcc_filename_path):
        with open(pcc_filename_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            for row in reader:
                #rows are rownum, precinct, contest, choice (choice is same as candidate)
                _, precinct, contest, choice = row
                #print(precinct, contest, choice)
                #some contests have extra spaces between words - make them all one space
                contest = ' '.join(contest.split())
                self._update_dictionaries(precinct, contest, choice)
        #now test that no candidate is in more than one contest
        for key, contests in self.candidates.items():
            if len(contests) > 1:
                #this is normal for Yes/No and write-in "candidates"
                logging.debug(f"INFO - candidate: '{key}' is in more than one contest!")
            elif len(contests) == 0:
                logging.debug(f"WARNING - candidate: {key} is not in ANY contest!")
            else:
                continue
        logging.info(f"Metadata - loaded precinct-contest-choice from {pcc_filename_path}")

    def load_proposition_text(self, prop_text_path, measure_text_path):
        #load both props and measures into same dictionary - lets see if that works
        for file_path in (prop_text_path, measure_text_path):
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile, delimiter='\t')
                for row in reader:
                    #rows are propositionname, text
                    proposition_name, proposition_text = row
                    #print(precinct, contest, choice)
                    #some texts have extra spaces between words - make them all one space
                    proposition_text = proposition_text.strip()
                    text = ' '.join(proposition_text.split())
                    #add the prop's name to the searchable text
                    text = proposition_name + " " + text
                    self.proposition_to_text[proposition_name] = text
        logging.info(f"Metadata - loaded proposition and measure text from {prop_text_path} and {measure_text_path}")

    def load_barcode_to_precinct_dictionary(self, barcode_to_precinct_path):
        #map barcodes to precinct - many to one due to provisional vs mail-in vs regular ballots
        #done one time, at startup
        #precincts_to_barcode_path = self.path_to_metadata_dir / "full_barcode_to_precinct_map.csv"
           
        with open(barcode_to_precinct_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                self.barcode_to_precinct[row['barcode']] = row['precinct']
        return

    def _update_dictionaries(self, precinct, contest, candidate):
        #add precinct to its dictionary if new
        precinct_contest_set = self.precincts.setdefault(precinct, set())
        #and add contest to this precinct's contest set
        precinct_contest_set.add(contest) #pure contest name
        
        contest_candidate_set = self.contests.setdefault(contest, set())
        #and add candidate to contest_candidate_set
        contest_candidate_set.add(candidate)
        
        #add candidate to its dictionary
        candidate_contest_set = self.candidates.setdefault(candidate, set())
        #and add contest to candidate's set(s)
        candidate_contest_set.add(contest)
        
        #and add candidate and contest to a special first-candidate-only set
        first_name = candidate.split("and")[0].strip()
        if first_name not in ("Yes", "No", "Bonds Yes", "Bonds No", "Rejected write-ins", "Unassigned write-ins" ):
            first_candidate_contest_set = self.first_candidates.setdefault(first_name, set())
            first_candidate_contest_set.add(contest)
            self.first_candidate_to_full_candidate[first_name] = candidate

    def precinct_is_valid(self, p):
        #case sensitive for now?
        return p in self.precincts
    
    def contest_is_valid(self, c):
        return c in self.contests
    
    def candidate_is_valid(self, can):
        #this requires full string to match - including both candidates!
        return can in self.candidates
    
    def candidate_is_valid_up_to_and(self, can):
        #hack to match first candidate in multi-candidate contests (eg match "JOE" in "JOE and KAMELA")
        #if there is no "and", then match the whole string exactly
        #returns the actual full name (including the 'and' candidates)
        if len(can) <= 0:
            return ""    #find returns zero on search for null string!!
        for candidate in self.candidates.keys():
            and_begins = candidate.find("and")
            if and_begins == -1:
                #no 'and' thus match it all
                if can == candidate:
                    return candidate
            else:
                #match len up to the and
                if candidate[ 0:and_begins-1 ] == can:
                    return candidate
        return ""
    
    def contest_is_in_precinct(self, con, pre):
        if self.precinct_is_valid(pre) and self.contest_is_valid(con):
            return con in self.precincts.get(pre)
        else:
            return False

    def get_contests_in_precinct(self, pre):
        if self.precinct_is_valid(pre):
            return self.precincts.get(pre)
        
    #this won't be useful, since some candidates are not on the form!    
    def get_candidates_for_contest(self, contest):
        #assumes contests are unique even across precincts??
        return self.contests.get(contest)

    def candidate_is_in_contest(self, candidate, contest):
        if self.contest_is_valid(contest):
            if candidate in self.contests[contest]:
                return True
        return False

    def get_candidates_in_precinct(self, pre):
        #note the list will have duplicates for Yes, No, etc
        if self.precinct_is_valid(pre):
            return [cand for cand in self.contests[contest] for contest in self.precincts[pre]]
        return None
    
    def candidates_belong_in_this_contest(self, list_of_candidates, contest):
        #return true if all these candidates belong in this contest
        #returns true if the list is empty and also if the list is a proper subset
        if self.contest_is_valid(contest):
            set_cand = set(list_of_candidates)
            return set_cand.issubset(self.contests[contest])
        return False

    def contests_belong_in_this_precinct(self, list_of_contests, precinct):
        #return true if all these candidates belong in this contest
        #returns true if the list is empty and if the list is a proper subset
        if self.precinct_is_valid(precinct):
            set_con = set(list_of_contests)
            return set_con.issubset(self.precincts[precinct])
        return False
    
    #This is BROKEN - do not use. Lots of mistakes. Replaced.
    def get_contests_for_candidate(self, candidate):
        #return list((candidate,contest,score) for candidates that match for this candidate name
        # allow match on beginning of name - since we don't get second candidate sometimes
        #if more than one contest matches, return all (c,c,s) in the list
        #if match is perfect use score 100
        #if no contest matches, try fuzzy match and return (candidate,contest) for top two fuzzy candidates
        results = []
        full_candidate_name = self.candidate_is_valid_up_to_and(candidate)
        if len(full_candidate_name) > 0:
            #candidate has direct match for first part of name (first candidate, before the and)
            results = [(full_candidate_name, contest, 100) for contest in self.candidates[full_candidate_name] ]
            return results
        else:
            #try fuzzy match - will be slow - take top two candidates?
            all_cans = list(self.candidates)
            winners = process.extract(candidate, all_cans, limit=2)
            for winner, score in winners:
                results.extend( [(winner,contest,score) for contest in self.candidates[winner]]  )
            return results
        return []

    def fuzzy_match_first_candidate(self, first_cand):
        results = []
        all_first_cans = list(self.first_candidates) #fix me cache in class?
        winners = process.extract(first_cand, all_first_cans, limit=2)
        for winner, score in winners:
            #process.extract only finds the best fit, which can score too high for absolute match
            #so convert the score into a fuzz.ratio test - much more specific for near exact match
            ratio_score = fuzz.ratio(first_cand, winner)
            full_name = self.first_candidate_to_full_candidate.get(winner)
            #return (first_name, full_name, contest, score)
            results.extend( [(winner, full_name, contest, ratio_score) for contest in self.first_candidates[winner]]  )
        return results

    def is_writein_allowed(self, contest):
        #does this contest accept writeins?
        #uses presence of "Unassigned write-ins" as flag
        if self.contest_is_valid(contest):
            if "Unassigned write-ins" in self.contests[contest]:
                return True
        return False

    def fuzzy_match_measure_name(self, partial_name):
        #returns full name for best match measure
        # NOTE this ought to be supplemented with measure text, otherwise it's VERY fragile
        #fixme

        measures = [mn for mn in self.contests if mn.find("Measure") == 0]
        winners = process.extract(partial_name, measures, limit=1)
        return winners[0][0] #return best match contest name, regardless of the score

    def get_best_proposition_or_measure_from_text(self, text):
        #find the best matching Proposition or Measure from OCR'd text
        #returns contest name as per the precinct-contest-candidate metadata
        best_score_1 = 0
        best_prop_1 = ""
        best_score_2 = 0
        best_prop_2 = ""
        for key, value in self.proposition_to_text.items():
            score_1 = fuzz.partial_ratio(text, value)
            score_2 = fuzz.token_set_ratio(text, value)
            if score_1 > best_score_1:
                best_score_1 = score_1
                best_prop_1 = key
            if score_2 > best_score_2:
                best_score_2 = score_2
                best_prop_2 = key
        #quick experiments suggest that score_2 is best
        return best_prop_1, best_score_2, best_prop_2, best_score_2

    def convert_barcode_to_precinct(self, barcode):
        return self.barcode_to_precinct.get(barcode)
