

"""Reprocess the barcodes for  selected file numbers"""

from ETP_util import fullpath_to_image, subpath_to_image
from HARTgetBallotType import HARTgetBallotType, b2str
import GLB_globs
import etpconfig
import dbase
import sys
GLB = GLB_globs.get()

GLB.db.connect('testing')

barcode_data = GLB.db.get_barcodes()
barcodes = list(x.barcode for x in barcode_data)

def find_barc_row(barcode):
    for row in barcode_data:
        if row.barcode == barcode: return row
    return None

# with open('test_data/t_barcodes.txt') as inf:
#     barcodes = set((x.strip() for x in inf))

batches = [
    (0,9479),
]
processed = set()
with open('/Users/Wes/Downloads/reprocessnums.txt', 'w') as reprnums:
    with HARTgetBallotType(barcode_data, 300) as hgbt:
        for first, last in batches:
            for n in  range(first, last + 1):
                reprnums.write(f'{n}\n')
                pth = fullpath_to_image(n)
                try:
                    barcode = b2str(hgbt.getBallotType(pth))
                except Exception as e:
                    print(n, e, file=sys.stderr)
                else:
                    if barcode not in barcodes:
                        barcodes.append(barcode)
                        print(f'adding: {n}\t{barcode}')
                    else:
                        if barcode not in processed:
                            processed.add(barcode)
                            row = find_barc_row(barcode)
                            if row:
                                print(f'{n}\t{barcode}\t{row.precinct_id}\t{row.party_id}')
                            else:
                                print(f'{n}\t{barcode}\t(no matching row)')

                # if n % 100 == 0: print(f'\t\t\t{n}')

