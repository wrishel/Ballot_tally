"""Clear all the data about recorded votes from the database."""

import dbase


r = input('Are you sure you want to delete all votes?').lower()
if r[0] == 'y':
    db = dbase.ETPdb()
    db.connect('testing')
    db.clear_recorded_votes()
    print('Votes cleared.')
else:
    print('No database changes made')
