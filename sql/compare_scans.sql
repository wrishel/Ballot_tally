/* Generate a report comparing data from the elections spreadsheet
   of batches scanned to the contents of Images.

   Wes Rishel
 */
 
drop table if exists t_ETP_totals ;
create table t_ETP_totals as
    select precinct,
           convert(count(image_number)/2, unsigned ) as count
        from Images
        /* where precinct not in ("MISSNG", "UNKNOWN", "UNREC") */
        group by precinct;

drop table if exists t_scanning_compare;
create table t_scanning_compare as
    select elec.precinct as elec_pct,
           elec.count as elec_count,
           etp.precinct as etp_pct,
           etp.count as etp_count
        from Elections_counts elec
    left outer join t_ETP_totals etp using (precinct)
    union
    select elec.precinct as elec_pct,
           elec.count as elec_count,
           etp.precinct as etp_pct,
           etp.count as etp_count
        from Elections_counts elec
    right outer join t_ETP_totals etp using (precinct)
    order by elec_pct;


drop table if exists t_output;
create table t_output as
    select
        if(elec_pct is null, etp_pct, elec_pct) as "Precinct",
        if(elec_count is null, 0, elec_count) as "Election Count",
        if(etp_count is null, 0, etp_count) as "ETP Count"
        from t_scanning_compare
    union
    select "TOTALS", sum(elec_count), sum(etp_count)
        from t_scanning_compare
    order by Precinct;