# ScriptedBibleEditor

An editor that applies a table of commands to a batch of ESFM or USFM Bible files

This is a Python program which accepts a TSV table of edit commands, and an ESFM or USFM file or folder of files,
and applies the edits to the file(s).

The edit commands can be simple substitutions, e.g., change "color" to "colour",
or might have contextual or other conditions that will limit the edits.

## Script table

See the TableProtocol folder for details of the TSV (tab-separated values) table and how edit commands are expressed

## Command line parameters
