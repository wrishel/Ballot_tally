#a simple tabulator to verify that a batch of extracted form records match expectations

import json
import pandas as pd

#utility used in add_totals_to_dataframe routine
def custom_sum(row):
    return int(row.sum())

class Tabulator():
    def __init__(self):

        self.data_accumulators = {} #dictionary of contest->pandas_df

    def add_form_result(self, form_result):
        #form_result should be the top-level dictionary corresponding to the JSON format
        #

        if form_result['processing_success'] == False:
            return #don't process failed forms

        precinct = form_result['precinct']
        page = form_result['page']

        contests = form_result['contests']

        for contest in contests:

            contest_name = contest['contest_name']

            #do we need a new dataframe for this contest? If so, allocate one (or add ref data to RDBMS)
            contest_df = self.data_accumulators.get(contest_name)
            if contest_df is None:
                #register all the data for this contest with the dataframe
                contest_df = pd.DataFrame()
                self.data_accumulators[contest_name] = contest_df
                     
                if 'over count' not in contest_df.columns:
                    x = len(contest_df.columns)
                    contest_df.insert(loc=x, column='over vote', value=0) 
                
                if 'under count' not in contest_df.columns:
                    x = len(contest_df.columns)
                    contest_df.insert(loc=x, column='under vote', value=0)

                #then add all candidates to this new df for this new contest
                for choice in contest['choices']:
                    candidate = choice['choice_name']
                    if candidate not in contest_df.columns:
                        contest_df.insert(0, column=candidate, value=0)
            
            #make sure this precinct is in the df as a row
            if precinct not in contest_df.index:
                contest_df.loc[precinct] = 0

            #OK, now the dataframe is ready, so add the scores
            #we'll confirm the over/under using duplicate logic to be a sanity check with the JSON data

            votes_allowed = contest['votes_allowed']

            choices = contest['choices']
            above_thresh = 0
            for choice in choices:
                #candidate = choice['choice_name']
                score = choice['score']
                #lower_thresh = choice["lower_threshold"]
                upper_thresh = choice["upper_threshold"]
                if (score >= upper_thresh):
                    above_thresh += 1
                #marked = choice['marked']

            if above_thresh > 0 and above_thresh <= votes_allowed:
                #sanity check against reported content status
                if contest["validcount"] != True:
                    print("ERROR - VALID VOTE contest scored differently! form: {} contest:{}".format(
                        form_result["image_number"], contest_name ))
                    return None
                #we have a valid contest, so add the candidate to the dataframe
                for choice in choices:
                    candidate = choice['choice_name']
                    score = choice['score']
                    upper_thresh = choice["upper_threshold"]
                    if score >= upper_thresh:
                        #add a vote
                        contest_df.at[precinct, candidate] += 1
                        #sanity check
                        if choice['marked'] != True:
                            print(f"{form_result['image_number']} - {candidate} - Error - score>=thresh but MARKED is not set!")
                    elif choice['marked'] != False:
                            print(f"{form_result['image_number']} - {candidate} - Error - score<thresh but MARKED IS set!")

            if above_thresh < votes_allowed:
                #under vote
                #sanity check against reported status
                if contest["undervoted"] != (votes_allowed - above_thresh):
                    print("ERROR - UNDER VOTE contest scored differently! form: {} contest:{}".format(
                        form_result["image_number"], contest_name ))
                    #return None

                contest_df.at[precinct, 'under vote'] += int(contest["undervoted"])
            
            if above_thresh > votes_allowed:
                #over vote, no candidates get votes
                #sanity check against reported status
                if contest["overvoted"] != True:
                    print("ERROR - OVER VOTE contest scored differently! form: {} contest:{}".format(
                        form_result["image_number"], contest_name ))
                    #return None

                contest_df.at[precinct, 'over vote'] += 1
        
        return True


    def _add_totals_to_all_dataframes(self):
        #hack to add totals to rows and colums
        #use this after accumulation is done, before printing
        for (name, dframe) in self.data_accumulators.items():
            dtypes_before = dframe.dtypes
            #Total sum per column: 
            dframe.loc['TOTAL'] = dframe.apply(custom_sum, axis=0)
            #Total sum per row: 
            dframe.loc[:,'Total'] = dframe.sum(axis=1)
 

    def print_contests(self):
        #just cycle thru contests and print, without sums or anything
        
        #self._add_totals_to_all_dataframes()

        for contest_name, contest_df in self.data_accumulators.items():
            print("Contest: {}".format(contest_name))
            print(contest_df)
            print("---------------------------------------------------------------")

    def save_to_csv(self, path_to_directory):
        
        self._add_totals_to_all_dataframes()
        #save each contest as separate CSV, in the Path(path_to_directory)
        for contest_name, contest_df in self.data_accumulators.items():
            outfile = path_to_directory / (contest_name + ".csv")
            contest_df.to_csv(str(outfile))






