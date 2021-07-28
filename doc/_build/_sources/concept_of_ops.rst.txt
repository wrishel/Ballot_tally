Concept of Operations
=====================

This software was created to support the work of the Humboldt Election Transparency Project
(HETP - https://electionstransparencyproject.com/),
an independent non-profit organization in Humboldt County, CA.

With the cooperation of local elections officials, volunteers of HETP scan ballots that
have already been counted officially. The scanned images are processed to identify counts by
precinct and party and the counts are compared to officially posted counts.

The set of scanned information may be obtained from HETP for local interest or in support
of academic projects in accordance with its policies.

The scanned ballot images are further processed to count the votes in the contests and these
counts are compared to the official counts. Because the process of examining hand-marked ballots
is inexact and often requires manual examination of ballots to determine the intent of
a voter, any discrepancies detected are not regarted as refuting the official results. They
simply indicate an area that might be worthy of a more detailed look.

An example of the output of our work, along with some detailed explanation of the report are available at our `Letter to volunteers`_.

.. _`Letter to volunteers`: https://docs.google.com/document/d/1eD4Jp5A9wsKxUWTmF-Jc16pV70OW5ghSRm8IpO1uSiw

Major Processing Steps
----------------------
The discrete steps in processing an election include Sscanning, Ballot Classification,
Ballot Templating,
Ballot Decoding,
Vote Determination, and
Analysis. Each is described below.

Scanning
^^^^^^^^
HETP volunteers working on the premises of the elections office receive ballots in batches from elections workers after they have been validated, scanned and accepted by official election counting system. A protocol in place provides a log of custody of the batches and there are always two volunteers working with an elections office person.

Using an industrial scanner, the volunteers create images, one for each side of each page of a ballot. Currently the images are 300 DPI 8-bit color. Image files are named with sequential numbers, starting with 000000.jpg. The scanner imprints the same number vertically on the left side of the front of a page. With this imprint it is possible to subsequently examine the ballots in a batch to verify that it was scanned by HETP and locate the image.

In a recent election, approximately 279,000 images were created from the ballots cast by almost 70,000 voters, one image for each side of the two pages that constituted a single ballot. The ratio is not exactly 4:1 because not all voters returned both pages of the ballot.

Ballot Classification
^^^^^^^^^^^^^^^^^^^^^
The ballot images are first scanned to identify the precinct, page number, and party (for primary elections). Quick reports are provided tallying the counts. The combination of precinct, page number, and party constitute a "ballot type" for this system. That is, all images of the same type have the identical positioning of contests and candidates.

Ballot Templating
^^^^^^^^^^^^^^^^^
The collected ballot images are analyzed using software built on the OpenCV library in order to determine where a voter will have marked the ballot for a specific choice in a contest. Because of positioning variability in the scanning, scanning noise, and extraneous marks on ballots, numerous examples of each ballot type are examined until there is sufficient information to deduce the positioning. This analysis is aided by textual information that contains the exact spelling and punctuation of names of contests and candidates for the election.

Ballot Decoding
^^^^^^^^^^^^^^^
Once templates have been established all images are examined to compile data on the marks created by the voters. At this level each sense area (a square on our ballots) is given a score between 0 and 100 that approximates how thoroughly the sense area was filled in. Nothing outside the sense area is examined.

Vote Determination
^^^^^^^^^^^^^^^^^^
After the scores are recorded this system examines each contest on a ballot, interpreting the scores to determine whether a given choice was marked by the voter. There are situations where a person is required to interpret the voter's intent on a scanned ballot. That intent cannot be determined solely by seeing how well a sense area is filled in. These include

* Voters inconsistently fill in the sense areas and due to minor variations in the positioning of ballots it is possible, for example, that a low score indicates that the voter marked the area with a check mark instead of filling it in. On the other hand, it's also ppossible that a low-sccoring sense area is just a place where the voter accidentially touched it with a pen. This is often called a "hesitation mark".

* It is also possible that the voter apparently intentionally marked more sense areas than the number of choices permitted in a contest. This may be an overvote or, in mail-in ballots, it may be a way of correcting an error in marking the ballots. Information outside the sense area enable a person to interpret the voter's intent.

Official voting systems devote considerable person time to examining ballots with ambiguous marks and recording their interpretation of the voter's intent.
However our vote verification time and person bandwidth doesn't permit manual determination of intent.
Our software estimates the voter's intent based on the relative scores of the sense areas within a contest. However, there are situations where the certainty that such determination is an error. For those, we record the vote as uncertain.

Analysis
^^^^^^^^
After vote determination we compare our counts to the Official Canvas published by the Elections department. For most contests even if we have some marks as uncertain, the margin between winning and nonwinning choices is so high that we consider that we have confirmed that contest.
If the margin is close and we have a high number of uncertain votes, we would say that contest was too close to call.
Interested parties may want to examine the ballot images directly for that contest.






