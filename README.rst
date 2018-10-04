odarchive
=========

Optical disc archiving - converting file systems to iso files and back

Python archive tool to convert drive paths to ISO's

Usage
=====

Summary of commands, see below for commandline options.

+-----------+-----------------------------+
| Commands  | Comment                     |
+===========+=============================+
| init      | Creates a new catalogue     |
+-----------+-----------------------------+
| write_iso | write out an iso            |
+-----------+-----------------------------+
| archive   |                             |
+-----------+-----------------------------+
| segment   | split archive into segments |
+-----------+-----------------------------+

odarchive create_db drive_path
------------------------------

Creates a database catalogue.json in current working directory from
files in drive_path

odarchive plan_iso size
-----------------------

Enriches the database to plan building ISO with a maximum size of n
bytes or using

- 'cd'     = 700MB
- 'dvd'    = 4.7GB
- 'bluray' = 25GB
- 'bd-dl' = 50GB
- 'bd-xl' = 100GB
- 'bd-xx' = 128GB

odarchive num_isos
------------------

*Planned* Return number of isos required

odarchive create_iso n
----------------------

Default for n is 0 (numbering from Zero)

Future enhancements
===================

convert a json catalogue into a pickle
--------------------------------------

Currently when working on a backup plan the data is pickled from command
to command. In order to work with existing cataloges this is what you
need.

Make a .exe
-----------

Create a single exe that will do this job or make an exe that can be
installed via pip.

Segemented isos into specific size
----------------------------------

Convert catalogue from dictionary to database
---------------------------------------------

At the moment the catalogue database is an in memory dictionary. This
will limit it to about 2 million files per GB of available memory.

Make a service with feedback on status
--------------------------------------

Eg archiving Z drive has taken at least an hour and I don’t if working
or crashed.

Make calculating Hash multi threaded
------------------------------------

May work faster

Add size of catalogue to length of reserved space
-------------------------------------------------

Incremental
-----------

| With an old catalogue and drive path create a additional catalog. Can
  be current point in time, eg so not reference files that were deleted.
| This also allows rescanning without making any changes. This should
  also cover the case of multiple single backups being coalesced into a
  bigger backup. You might in large file format decide to backup a
  number of individual files first.

Split large files
-----------------

Make a service as a Glacier replacement.
----------------------------------------

Eg rerun and post changes via web

Make read only cached drive
---------------------------

robot plus discs 600 discs = 15TB

Calculate directory size when segmenting
----------------------------------------

At the moment a fixed directory size is added to each entry

get_info
--------

Add JsON alternative to returned data

Make Platinum discs
-------------------

GBP16 a g SG 19 1u 12cm area = 0.012 a 1u coat costs about GBP4 a disc
However if these had a glass substrate they might have a very long life.
Potentially you could write them naked and then cover them with another
glass slip. Could even write with an electron beam although might be
expensive

UDF Bridge format
=================

To make the discs more compatible add a ISO 9660 directory structure as
well as the UDF

In order to make the discs more compatible both a UDF and a ISO 9660
directory structure are output. There are different levels of ISO 9660
structure but I have chosen level 3 as the standard.

The ISO 9660 leads to complications as it is restricted to shorter
directory names and a maximum directory depth of 7. This means the the
conversion from UDF directories to ISO 9660 directories is lossy. From
this it means that you have to implement a lossless scheme (store the
directory mapping as a dictionary) so that you can do multiple backups
on multiple discs and still have a coherent directory structure.

Technical
=========

Segmentation
------------

When a catalogue is created for the first time it is not segmented.
Segmenting refers to writing out a single disc which has smaller
capacity than the total archive.

File name
---------

| This services is planned to work from supplied USB drives.
| The internal file name is a UDF Abolute Path. It is an absolute path
  so that if the name of the Data directory changes this won’t make a
  difference when combining discs with different naming conventions.

User case history: I want to backup some critical files first eg my own
Photgraphs and video and then other files The deeper the file system on
the USB the better the result will be

Disk directory layout
---------------------

| /Data + All data files catalogue.json #
| README.MD

Json file format
~~~~~~~~~~~~~~~~

| JsonFile = HeadingSection \*FileDefinition
| HeadingSection = Version
| FileDefinition = Hash FileNameList Mtime Size

Max. filename length 255 bytes (path 1023 bytes)

Example::
    {
        "version": 1,
        "files" :  {
            "Hash1": {
                filenames : {
                    "data/first.html" : null,
                    "data/first_copy.html" : null,
                }
                size : 21,
                mtime : ??
            },
            "Hash2": {
                filenames : {
                    "data/second.txt" : null,
                }
            size : 22,
            mtime : ?? },
        }
    }

Software Structure
==================

This is one module: odarchive.

This has three top level modules: - ``archive.py`` which handles the
archive - ``odarchive_cli.py`` which puts a command line wrapper around
the archive code. - a ``_version.py`` which holds the version number
constants for both pypy and the code

The archive code is the main code and 4 sub files: - ``consts.py``
General constants - ``file_db.py`` handles a file database - ``hash_db``
extends the file database to include a database of hashentries -
``hash_file_entry.py`` creating hashes for single files

There is a distinct order in which things must happen:

-Scan the file and build a file database. -Create a hash tables

Inspiration
===========

Thanks to M Ruffalo of
https://github.com/mruffalo/hash-db/blob/master/hash_db.py for a lot of
inspiration.

Licensing
=========

Using an MIT license see LICENSE.
