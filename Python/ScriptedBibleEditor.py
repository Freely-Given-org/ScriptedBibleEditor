#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# ScriptedBibleEditor.py
#
# Module handling ScriptedBibleEditor functions
#
# Copyright (C) 2022-2024 Robert Hunt
# Author: Robert Hunt <Freely.Given.org+BOS@gmail.com>
# License: See gpl-3.0.txt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Module handling ScriptedBibleEditor functions.

TODO: Need to allow parameters to be specified on the command line

Updates:
    2023-03-06 To use new Python tomllib (which parses binary files) so only works now in Python3.11 and above
    2023-03-07 To copy TSV tables across to the output for ESFM projects
    2023-03-08 To handle ESFM ¦nnn word-link numbers
    2023-09-13 Now handles multiple words in search/replace (but can't reorder them)
"""
from gettext import gettext as _
from typing import Dict, List, Set, NamedTuple, Tuple, Optional
from pathlib import Path
import os
import shutil
import tomllib
import logging
from datetime import datetime
import re
import unicodedata

import BibleOrgSysGlobals
from BibleOrgSysGlobals import fnPrint, vPrint, dPrint

import sys
sys.path.insert( 0, '../../BibleTransliterations/Python/' ) # temp until submitted to PyPI
from BibleTransliterations import load_transliteration_table, transliterate_Hebrew, transliterate_Greek


LAST_MODIFIED_DATE = '2024-03-25' # by RJH
SHORT_PROGRAM_NAME = "ScriptedBibleEditor"
PROGRAM_NAME = "Scripted Bible Editor"
PROGRAM_VERSION = '0.31'
PROGRAM_NAME_VERSION = f'{SHORT_PROGRAM_NAME} v{PROGRAM_VERSION}'

DEBUGGING_THIS_MODULE = False


DUMMY_VALUE = 999_999 # Some number bigger than the number of characters in a line

DEFAULT_CONTROL_FILE_NAME = f'{SHORT_PROGRAM_NAME}.control.toml'

COMMAND_TABLE_NUM_COLUMNS = 15
COMMAND_HEADER_LINE = 'Tags	IBooks	EBooks	IMarkers	EMarkers	IRefs	ERefs	PreText	SCase	Search	PostText	RCase	Replace	Name	Comment'
assert ' ' not in COMMAND_HEADER_LINE
assert COMMAND_HEADER_LINE.count( '\t' ) == COMMAND_TABLE_NUM_COLUMNS - 1


class EditCommand(NamedTuple):
    tags: str           # 0
    iBooks: list        # 1
    eBooks: list        # 2
    iMarkers: list      # 3
    eMarkers: list      # 4
    iRefs: list         # 5
    eRefs: list         # 6
    preText: str        # 7
    sCase: str          # 8
    searchText: str     # 9
    postText: str       # 10
    rCase: str          # 11
    replaceText: str    # 12
    name: str           # 13
    comment: str        # 14


class State:
    def __init__( self ) -> None:
        """
        Constructor:
        """
        self.controlData = None

        # if DEBUGGING_THIS_MODULE: # setup test state
        #     self.commandTableFilepath = Path( '../TestFiles/editCommandTable.tsv' )
        #     if not self.commandTableFilepath.exists():
        #         self.commandTableFilepath = Path( 'TestFiles/editCommandTable.tsv' )
    # end of ScriptedBibleEditor.__init__


state = None
def main() -> None:
    """
    """
    BibleOrgSysGlobals.introduceProgram( __name__, PROGRAM_NAME_VERSION, LAST_MODIFIED_DATE )

    global state
    state = State()
    if BibleOrgSysGlobals.commandLineArguments.flagReplacements:
        vPrint( 'Quiet', DEBUGGING_THIS_MODULE, "<<<<< LEAVE_REPLACEMENT_INDICATORS flag is enabled! (Maybe affect consecutive replacements) >>>>>" )

    load_transliteration_table( 'Hebrew' )
    load_transliteration_table( 'Greek' )

    if controlFilepath := findControlFile():
        if loadControlFile( controlFilepath ):
            if loadCommandTables():
                executeEditsOnAllFiles()
            else: vPrint( 'Quiet', DEBUGGING_THIS_MODULE, "No command tables found!\n" )
    else: vPrint( 'Quiet', DEBUGGING_THIS_MODULE, "No control file found!\n" )
# end of ScriptedBibleEditor.main


def findControlFile():
    """
    """
    fnPrint( DEBUGGING_THIS_MODULE, "findControlFile()")

    searchPaths = [DEFAULT_CONTROL_FILE_NAME,]
    try:
        if BibleOrgSysGlobals.commandLineArguments.controlPath: # May not even be defined
            searchPaths.insert( 0, f'{BibleOrgSysGlobals.commandLineArguments.controlPath}/{DEFAULT_CONTROL_FILE_NAME}')
    except ValueError:
        pass

    for filepath in searchPaths:
        if os.path.isfile(filepath):
            vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"  Loaded control file from {filepath}" )
            return filepath

    logging.critical( f"No control file found in {searchPaths}." )
# end of ScriptedBibleEditor.findControlFile


def loadControlFile( filepath ) -> bool:
    """
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"loadControlFile( {filepath} )")

    state.controlFolderpath = os.path.dirname( filepath )
    vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"Loading control file: {filepath}…" )
    with open(filepath, 'rb') as controlFile:
        state.controlData = tomllib.load( controlFile )
        displayTitle = f"'{state.controlData['title']}'" \
                        if 'title' in state.controlData and state.controlData['title'] \
                        else "control file"
        vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"    Loaded {len(state.controlData)} parameter{'' if len(state.controlData)== 1 else 's'} from {displayTitle}." )

    # Check that the control file mostly contains what we expected
    # print( type(state.controlData), len(state.controlData), state.controlData )
    for someKey in state.controlData:
        if not someKey.endswith( '.tsv' ) \
        and someKey not in ('title','description',
                            'inputFolder','inputFilenameTemplate',
                            'outputFolder','outputFilenameTemplate','clearOutputFolder','createOutputFolder',
                            'applyOrder', 'commandTables',
                            'handleESFMWordNumbers'):
            logging.critical( f"Unexpected '{someKey}' entry in TOML command file." )

    return len(state.controlData) > 0
