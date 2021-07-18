select precinct,
       sum(if(page_number = 1, 1, 0))                  as "Page 1",
       sum(if(page_number = 2, 1, 0))                  as "Page 2",
       sum(if(page_number = 3, 1, 0))                  as "Page 3",
       sum(if(page_number = 4, 1, 0))                  as "Page 4",
       sum(if(page_number = 'UNK', 1, 0))              as "Unknown",
       sum(if(page_number in (1, 2, 3, 4, 'UNK'),1,0)) as "Total"
    from images
    group by precinct
union
select "TOTAL",
       sum(if(page_number = 1, 1, 0))                  as "Page 1",
       sum(if(page_number = 2, 1, 0))                  as "Page 2",
       sum(if(page_number = 3, 1, 0))                  as "Page 3",
       sum(if(page_number = 4, 1, 0))                  as "Page 4",
       sum(if(page_number = 'UNK', 1, 0))              as "Unknown",
       sum(if(page_number in (1, 2, 3, 4, 'UNK'),1,0)) as "Total"
    from images
    order by precinct;