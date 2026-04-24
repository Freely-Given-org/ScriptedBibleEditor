# ScriptedBibleEditor

A command-line editor that applies a table of edit commands to a batch of ESFM or USFM Bible files

## Overview

ScriptedBibleEditor is a Python program which understands
[USFM](https://docs.usfm.bible/usfm/latest/index.html) and [ESFM](https://github.com/Freely-Given-org/ESFM)
Bible files (with special features to handle USFM word numbers) and
then applies edits (specified in TSV files) to the specified ESFM or USFM file(s).

An optional TOML control file can be saved so that sets of edits can easily
be applied over and over again without having to remember all the
command-line parameters.
The control file contains global program settings (including input and
output files/folders) and a list of one or more TSV tables.

Those TSV tables specify edit commands including Bible aware references,
e.g., do these changes in Ezra and Nehemiah only, or in every book except Psalms,
or in Genesis chapter 1 only, or only in Ephesians 4:2.

The edit commands can be simple substitutions, e.g., change "color" to "colour",
or might have contextual or other conditions that will limit the edits.

There’s been no attempt to make this process particularly efficient in terms of memory use or CPU cycles.
The current focus is more on making the process convenient and powerful for converting a Bible translation into something different.

## Edit command table

See the EditCommandTable folder for details of the TSV (tab-separated values) table and how edit commands are expressed.

## Control file

See the ControlFile folder for details of the optional control file
which can specify the file extensions, whether or not backup files or folders are made, etc.

## Command line parameters

(to be written)

## Rust plans

This Python prototype hasn't been designed to be fast or efficient -- we'll rewrite in Rust to do that.
Note also that not all envisaged features have been fully implemented,
i.e., some of the TSV columns might work better than others.

The first task would be to become familiar with SBE and the tasks it currently does.
This [makefile](https://github.com/Freely-Given-org/OpenEnglishTranslation--OET/blob/main/scripts/makefile)
uses SBE extensively (along with Python scripts) to create a literal Bible version,
and the TOML and TSV files in that repo along with the Bible files at various stages should provide good test data
and because they're open licenced, can be statically copied into this repo into a test_data folder.

Then the program logic can be rewritten in Rust (e.g., using Claude or similar) into a Rust folder,
and tested.

In addition, specific Rust tests could be written to test each feature of the TSV files (including combinations of columns).
This will likely uncover any features that were obviously intended and never properly implemented in the Python.

It should be ensured that SBE can operate in a CLI mode where a TOML or TSV file is specified
(the TOML file shouldn't specify physical input and output folders, etc.),
and then it reads a USFM/ESFM file from stdin and writes the edited file to stdout,
thus it could be included in a typical Unix-style pipeline.

The documentation should then be improved to make it more easily usable.

Then the Python code could be removed, folders could be cleaned up,
and it should be published so that it can be used in any Bible adjustment tool chain.