# end of ScriptedBibleEditor.loadControlFile


def loadCommandTables() -> bool:
    """
    Load all the command tables in the specified folder
        into state.commandTables

    Does some basic checking at the same time
    """
    fnPrint( DEBUGGING_THIS_MODULE, "loadCommandTables()")
    if 'commandTables' in state.controlData:
        state.commandTables = {}
        for name, givenFilepath in state.controlData['commandTables'].items():
            completeFilepath = os.path.join( state.controlFolderpath, givenFilepath )
            if os.path.isfile(completeFilepath):
                vPrint( 'Info', DEBUGGING_THIS_MODULE, f"  Loading command table file: {completeFilepath}…" )
                assert name not in state.commandTables
                state.commandTables[name] = []
                with open( completeFilepath, 'rt', encoding='utf-8' ) as commandTableFile:
                    line_number = 0
                    for line in commandTableFile:
                        line_number += 1
                        line = line.rstrip( '\r\n' )
                        if not line or line.startswith( '#' ): continue
                        tab_count = line.count( '\t' )
                        if tab_count>9 and tab_count < (COMMAND_TABLE_NUM_COLUMNS - 1): # Some editors delete trailing columns
                            line += '\t' * (COMMAND_TABLE_NUM_COLUMNS - 1 - tab_count) # Add back the empty columns
                            tab_count = line.count( '\t' )
                        if tab_count != (COMMAND_TABLE_NUM_COLUMNS - 1):
                            logging.critical( f"Skipping line {line_number} which contains {tab_count} tabs (instead of {COMMAND_TABLE_NUM_COLUMNS - 1})" )
                        if line == COMMAND_HEADER_LINE:
                            continue # as no need to save this

                        # Get the fields and check some of them
                        fields = line.split( '\t' ) # 0:Tags 1:IBooks 2:EBooks 3:IMarkers 4:EMarkers 5:IRefs 6:ERefs 7:PreText 8:SCase 9:Search 10:PostText 11:RCase 12:Replace 13:Name 14:Comment
                        tags, searchText, replaceText = fields[0], fields[9], fields[12]
                        iBooks, eBooks = fields[1].split(',') if fields[1] else [], fields[2].split(',') if fields[2] else []
                        iMarkers, eMarkers = fields[3].split(',') if fields[3] else [], fields[4].split(',') if fields[4] else []
                        iRefs, eRefs = fields[5].split(',') if fields[5] else [], fields[6].split(',') if fields[6] else []
                        for iBook in iBooks:
                            assert iBook in BibleOrgSysGlobals.loadedBibleBooksCodes, iBook
                        for eBook in eBooks:
                            assert eBook in BibleOrgSysGlobals.loadedBibleBooksCodes, eBook
                        for iRef in iRefs:
                            assert iRef.count('_')==1 and iRef.count(':')==1, iRef
                            iRefBits = iRef.split('_')
                            assert iRefBits[0] in BibleOrgSysGlobals.loadedBibleBooksCodes, iRef
                            iRefC, iRefV = iRefBits[1].split(':')
                            assert iRefC[0].isdigit() and iRefV[0].isdigit(), iRef
                        for eRef in eRefs:
                            assert eRef.count('_')==1 and eRef.count(':')==1, eRef
                            eRefBits = eRef.split('_')
                            assert eRefBits[0] in BibleOrgSysGlobals.loadedBibleBooksCodes, eRef
                            eRefC, eRefV = eRefBits[1].split(':')
                            assert eRefC[0].isdigit() and eRefV[0].isdigit(), eRef

                        # Adjust and save the fields
                        if 'H' in tags:
                            newReplaceText = transliterate_Hebrew( replaceText, searchText[0].isupper() )
                            if newReplaceText != replaceText:
                                # print(f" Converted Hebrew '{replaceText}' to '{newReplaceText}'")
                                replaceText = f'H‹{newReplaceText}›H' if BibleOrgSysGlobals.commandLineArguments.flagReplacements else newReplaceText
                            for char in replaceText:
                                if 'HEBREW' in unicodedata.name(char):
                                    logging.critical(f"Have some Hebrew left-overs in '{replaceText}'")
                                    break
                        if 'G' in tags:
                            newReplaceText = transliterate_Greek( replaceText )
                            if newReplaceText != replaceText:
                                # print(f" Converted Greek '{replaceText}' to '{newReplaceText}'")
                                replaceText = f'G‹{newReplaceText}›G' if BibleOrgSysGlobals.commandLineArguments.flagReplacements else newReplaceText
                            for char in replaceText:
                                if 'GREEK' in unicodedata.name(char):
                                    logging.critical(f"Have some Greek left-overs in '{replaceText}'")
                                    break
                        state.commandTables[name].append( EditCommand( tags,
                                iBooks, eBooks, iMarkers, eMarkers, iRefs, eRefs,
                                fields[7], fields[8], searchText, fields[10], fields[11],
                                f'R‹{replaceText}›R' if BibleOrgSysGlobals.commandLineArguments.flagReplacements and BibleOrgSysGlobals.verbosityLevel>2 else replaceText, fields[13], fields[14] ) )
                vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"    Loaded {len(state.commandTables[name])} command{'' if len(state.commandTables[name])==1 else 's'} for '{name}'." )
            else: vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"      '{completeFilepath}' is not a file!" )
        return True
    else:
        vPrint("No command tables available to load")
    return False
