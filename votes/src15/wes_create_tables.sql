rollback;

commit;

create table choice
(
id int auto_increment
primary key,
contest_id int null,
choice_text varchar(100) null
)
comment 'All valid choices for a contest.
';

create index fk_choice_contest_idx
on choice (contest_id);

create table contest
(
contest_name varchar(255) null,
id int not null
primary key
)
comment 'All contests for an election.';

create table elec_results
(
id int auto_increment
primary key,
pct varchar(7) null,
contest varchar(255) null,
choice varchar(255) null,
ballots_cast int null comment 'votes+ove rvotes+under votes+invalid votes',
num_overvotes int null,
num_undervotes int null,
num_invalids int null comment 'Usually unresolved writeins',
num_votes int null
)
comment 'The aggregate count for a choice in a contest in a precinct. (Denormalized)';

create table election
(
elec_id varchar(12) not null,
title varchar(255) not null,
date date null,
DPI int null,
primary key (elec_id, title)
);

create table images
(
image_number mediumint not null
primary key,
precinct varchar(7) null,
page_number varchar(3) null,
elections_batch_num varchar(6) null,
ETP_batch_num varchar(6) null,
assigned_to_pid mediumint null,
barcode varchar(14) null,
comments varchar(254) null comment 'Comments should include notations where a row was edited by hand or using an ad hoc program, such as "2020-11-24 Edited by WR to create precinct and page_number because barcodes obscured."',
lower_barcode varchar(14) null,
undecodable_reason varchar(255) null,
date_time_tabulated datetime null,
H_matrix json null,
processing_success int null,
flipped_form tinyint(1) null,
M_matrix json null,
processing_comment varchar(255) null
);

create index fk_images_precinct_id_idx
on images (precinct);

create table img_choice
(
id int auto_increment
primary key,
image_number mediumint null,
img_contest_subid int null,
choice_name varchar(100) null,
score float null,
comment varchar(255) null,
marked tinyint null comment 'boolean',
marked_by_pct tinyint null,
upper_threshold float null,
location_ulcx int null,
location_ulcy int null,
location_lrcx int null,
location_lrcy int null,
lower_threshold float null
);

create index ix_img_num
on img_choice (image_number);

