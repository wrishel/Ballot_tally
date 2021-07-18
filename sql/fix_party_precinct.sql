

select count(*) from Images i join Barcode_info b
on barcode_upper = barcode
where i.party <> b.party_id or i.precinct <> b.precinct_id;

update Images i join Barcode_info b
on barcode_upper = barcode
set i.precinct = b.precinct_id, i.party = b.party_id
where i.party <> b.party_id or i.precinct <> b.precinct_id;
