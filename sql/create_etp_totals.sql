

drop table if exists HETP_totals ;
create table HETP_totals as
    select precinct, convert(count(image_number)/2, unsigned ) as count
        from Images
        where precinct not in ("MISSNG", "UNKNOWN", "UNREC")
        group by precinct;

drop table if exists ETPvElections_precinct_compare;
create table ETPvElections_precinct_compare as
    select elec.precinct as elec_pct, etp.precinct as etp_pct,
           elec.count as elec_count, etp.count as etp_count
        from Elections_counts elec
    left outer join HETP_totals etp using (precinct)
    union
    select elec.precinct as elec_pct, etp.precinct as etp_pct,
           elec.count as elec_count, etp.count as etp_count
        from Elections_counts elec
    right outer join HETP_totals etp using (precinct);