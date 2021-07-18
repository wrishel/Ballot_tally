/*  Correct the Images table after updating Barcode_info  */


update Images img, Barcode_info bc
set img.party = bc.party_id, img.precinct = bc.precinct_id
where barcode = barcode_upper and
      (img.party != bc.party_id OR img.precinct != bc.precinct_id)