# end of ScriptedBibleEditor.loadCommandTables


def executeEditsOnAllFiles() -> bool:
    """
    Returns a success flag.
    """
    fnPrint( DEBUGGING_THIS_MODULE, "executeEditsOnAllFiles()" )

    inputFolder = os.path.join( state.controlFolderpath, state.controlData['inputFolder'] )
    if not os.path.isdir(inputFolder):
        logging.critical( f"Unable to open input folder: {inputFolder}" )
        return False
    inputCount = 0
    for someName in os.listdir(inputFolder):
        if os.path.isfile(os.path.join(inputFolder, someName)):
            inputCount += 1
    if inputCount < 1:
        vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"No files found in input folder: {inputFolder}" )
        return False
    numTables = len( state.commandTables )
    vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"\nApplying edits from {numTables} table{'' if numTables==1 else 's'} to {inputCount} file{'' if inputCount==1 else 's'} in {inputFolder}" )

    outputFolder = os.path.join( state.controlFolderpath, state.controlData['outputFolder'] )
    if state.controlData['clearOutputFolder'] == True:
        if state.controlData['createOutputFolder'] == True:
            shutil.rmtree( outputFolder ) # This removes the actual folder (and contents) and a new empty folder will then be created below
        else: # Remove the individual files (but we don't remove any subfolders)
            for file in os.scandir( outputFolder ):
                os.unlink( file.path )
    if state.controlData['createOutputFolder'] == True:
        if not os.path.isdir( outputFolder ):
            os.makedirs( outputFolder )

    applyOrder = 'AllTablesFirst' # default
    if 'applyOrder' in state.controlData and state.controlData['applyOrder']:
        applyOrder = state.controlData['applyOrder']

    numFilesWritten = 0
    if applyOrder == 'AllTablesFirst':
        esfmFilelist = set()
        for BBB in BibleOrgSysGlobals.loadedBibleBooksCodes:
            UUU = BibleOrgSysGlobals.loadedBibleBooksCodes.getUSFMAbbreviation( BBB ) or ''
            inputFilename = state.controlData['inputFilenameTemplate'] \
                                    .replace( 'BBB', BBB ).replace( 'UUU', UUU.upper() )
            try:
                outputFilename = state.controlData['outputFilenameTemplate'] \
                                    .replace( 'BBB', BBB ).replace( 'UUU', UUU.upper() )
            except KeyError:
                outputFilename = inputFilename
            inputFilepath = os.path.join( inputFolder, inputFilename )
            if os.path.isfile( inputFilepath ):
                vPrint( 'Info', DEBUGGING_THIS_MODULE, f"  Processing {inputFilename}…" )
                with open( inputFilepath, 'rt', encoding='utf-8') as inputFile:
                    inputText = inputFile.read()
                vPrint( 'Info', DEBUGGING_THIS_MODULE, f"    Read {len(inputText):,} characters from {inputFilename}" )
                extractESFMTableNames( inputFilename, inputText, esfmFilelist )
                appliedText = executeEdits( BBB, inputText, state.commandTables )
                if appliedText != inputText: # Make a backup before overwriting the input file
                    # Putting the conversion date/time into the output file doesn't work well with Git
                    # appliedText = appliedText.replace( '\n\\h ', f"\n\\rem USFM file edited {datetime.now().strftime('%Y-%m-%d %H:%M')} by {PROGRAM_NAME_VERSION}\n\\h " )
                    appliedText = appliedText.replace( '\n\\h ', f"\n\\rem USFM file edited by {PROGRAM_NAME_VERSION}\n\\h " )
                    outputFilepath = os.path.join( outputFolder, outputFilename )
                    if outputFilepath == inputFilename:
                        BibleOrgSysGlobals.backupAnyExistingFile( inputFilename, numBackups=3 )
                    vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"    Writing {len(appliedText):,} characters (was {len(inputText):,}) to {outputFilename}…" )
                    with open( outputFilepath, 'wt', encoding='utf-8' ) as outputFile:
                        outputFile.write(appliedText)
                    numFilesWritten += 1
                # break # while debugging first file
        if esfmFilelist:
            numFilesWritten += copyAuxilliaryESFMfiles( Path(inputFolder), Path(outputFolder), esfmFilelist )
    else:
        other_orders_not_implemented_yet

    vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"  {numFilesWritten} files written to {outputFolder}." )
    return numFilesWritten > 0
