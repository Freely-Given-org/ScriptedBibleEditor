# ScriptedBibleEditor EditComandTable

A tab-separated values (TSV) file that contains the list
of contextual edit commands to be applied in order

The edit commands can be simple substitutions, e.g., change "color" to "colour",
or might have contextual or other conditions that will limit the edits.

## Edit command table file

Default is named _EditCommands.tsv_, but any other name can be specified.
If a full path is not given, the edit command table file is first searched for in the current folder,
and then in the folder where the input file(s) are located.

The file is a UTF-8 encoded 15-column table where table columns are separated by tab characters.
The first row in the file is the column headers which should be
    Type	IBooks	EBooks	IMarkers	EMarkers	IRefs	ERefs	PreText	SCase	Search	PostText	RCase	Replace	Name	Comment
Unix line-endings are recommended, but Windows line-endings will also be acceptable.
The file may begin with an optional Byte Order Marker (BOM).
Blank lines are ignored
Lines beginning with # are regarded as comments.

## Edit commands

### Type

The _Type_ column contains two letters:

1. The first letter can be:
    - w: match WHOLE WORDS only
    - i: match text INSIDE words (must be less than a whole word)
    - a: any
    - r: match Python regular expression

### Include books (IBooks)

A list of BibleOrgSys (BOS) books codes which the command line applies to.
Empty default is to include all books.

### Exclude books (EBooks)

A list of BOS books codes which the command line excludes.
Empty default is to exclude no books.

### Include markers (IMarkers)

A list of ESFM/USFM markers which the command line applies to.
Empty default is to include all markers, i.e., all lines in the file.

### Exclude markers (EMarkers)

A list of ESFM/USFM markers which the command line excludes.
Empty default is to exclude no markers.

### Include references (IRefs)

A list of B_C:V references which the command line applies to.
Note that giving a reference automatically exclude all non-verse text (such as headers).
Empty default is to include all references, i.e., all verses and additional fields in the Bible.

### Exclude references (ERefs)

A list of B_C:V references which the command line excludes.
Empty default is to exclude no verses.

### PreText

### Search case (SCase)

This sets the case of the search match (for non-regex replaces)
    -i: case INSENSITIVE (match any case)
    -c: CASE match (must be exact case match)
    -s: SENTENCE case (First letter can be uppercase at the beginning of a sentence or similar) -- for this the search text field should be lowercase

### Search text

The text (or Python regex) with the text to be searched for.
It’s an error if this field is empty.
See https://docs.python.org/3/howto/regex.html for how to write Python regular expressions.

### PostText

### Replace case (RCase)

### Replace field

The text (or Python regex) with the text to be replaced.
If the field is empty, the search text will be deleted.

### Name

An optional name for the rule (or for a group of rules).
Rules can then be applied or excluded by name.

### Comment

An optional comment to explain the rule or the reason for it.