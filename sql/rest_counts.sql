/* Reset all counting in order to start over
   1/22/21
 */

update images set
    undecodable_reason=NULL,
    date_time_tabulated=NULL,
    H_matrix=NULL,
    processing_success=NULL,
    flipped_form=NULL,
    M_matrix=NULL,
    processing_comment=NULL
where image_number = image_number;
truncate img_choice;
truncate img_contest;