# end of ScriptedBibleEditor.executeEditsOnAllFiles


def extractESFMTableNames( filename:str, fileText:str, esfmFilelist:Set[str] ) -> int:
    """
    Checks if the filename and fileText specify an ESFM file.
    If so, looks for ESFM table names, and adds them to the set.
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"extractESFMTableNames( {filename}, {len(fileText)}, {len(esfmFilelist)} )" )

    if filename.endswith( '.ESFM' ):
        assert '\\rem ESFM v' in fileText
        ix = fileText.index( '\\rem ESFM v' ) + 11
        ixEnd = fileText.index( '\n', ix )
        versionAndBookStuff = fileText[ix:ixEnd]
        # print( f"Got '{versionAndBookStuff}'" )
        versionString, BBB = versionAndBookStuff.split( ' ', 1 )
        # print( f"Processing ESFM v{versionString} for {BBB}" )
        assert 0.5 <= float(versionString) <=  1.0
    elif '\\rem ESFM v' in fileText:
        logging.critical( f"Text seems to be ESFM but file extension is not .ESFM" )
        halt
    else:
        return 0 # nothing to do and nothing done

    numAdded = 0
    for tableType in ('WORKDATA','FILEDATA','WORDTABLE'):
        searchString = f'\\rem {tableType} '
        ix = fileText.find( searchString )
        if ix == -1: # Didn't find this table type
            continue
        ix += len(searchString) # We want the bit AFTER what we just found
        ixEnd = fileText.index( '\n', ix )
        filename = fileText[ix:ixEnd]
        esfmFilelist.add( filename )
        numAdded += 1

    return numAdded
# end of ScriptedBibleEditor.extractESFMTableNames


def copyAuxilliaryESFMfiles( inputFolder:Path, outputFolder:Path, esfmFilelist:Set[str] ) -> int:
    """
    Copies the ESFM auxilliary files across to the output folder.

    Returns the number of files copied across
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"copyAuxilliaryESFMfiles( {inputFolder}, {outputFolder}, {len(esfmFilelist)} )" )

    for filename in esfmFilelist:
        inputFilepath = inputFolder.joinpath( filename )
        outputFilepath = outputFolder.joinpath( filename )
        dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"Copying ESFM auxilliary {inputFilepath} to {outputFilepath}…" )
        shutil.copy( inputFilepath, outputFilepath ) # Need to update the file creation time otherwise "make" doesn't function correctly
        # shutil.copy2( inputFilepath, outputFilepath ) # copy2 copies the file attributes
    
    return len(esfmFilelist)
# end of ScriptedBibleEditor.copyAuxilliaryESFMfiles


