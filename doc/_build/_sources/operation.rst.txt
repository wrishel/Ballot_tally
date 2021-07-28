Operation
=========

This section lists the executable programs that accomplish the steps outlined in Concept of Operations and some other utilities.

General Information
-------------------

.. _filestruc:

Image File Directory Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The image files are arranged in a directory tree with 1000 images per subdirectory. The subdirectory name is the first three digits of the file named.

::

    location/
        000/
            000000.jpg
            000001.jpg
            ...
            000999.jpg
        001/
            001000.jpg
            001001.jpg
            ...
        ...


Major Data Base Tables
^^^^^^^^^^^^^^^^^^^^^^
The following tables are significant in the processing flow.

.. table:: Major Database Tables
   :widths: 20, 80
   :align: left


   =======  =====
   Table    Description
   =======  =====
   Images   Tracks the state of an image through the processing steps.

            Primary key: image number
   (Other)  (to be added later)
   =======  =====

The associated MySQL database has two schemas. Currently production work is run in the database named "testing".

External Inputs
^^^^^^^^^^^^^^^
In addition to the images, the following data is imported through .csv or .tsv files.
1 The exact spelling of contest names and the corresponding choices is used in generating templates.
2 A table relating a subfield of the barcodes to precinct ID
3 A table relating a subfield of the barcodes to party
4 Canvas results (i.e., the official result of the election).

This information is provided by the Humboldt County elections department.

In theory, the information in (1) and (4) could be obtained by scraping various public web sites and (2) and (3) could be created by using OCR on the ballots during the creation of templates. However we have not found open source OCR that makes this easy.

In theory, OCR could eliminate the requirement for (2) and (3) altogether but the same issue about the quality of OCR makes using the barcodes more reliable.

Global Parameters
^^^^^^^^^^^^^^^^^
The source file GLB_globs.py contains a number of static globals including paths to specific input and output directories.


Scanning
--------
The control program for scanning is currently a separate project written in Python 2.7. Its output is a set of files described in `Image File Directory Structure`_. These files are never modified by any downstream process so that the creation date matches manual logs created during scanning.

(This program is currently not in this repository.)

Ballot Classification
---------------------
**discover_new_images.py**

This daemon periodically checks the image directory for images that are not already present in the images table. If it finds new ones it adds them to the table. Multiple copies of this program should not be run at the same time, but it the single copy can run in parallel with process_barcodes.py.

**process_barcodes.py**

This daemon discovers new entries in the images table and examines the barcodes in the corresponding image to determine the precinct, page number, and party associated with the ballot. This information is added to the entries in the images table.

Multiple copies of process_barcodes.py may run in parallel to achieve substantial performance improvements.

.. _HETP_main.py:

**HETP_main.py**

This program is capapble of launching daemon processes from a list of programs. The list specifies how many copies of the program should be run simultaneously. It could support operating all of these processing steps in parallel. Scanning, Ballot classification, ballot classification, ballot decoding, and vote determination.

However, scanning is actually run on a different computer than all the other steps, that computer being in a controlled access area of the elections department. Data is then transferred by sneakernet to an off-site computer where the other steps are processed.

Ballot Templating
-----------------
Templates are created for each combination of precinct, page number, and party using a semi-automated process to be described here later.

Ballot Decoding and Vote Determination
--------------------------------------
**process_votes.py**

process_votes.py discovers entries in the images table that have identified precinct, page nuber, and party but where the votes have not been determined. For each some issues, it normalizes the image against the template, determines the scores for each sense area and then determines which sense areas are marked. For any contest it may also set a boolean value indicating that the marking is uncertain.

This program calls on two modules: ballot_scanner does the heavy lifting of determining the scores and marks_from_scores accepts the scores for a contest and decides which choices were selected. It also may indicate that a contest was undervoted, overvotes, or whether the score determination is uncertain.

Analysis
--------
**dbase.report_comparison_newer()**

This is a function in the dbase module that produces the primary output report. Currently it is run if you run the dbase.py file as a main program.