create table img_contest
(
sub_id int not null,
image_number mediumint not null,
contest_name varchar(255) null,
overvoted tinyint null comment 'Boolean',
undervoted tinyint null,
validcount tinyint null,
votes_allowed int null,
underthreshold int null comment 'True if at least one choice was under threshold.',
img_contest_sub_id int not null,
img_contest_image_number mediumint not null,
tot_scores float null comment 'Sum of scores for this choice.',
overvoted_by_pct tinyint null comment '''by_pct'' refers to alternate scoring method "by percentage"',
undervoted_by_pct tinyint null,
ratio_by_pct float null comment 'ratio of candidate scores to total scores',
primary key (sub_id, image_number)
);

create index fk_img_contest_images1_idx
on img_contest (image_number);

create table precinct
(
id int not null
primary key,
precinct_name varchar(7) not null,
constraint precinct_name_UNIQUE
unique (precinct_name)
);

/* create table t
(
image_number mediumint not null,
precinct varchar(7) null,
contest_name varchar(255) null,
choice_name varchar(100) null,
overvoted tinyint null comment 'Boolean',
validcount tinyint null,
votes_allowed int null,
marked tinyint null comment 'boolean',
underthreshold int null comment 'True if at least one choice was under threshold.',
undervoted tinyint null
);

create table t_not_processed
(
image_number mediumint not null,
precinct varchar(7) null,
page_number varchar(3) null,
elections_batch_num varchar(6) null,
ETP_batch_num varchar(6) null,
assigned_to_pid mediumint null,
barcode varchar(14) null,
comments varchar(254) null comment 'Comments should include notations where a row was edited by hand or using an ad hoc program, such as "2020-11-24 Edited by WR to create precinct and page_number because barcodes obscured."',
lower_barcode varchar(14) null,
undecodable_reason varchar(255) null,
date_time_tabulated datetime null,
H_matrix json null,
processing_success int null,
flipped_form tinyint(1) null,
M_matrix json null,
processing_comment varchar(255) null
);

create table t_our_counts
(
precinct varchar(7) null,
contest_name varchar(255) null,
votes decimal(25) null
);

create table t_proecssed
(
imgnum mediumint null
);

create table temp_counts
(
precinct varchar(7) null,
page_1 bigint default 0 not null,
page_2 bigint default 0 not null,
page_3 bigint default 0 not null,
page_4 bigint default 0 not null,
unrecognized bigint default 0 not null,
other_error bigint default 0 not null,
not_processed bigint default 0 not null,
elections_nums text null
); */

/* create definer = root@localhost view compared as
select `hetptesting`.`icc`.`image_number`   AS `image_number`,
       `hetptesting`.`icc`.`precinct`       AS `precinct`,
       `hetptesting`.`icc`.`contest_name`   AS `contest_name`,
       `hetptesting`.`icc`.`choice_name`    AS `choice_name`,
       `hetptesting`.`icc`.`overvoted`      AS `overvoted`,
       `hetptesting`.`icc`.`validcount`     AS `validcount`,
       `hetptesting`.`icc`.`votes_allowed`  AS `votes_allowed`,
       `hetptesting`.`icc`.`marked`         AS `marked`,
       `hetptesting`.`icc`.`underthreshold` AS `underthreshold`,
       `hetptesting`.`icc`.`undervoted`     AS `undervoted`,
       `hetptesting`.`erm`.`id`             AS `id`,
       `hetptesting`.`erm`.`pct`            AS `pct`,
       `hetptesting`.`erm`.`contest`        AS `contest`,
       `hetptesting`.`erm`.`choice`         AS `choice`,
       `hetptesting`.`erm`.`ballots_cast`   AS `ballots_cast`,
       `hetptesting`.`erm`.`num_overvotes`  AS `num_overvotes`,
       `hetptesting`.`erm`.`num_undervotes` AS `num_undervotes`,
       `hetptesting`.`erm`.`num_invalids`   AS `num_invalids`,
       `hetptesting`.`erm`.`num_votes`      AS `num_votes`,
       `hetptesting`.`erm`.`mchoice`        AS `mchoice`
from (`hetptesting`.`img_con_cho` `icc`
         join `hetptesting`.`elec_res_matchable` `erm`
              on (((`hetptesting`.`erm`.`pct` = `hetptesting`.`icc`.`precinct`) and
                   (`hetptesting`.`erm`.`contest` = `hetptesting`.`icc`.`contest_name`) and
                   (`hetptesting`.`erm`.`mchoice` = `hetptesting`.`icc`.`choice_name`))));

create definer = root@localhost view elec_res_matchable as
select `hetptesting`.`elec_results`.`id`                           AS `id`,
       `hetptesting`.`elec_results`.`pct`                          AS `pct`,
       `hetptesting`.`elec_results`.`contest`                      AS `contest`,
       `hetptesting`.`elec_results`.`choice`                       AS `choice`,
       `hetptesting`.`elec_results`.`ballots_cast`                 AS `ballots_cast`,
       `hetptesting`.`elec_results`.`num_overvotes`                AS `num_overvotes`,
       `hetptesting`.`elec_results`.`num_undervotes`               AS `num_undervotes`,
       `hetptesting`.`elec_results`.`num_invalids`                 AS `num_invalids`,
       `hetptesting`.`elec_results`.`num_votes`                    AS `num_votes`,
       `convert_elc_choice`(`hetptesting`.`elec_results`.`choice`) AS `mchoice`
from `hetptesting`.`elec_results`
where (`hetptesting`.`elec_results`.`ballots_cast` > 0);

create definer = root@localhost view img_con_cho as
select `ico`.`image_number`   AS `image_number`,
       `img`.`precinct`       AS `precinct`,
       `ico`.`contest_name`   AS `contest_name`,
       `ich`.`choice_name`    AS `choice_name`,
       `ico`.`overvoted`      AS `overvoted`,
       `ico`.`validcount`     AS `validcount`,
       `ico`.`votes_allowed`  AS `votes_allowed`,
       `ich`.`marked`         AS `marked`,
       `ico`.`underthreshold` AS `underthreshold`,
       `ico`.`undervoted`     AS `undervoted`,
       `ich`.`marked_by_pct`  AS `marked_by_pct`,
       `ich`.`score`          AS `score`
from ((`hetptesting`.`img_contest` `ico` join `hetptesting`.`img_choice` `ich` on ((
        (`ico`.`image_number` = `ich`.`image_number`) and (`ico`.`sub_id` = `ich`.`img_contest_subid`))))
         join `hetptesting`.`images` `img` on ((`ico`.`image_number` = `img`.`image_number`)));

create definer = root@localhost function convert_elc_choice(s varchar(255)) returns varchar(255)
begin
        declare t varchar(255);
        set t = regexp_replace(s, '.*write-ins', '(WRITE IN)');
        set t = regexp_replace(t, '[.,"]', '');
        set t = regexp_replace(t, '[\'-]', ' ');
        set t = regexp_replace(t, ' and .*', '');
        return t;
    end;
 */