def executeEdits( BBB:str, inputText:str, commandTables ) -> str:
    """
    Returns a modified string.
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"executeEdits( {len(inputText)} )" )
    appliedText = inputText

    for commandTableName, commands in commandTables.items():
        vPrint( 'Info', DEBUGGING_THIS_MODULE, f"    Applying {commandTableName}…" )
        appliedText = executeEditCommands( BBB, appliedText, commands )

    return appliedText
# end of ScriptedBibleEditor.executeEdits


def executeEditCommands( BBB:str, inputText:str, commands ) -> str:
    """
    Returns the adjusted text with the command(s) applied
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"executeEditCommands( {BBB}, {len(inputText)}, {len(commands)} )" )
    adjustedText = inputText

    for command in commands:
        if BBB in command.iBooks:
            assert BBB not in command.eBooks
        if BBB in command.eBooks:
            assert BBB not in command.iBooks
            vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping excluded '{BBB}' book…" )
            continue

        editFunction = executeRegexEditChunkCommand \
                        if 'w' in command.tags or command.preText or command.postText or '¦' in command.searchText \
                        else executeEditChunkCommand

        if not command.iMarkers and not command.eMarkers and not command.iRefs and not command.eRefs:
            # Then it's easier -- don't care about USFM structure
            adjustedText = editFunction( BBB, adjustedText, command )
        else: # need to parse USFM by line
            dPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"Need to parse USFM by line to apply {command}!" )
            newLines = []
            C, V = '-1', '-1' # So first/id line starts at -1:0
            lineNumber, lastMarker =  0, None
            for line in adjustedText.split( '\n' ):
                lineNumber += 1
                if C == '-1': V = str( int(V) + 1 )
                line = line.rstrip( '\r' )
                if not line:
                    newLines.append( line )
                    continue
                marker, text = splitUSFMMarkerFromText( line )
                if marker == 'c':
                    C, V = text, '0'
                elif marker == 'v':
                    V = text.split(' ')[0]
                effectiveMarker = lastMarker if marker is None else marker
                lastMarker = marker
                if effectiveMarker:
                    if effectiveMarker in command.eMarkers:
                        assert effectiveMarker not in command.iMarkers
                        newLines.append( line )
                        vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping excluded '{effectiveMarker}' marker…" )
                        continue
                    if command.iMarkers and effectiveMarker not in command.iMarkers:
                        newLines.append( line )
                        vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping not included '{effectiveMarker}' marker…" )
                        halt
                        continue
                CVRef, BCVRef = f'{C}:{V}', f'{BBB}_{C}:{V}'
                if CVRef in command.eRefs:
                    assert CVRef not in command.iRefs
                    newLines.append( line )
                    vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping excluded '{CVRef}' reference…" )
                    halt
                    continue
                if BCVRef in command.eRefs:
                    assert BCVRef not in command.iRefs
                    newLines.append( line )
                    vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping excluded '{BCVRef}' reference with '{line}'…" )
                    continue
                if command.iRefs and CVRef not in command.iRefs and BCVRef not in command.iRefs:
                    newLines.append( line )
                    vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    Skipping not included '{BCVRef}' reference…" )
                    continue
                # If we get here, we need to process the USFM field
                newLines.append( editFunction( f'{BCVRef}~{marker}', line, command ) )
            adjustedText = '\n'.join( newLines )

    return adjustedText
# end of ScriptedBibleEditor.executeEditCommands


def splitUSFMMarkerFromText( line:str ) -> Tuple[Optional[str],str]:
    """
    Given a line of text (may be empty),
        returns a backslash marker and the text.

    If the marker is self-closing and without any internal fields, e.g., \\ts\\*
        the closure characters will be included with the marker.

    Returns None for the backslash marker if there isn't one.
    Returns an empty string for the text if there isn't any.
    """
    if not line: return None, ''
    if line[0] != '\\': return None, line # Not a USFM line

    # We have a line that starts with a backslash
    # The marker can end with a space, asterisk, or another marker
    lineAfterLeadingBackslash = line[1:]
    ixSP = lineAfterLeadingBackslash.find( ' ' )
    ixAS = lineAfterLeadingBackslash.find( '*' )
    ixBS = lineAfterLeadingBackslash.find( '\\' )
    if ixSP==-1: ixSP = DUMMY_VALUE
    if ixAS==-1: ixAS = DUMMY_VALUE
    if ixBS==-1: ixBS = DUMMY_VALUE
    ix = min( ixSP, ixAS, ixBS ) # Find the first terminating character (if any)

    if ix == DUMMY_VALUE: # The line is only the marker
        return lineAfterLeadingBackslash, ''
    else:
        if ix == ixBS: # Marker stops before a backslash
            if len(lineAfterLeadingBackslash) > ixBS+1 \
            and lineAfterLeadingBackslash[ixBS+1] == '*': # seems to be a self-closed marker
                marker = lineAfterLeadingBackslash[:ixBS+2]
                text = lineAfterLeadingBackslash[ixBS+2:]
            else: # Seems not self-closed
                marker = lineAfterLeadingBackslash[:ixBS]
                text = lineAfterLeadingBackslash[ixBS:]
        elif ix == ixAS: # Marker stops at an asterisk
            marker = lineAfterLeadingBackslash[:ixAS+1]
            text = lineAfterLeadingBackslash[ixAS+1:]
        elif ix == ixSP: # Marker stops before a space
            marker = lineAfterLeadingBackslash[:ixSP]
            text = lineAfterLeadingBackslash[ixSP+1:] # We drop the space completely
    return marker, text
# end if ScriptedBibleEditor.splitUSFMMarkerFromText


