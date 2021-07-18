"""Compare old and new results after change in counting software"""

import csv
import dbase
import GLB_globs
GLB = GLB_globs.GLB_globs()


"""comparison_db_210628 is the table that mirrors the TSV output with 
   the new software/
   
   old_comparison_db is from the prior software"""



db = dbase.ETPdb()
db.connect('testing')

sql = """select 'New' which,
       if (left(Choice, 3) = 'R/M', 'ZZ', Choice) sort_choice,
       comparison_db_210628.* from comparison_db_210628
    union select 'Old',
       if (left(Choice, 3) = 'R/M', 'ZZ', Choice) sort_choice,
       old_comparison_db.* from old_comparison_db
        order by  Precinct, Contest, sort_choice, which"""

cols = ["Precinct",
        "Contest",
        "Choice",
        "Notes",
        "Our_Low",
        "Our_High",
        "Out_of_Range",
        "Our_Number_of_Images",
        "Our_Unresolved_Write_In",
        "Our_Overvotes",
        "Our_Undervotes",
        "Our_Tentative"]

rows = db.retrieve_named_tuples(sql)
new_row = None
ncols = len(cols) + 1

with open(GLB.path_to_rpts_out_dir / 'old_v_new.tsv', 'w', newline='') as csvfile:
    spamwriter = csv.writer(csvfile, dialect=csv.excel,
                            delimiter='\t')
    spamwriter.writerow([''] + cols)

    for row in rows:
        if new_row is None:
            assert row.which == 'New'
            new_row = row
        else:
            assert row.which == 'Old'
            show = False
            new_row_out = ['new']
            old_row_out = ['old']
            for col in cols:
                newitem = getattr(new_row, col)
                olditem = getattr(row, col)
                new_row_out.append(newitem)
                if olditem != newitem:
                    old_row_out.append(olditem)
                    show = True
                else:
                    old_row_out.append('')

            if show:
                spamwriter.writerow(new_row_out)
                spamwriter.writerow(old_row_out)
                diffs = ['diff']
                for i in range(1, ncols):
                    diff = ''
                    try:
                        diff = new_row_out[i] - old_row_out[i]
                        if diff == 0: diff = ''
                    except:
                        diff = ''

                    diffs.append(diff)

                spamwriter.writerow(diffs)
                spamwriter.writerow([''] * len(cols))


            new_row = None
