"""Import data from a specific Verity report that might be called
   something like "Detailed vote totals"."""

import csv
from pathlib import Path
import pandas as pd

import dbase
import GLB_globs
import io


GLB = GLB_globs.GLB_globs()
db = dbase.ETPdb()
db.connect('testing')

import_fn = 'Detailed vote totals-12-2-2020 11-07-38 AM (1).CSV'
import_path = Path(__file__).parent / import_fn
with open(import_path, 'r') as inf:
    text = inf.read()

# hack for precincts like "1E-26" showing up as "1.00E-26"
text = text.replace('.00E', 'E')
elec_df = pd.read_csv(io.StringIO(text))
db.add_all_elec_results(elec_df)
