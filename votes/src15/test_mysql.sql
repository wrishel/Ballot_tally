drop table form_contest;

CREATE TABLE IF NOT EXISTS form_contest(  
    form_id VARCHAR (12),
    contest_id VARCHAR (12),
    candidate_id VARCHAR (12),
    score FLOAT,
    PRIMARY KEY (form_id , contest_id, candidate_id)
) default charset utf8 comment '';

insert into form_contest (form_id, contest_id, candidate_id, score) values (1,1,1,50.0);

insert into form_contest (form_id, contest_id, candidate_id, score) values (1,1,2,10.0)
on duplicate key update form_id = values(form_id), contest_id = values(contest_id), 
candidate_id = values(candidate_id), score = values(score);

select * from form_contest;