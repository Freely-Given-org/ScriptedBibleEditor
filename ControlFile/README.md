# ScriptedBibleEditor

A command-line editor that applies a table of edit commands to a batch of ESFM or USFM Bible files

## Overview

ScriptedBibleEditor is a Python program which accepts a TSV table of edit commands, and an ESFM or USFM file or folder of files,
and applies the edits to the file(s).

The edit commands can be simple substitutions, e.g., change "color" to "colour",
or might have contextual or other conditions that will limit the edits.

An optional control file can be saved so that sets of edits can easily
be applied over and over again without having to remember all the
command-line parameters.

## Edit command table

See the EditCommandTable folder for details of the TSV (tab-separated values) table and how edit commands are expressed

## Control file

See the ControlFile folder for details of the optional control file
which can specify the file extensions, whether or not backup files or folders are made, etc.

## Command line parameters