STANDARD_DISTANCE = 2500 # 3JN USFM is about 2,300 chars, LUK is about 175,000 chars, MAT 1 is about 3,500 chars.
def executeEditChunkCommand( where:str, inputText:str, command:EditCommand ) -> str:
    """
    Assumes we're in the right field.

    Loops or delays as necessary.
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"executeEditChunkCommand( {where}, {len(inputText)}, {command} )" )
    assert not command.preText and not command.postText and 'w' not in command.tags
    adjustedText = inputText

    sourceCount = adjustedText.count( command.searchText )
    if sourceCount > 0:
        vPrint( 'Verbose', DEBUGGING_THIS_MODULE,
            f"    About to {'loop ' if command.tags=='l' else ''}replace {sourceCount} instance{'' if sourceCount==1 else 's'} of {command.searchText!r} with {command.replaceText!r} in {where}" )
        if 'd' in command.tags and sourceCount>1 and len(adjustedText) > STANDARD_DISTANCE:
            # 'd' is for distance, and usually used for names
            assert 'l' not in command.tags
            assert '/' in command.replaceText or '\\add ' in command.replaceText, f"Can't use 'd' flag with '{command.replaceText}'"
            shortReplaceText = command.replaceText.split('/')[0] if '/' in command.replaceText \
                else re.sub( '\\\\add .+?\\\\add[*]', '', command.replaceText ) # the /add part could be at the beginning, the end, or in the middle
            dPrint( 'Info', DEBUGGING_THIS_MODULE, f"Have a distanced replace on {where} text ({len(adjustedText):,} chars) with {sourceCount:,} '{command.searchText}' -> '{shortReplaceText}' from '{command.replaceText}'" )
            startIndex = 0
            indexes = []
            while True:
                index = adjustedText.find( command.searchText, startIndex)
                if index == -1: break
                indexes.append( index )
                startIndex = index + len( command.searchText )
            assert len(indexes) == sourceCount
            dPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"  Indexes are {indexes}" )
            dPrint( 'Info', DEBUGGING_THIS_MODULE, f"  Distances are {[indexes[j+1]-indexes[j] for j in range(sourceCount-1)]}" )
            adjustedText = adjustedText.replace( command.searchText, command.replaceText, 1 ) # Replace first instance
            searchLength = len( command.searchText )
            lastFullReplaceIndex = indexes[0]
            numFullReplacesDone, numShortReplacesDone = 1, 0
            offset = len(command.replaceText) - len(command.searchText)
            for jj in range(1, sourceCount):
                index = indexes[jj]
                adjustedIndex = index + offset
                dPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    {jj=} {index=} {offset=} {adjustedIndex=} {numFullReplacesDone=} {numShortReplacesDone=}" )
                assert adjustedText[adjustedIndex:].startswith( command.searchText )
                distance = index - lastFullReplaceIndex
                if distance >= STANDARD_DISTANCE: # then it's time to do another full replace
                    dPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"      Doing FULL replace for '{command.searchText}'" )
                    adjustedText = f'{adjustedText[:adjustedIndex]}{command.replaceText}{adjustedText[adjustedIndex+searchLength:]}'
                    offset += len(command.replaceText) - len(command.searchText)
                    lastFullReplaceIndex = index
                    numFullReplacesDone += 1
                else:
                    dPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"      Doing SHORT replace for '{command.searchText}'" )
                    adjustedText = f'{adjustedText[:adjustedIndex]}{shortReplaceText}{adjustedText[adjustedIndex+searchLength:]}'
                    offset += len(shortReplaceText) - len(command.searchText)
                    numShortReplacesDone += 1
            dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"  Did {numFullReplacesDone:,} full replaces and {numShortReplacesDone:,} short replaces of '{command.searchText}'" )
            assert numFullReplacesDone + numShortReplacesDone == sourceCount
            # if command.searchText=='Jesus': halt
        else: # no 'd' (or text chunk is too short anyway) so we're just normal
            adjustedText = adjustedText.replace( command.searchText, command.replaceText )
            lastCount = adjustedText.count( command.searchText )
            vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"      Replaced {sourceCount-lastCount} instances of '{command.searchText}' with '{command.replaceText}' {where}" )
            if 'l' in command.tags: # for loop -- handles overlapping strings
                while command.searchText in adjustedText: # keep at it
                    adjustedText = adjustedText.replace( command.searchText, command.replaceText )
                    newCount = adjustedText.count( command.searchText )
                    if newCount >= lastCount: # Could be in an endless loop
                        logging.critical( f"ABORTED endless loop replacing '{command.searchText}' with '{command.replaceText}'")
                        break
                    lastCount = newCount
    else:
        vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"    No instances of {command.searchText!r} in {where}!" )

    # if 'd' in command.tags and sourceCount>1 and len(adjustedText) > STANDARD_DISTANCE and command.searchText=='Jesus':
    #     # print(adjustedText)
    #     halt
    return adjustedText
# end of ScriptedBibleEditor.executeEditChunkCommand


def escape_backslash( regex:str ) -> str:
    return regex.replace('\\','\\\\') # Replace single backslash char (as in USFM) with two backslash chars for RegEx


wordLinkRegexString = '¦[1-9][0-9]{0,5}'
wordLinkRegex = re.compile( wordLinkRegexString )
def executeRegexEditChunkCommand( where:str, inputText:str, command:EditCommand ) -> str:
    """
    Assumes we're in the right text field.

    Uses regex to only replace whole words.

    Checks previous and following text as necessary.
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"executeRegexEditChunkCommand( {where}, {len(inputText)}, {command} )" )
    adjustedText = inputText
    
    searchBrokenPipeCount = command.searchText.count( '¦' )
    if searchBrokenPipeCount: # have ESFM wordlink numbers (appended to the end of words)
        myRegexSearchString = command.searchText.replace( '¦', wordLinkRegexString )
        myRegexSearchString = f'({escape_backslash(myRegexSearchString)})'
    else: # relatively straight forward without ESFM wordlink numbers
        myRegexSearchString = f'({escape_backslash(command.searchText)})'
    myRegexReplaceString = f'Rx-{escape_backslash(command.replaceText)}-Rx' if BibleOrgSysGlobals.commandLineArguments.flagReplacements else escape_backslash(command.replaceText)
    if command.preText:
        # myRegexSearchString = f'({command.preText}){myRegexSearchString}'
        # myRegexReplaceString = f'\\1{myRegexReplaceString}'
        myRegexSearchString = f'(?{escape_backslash(command.preText)}){myRegexSearchString}'
        dPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"Have PRE TEXT '{command.preText}' before '{myRegexSearchString}'" )
    elif 'w' in command.tags: # search after a word break -- matches after \b or after _
        myRegexSearchString = f'\\b{myRegexSearchString}|(?<=_){myRegexSearchString}'
    if command.postText:
        # myRegexSearchString = f'{myRegexSearchString}({command.postText})'
        # myRegexReplaceString = f'{myRegexReplaceString}\\3'
        myRegexSearchString = f'{myRegexSearchString}(?{escape_backslash(command.postText)})'
        dPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"Have POST TEXT '{command.postText}' after '{myRegexSearchString}'" )
    elif 'w' in command.tags:
        if '|(?<=_)' in myRegexSearchString:
            bits = myRegexSearchString.split( '|(?<=_)' )
            assert len(bits) == 2
            bits = [f'{bit}\\b' for bit in bits]
            myRegexSearchString = '|(?<=_)'.join(bits)
        else:
            myRegexSearchString = f'{myRegexSearchString}\\b'
    compiledSearchRegex = re.compile( myRegexSearchString )

    if searchBrokenPipeCount: # More work with word link numbers in this case
        # if len(inputText) < 500: print( f"{inputText=}" )
        # print( f"{where=} {myRegexSearchString=}" )
        # if '\\' in myRegexReplaceString:
        # print( f"({len(command.searchText)}) {command.searchText=} ({len(myRegexSearchString)}) {myRegexSearchString=}" )
        # print( f"({len(command.replaceText)}) {command.replaceText=} ({len(myRegexReplaceString)}) {myRegexReplaceString=}" )
        searchStartIndex = numReplacements = 0
        originalMyRegexReplaceString = myRegexReplaceString
        while True:
            match = compiledSearchRegex.search( adjustedText, searchStartIndex )
            if not match:
                break
            # print( f"{searchStartIndex}/{len(adjustedText)} {numReplacements=} {match=}" )
            # print( f"guts='{adjustedText[match.start()-10:match.end()+10]}'" )
            # print( f"({len(match.groups())}) {match.groups()=}" )
            assert len(match.groups()) == 1 \
            or ('w' in command.tags and len(match.groups())==2 and (match.group(2) is None or match.group(1) is None)), \
                f"{len(match.groups())} {match=} {myRegexSearchString=} {match.groups()}"
            wordOrWordsWithNumbers = match.group(1)
            if len(match.groups())==2 and match.group(1) is None:
                assert match.group(2) is not None
                wordOrWordsWithNumbers = match.group(2)
            # foundMatchBeginning, foundMatchEnd = match.group(1).split( '¦', 1 )
            # print( f"{foundMatchBeginning=} {foundMatchEnd=}" )
            # assert foundMatchEnd.isdigit() # Should be the wordlink number FAILS because there might be a suffix, e.g., '˱of¦2˲'
            replaceBrokenPipeCount = myRegexReplaceString.count( '¦' )
            # print( f"{wordOrWordsWithNumbers} '{myRegexReplaceString}' {replaceBrokenPipeCount=}" )
            if replaceBrokenPipeCount:
                if searchBrokenPipeCount==1: # we have one broken pipe char in both search and replace
                    wordLinkMatch = wordLinkRegex.search( wordOrWordsWithNumbers )
                    wordLinkNumberStr = wordLinkMatch.group(0)[1:] # After the broken pipe character
                    # print( f"{wordLinkNumber=}" )
                    assert wordLinkNumberStr.isdigit()
                    myRegexReplaceString = originalMyRegexReplaceString.replace( '¦', f'¦{wordLinkNumberStr}' ) \
                                                                       .replace( '\\\\', '\\' ) # Because we're NOT actually using a RegEx replace here
                else: # have 2 or more broken pipes in search (and at least one in replace)
                    # print( f"SBE: {wordOrWordsWithNumbers} '{myRegexReplaceString}' {replaceBrokenPipeCount=}" )
                    # These words could have different wordlink numbers or all be the same wordLink Number
                    wordLinkNumberStringsList, wordLinkNumberStringsSet = [], set()
                    for wordLinkMatch in wordLinkRegex.finditer( wordOrWordsWithNumbers ):
                        wordLinkNumberStr = wordLinkMatch.group(0)[1:] # After the broken pipe character
                        # print( f"{wordLinkNumber=}" )
                        assert wordLinkNumberStr.isdigit()
                        wordLinkNumberStringsList.append( wordLinkNumberStr )
                        wordLinkNumberStringsSet.add( wordLinkNumberStr )
                    orderedWordLinkNumberStringsSet = sorted( wordLinkNumberStringsSet )
                    # print( f"SBE: Found {len(wordLinkNumberStrings)} wordlink number: {wordLinkNumberStrings}")
                    if len(wordLinkNumberStringsSet) == 1:
                        myRegexReplaceString = originalMyRegexReplaceString.replace( '¦', f'¦{wordLinkNumberStringsSet.pop()}' ) \
                                                                           .replace( '\\\\', '\\' ) # Because we're NOT actually using a RegEx replace here
                        # print( f"{myRegexReplaceString=}" )
                    else: # more than one word number in the found set
                        # Individually do the word number replacements for each word in the found string
                        # Note that this code cannot REORDER words
                        dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"      {myRegexSearchString=} {originalMyRegexReplaceString=} {wordLinkNumberStringsSet=} {wordLinkNumberStringsList=} {orderedWordLinkNumberStringsSet=} {wordOrWordsWithNumbers=} {where}" )
                        searchWords = myRegexSearchString.split( ' ' )
                        replaceWords = originalMyRegexReplaceString.split( ' ' )
                        foundWords = wordOrWordsWithNumbers.split( ' ' )
                        numWords = len(searchWords)
                        assert numWords >= 2 # More than one word
                        assert numWords == len(replaceWords) == len(foundWords) == len(orderedWordLinkNumberStringsSet) # Same number of words
                        replacedWords = []
                        for searchWord,replaceWord,foundWord, wordNumber in zip( searchWords, replaceWords, foundWords, orderedWordLinkNumberStringsSet, strict=True ):
                            # Do each individual find/replace
                            dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"{searchWord=} {foundWord=} {replaceWord=} {wordNumber=}")
                            assert wordNumber in foundWord
                            assert '¦' in foundWord
                            assert '¦' in replaceWord
                            replacedWord = replaceWord.replace( '¦', f'¦{wordNumber}' )
                            replacedWords.append( replacedWord )
                        # dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"{replacedWords=}" )
                        myRegexReplaceString = ' '.join(replacedWords)
                        dPrint( 'Normal', DEBUGGING_THIS_MODULE, f"{replacedWords=} {myRegexReplaceString=} {where}" )

            else: # replaceBrokenPipeCount == 0
                # That means that we have to remove the digits
                not_written_for_removing_word_number_yet
            adjustedText = f'{adjustedText[:match.start()]}{myRegexReplaceString}{adjustedText[match.end():]}'
            numReplacements += 1
            # if numReplacements > 3: halt
            searchStartIndex = match.start() + len(myRegexReplaceString)
            # if len(adjustedText) < 500: print( f"{adjustedText=}" )
            # elif searchStartIndex < 500: print( f"{adjustedText[:searchStartIndex]=}" )
    else: # searchBrokenPipeCount == 0
        assert '¦' not in myRegexReplaceString
        while True:
            adjustedText, numReplacements = compiledSearchRegex.subn( myRegexReplaceString, adjustedText )
            if numReplacements:
                # dPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"      Replaced {numReplacements} whole word instances of '{command.searchText}' ({myRegexSearchString}) with '{command.replaceText}' ({myRegexReplaceString}) {where}" )
                vPrint( 'Verbose', DEBUGGING_THIS_MODULE, f"      Replaced {numReplacements} whole word instances of '{command.searchText}' with '{command.replaceText}' {where}" )
            if numReplacements==0 or 'l' not in command.tags: break

    return adjustedText
# end of ScriptedBibleEditor.executeRegexEditChunkCommand



if __name__ == '__main__':
    # from multiprocessing import freeze_support
    # freeze_support() # Multiprocessing support for frozen Windows executables

    # Configure basic Bible Organisational System (BOS) set-up
    parser = BibleOrgSysGlobals.setup( SHORT_PROGRAM_NAME, PROGRAM_VERSION, LAST_MODIFIED_DATE )
    parser.add_argument('controlPath', help="path of ScriptedBibleEditor.control.toml")
    parser.add_argument('-f', '--flag', action='store_true', dest='flagReplacements', default=False, help="flag where replacements were made")
    BibleOrgSysGlobals.addStandardOptionsAndProcess( parser )

    main()

    BibleOrgSysGlobals.closedown( PROGRAM_NAME, PROGRAM_VERSION )
# end of ScriptedBibleEditor.py
