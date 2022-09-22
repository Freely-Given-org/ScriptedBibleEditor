#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# ScriptedBibleEditor.py
#
# Module handling ScriptedBibleEditor functions
#
# Copyright (C) 2022 Robert Hunt
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
"""
from gettext import gettext as _
from typing import Dict, List, NamedTuple, Tuple, Optional
from pathlib import Path
import os
import shutil
import toml
import logging
from datetime import datetime
import re
import unicodedata

import BibleOrgSysGlobals
from BibleOrgSysGlobals import fnPrint, vPrint, dPrint

import sys
sys.path.insert( 0, '../../BibleTransliterations/Python/' ) # temp until submitted to PyPI
from BibleTransliterations import load_transliteration_table, transliterate_Hebrew, transliterate_Greek


LAST_MODIFIED_DATE = '2022-09-21' # by RJH
SHORT_PROGRAM_NAME = "ScriptedBibleEditor"
PROGRAM_NAME = "Scripted Bible Editor"
PROGRAM_VERSION = '0.14'
PROGRAM_NAME_VERSION = f'{SHORT_PROGRAM_NAME} v{PROGRAM_VERSION}'

DEBUGGING_THIS_MODULE = False
LEAVE_REPLACEMENT_INDICATORS = True # Leaves indicators in the output to show where replacements were done


# TODO: Need to allow parameters to be specified on the command line
# Choose one of the following
# ADDITIONAL_SEARCH_PATH = '../ExampleCommands/ModerniseYLT/'
ADDITIONAL_SEARCH_PATH = '../ExampleCommands/UpdateVLT/'


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
    if LEAVE_REPLACEMENT_INDICATORS:
        vPrint( 'Quiet', DEBUGGING_THIS_MODULE, "LEAVE_REPLACEMENT_INDICATORS flag is enabled! (Maybe affect consecutive replacements)" )

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
        if ADDITIONAL_SEARCH_PATH: # May not even be defined
            searchPaths.append( f'{ADDITIONAL_SEARCH_PATH}{DEFAULT_CONTROL_FILE_NAME}')
    except ValueError:
        pass

    for filepath in searchPaths:
        if os.path.isfile(filepath):
            return filepath

    vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"No control file found in {searchPaths}." )
# end of ScriptedBibleEditor.findControlFile


def loadControlFile( filepath ) -> bool:
    """
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"loadControlFile( {filepath} )")

    state.controlFolderpath = os.path.dirname( filepath )
    vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"Loading control file: {filepath}…" )
    with open(filepath, 'rt', encoding='utf=8') as controlFile:
        state.controlData = toml.load( controlFile )
        displayTitle = f"'{state.controlData['title']}'" \
                        if 'title' in state.controlData and state.controlData['title'] \
                        else "control file"
        vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"  Loaded {len(state.controlData)} parameter{'' if len(state.controlData)== 1 else 's'} from {displayTitle}." )
        return len(state.controlData) > 0
    return False
# end of ScriptedBibleEditor.loadControlFile


def loadCommandTables() -> bool:
    """
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
                        fields = line.split( '\t' )
                        tags, searchText, replaceText = fields[0], fields[9], fields[12]
                        if 'H' in tags:
                            newReplaceText = transliterate_Hebrew( replaceText, searchText[0].isupper() )
                            if newReplaceText != replaceText:
                                # print(f" Converted Hebrew '{replaceText}' to '{newReplaceText}'")
                                replaceText = f'H‹{newReplaceText}›H' if LEAVE_REPLACEMENT_INDICATORS else newReplaceText
                            for char in replaceText:
                                if 'HEBREW' in unicodedata.name(char):
                                    logging.critical(f"Have some Hebrew left-overs in '{replaceText}'")
                                    break
                        if 'G' in tags:
                            newReplaceText = transliterate_Greek( replaceText )
                            if newReplaceText != replaceText:
                                # print(f" Converted Greek '{replaceText}' to '{newReplaceText}'")
                                replaceText = f'G‹{newReplaceText}›G' if LEAVE_REPLACEMENT_INDICATORS else newReplaceText
                            for char in replaceText:
                                if 'GREEK' in unicodedata.name(char):
                                    logging.critical(f"Have some Greek left-overs in '{replaceText}'")
                                    break
                        state.commandTables[name].append( EditCommand( tags,
                                list(fields[1].split(',')) if fields[1] else [], list(fields[2].split(',')) if fields[2] else [],
                                list(fields[3].split(',')) if fields[3] else [], list(fields[4].split(',')) if fields[4] else [],
                                list(fields[5].split(',')) if fields[5] else [], list(fields[6].split(',')) if fields[6] else [],
                                fields[7], fields[8], searchText, fields[10], fields[11],
                                f'R‹{replaceText}›R' if LEAVE_REPLACEMENT_INDICATORS and BibleOrgSysGlobals.verbosityLevel>2 else replaceText, fields[13], fields[14] ) )
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

    if applyOrder == 'AllTablesFirst':
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
                appliedText = executeEdits( BBB, inputText, state.commandTables )
                if appliedText != inputText: # Make a backup before overwriting the input file
                    appliedText = appliedText.replace( '\n\\h ', f"\n\\rem USFM file edited {datetime.now().strftime('%Y-%m-%d %H:%M')} by {PROGRAM_NAME_VERSION}\n\\h " )
                    outputFilepath = os.path.join( outputFolder, outputFilename )
                    if outputFilepath == inputFilename:
                        BibleOrgSysGlobals.backupAnyExistingFile( inputFilename, numBackups=3 )
                    vPrint( 'Normal', DEBUGGING_THIS_MODULE, f"    Writing {len(appliedText):,} characters (was {len(inputText):,}) to {outputFilename}…" )
                    with open( outputFilepath, 'wt', encoding='utf-8' ) as outputFile:
                        outputFile.write(appliedText)
                # break # while debugging first file
    else:
        other_orders_not_implemented_yet

    return False
# end of ScriptedBibleEditor.executeEditsOnAllFiles


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

        editFunction = executeRegexEditChunkCommand if 'w' in command.tags or command.preText or command.postText \
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
                    halt
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


def executeRegexEditChunkCommand( where:str, inputText:str, command:EditCommand ) -> str:
    """
    Assumes we're in the right text field.

    Uses regex to only replace whole words.

    Checks previous and following text as necessary.
    """
    fnPrint( DEBUGGING_THIS_MODULE, f"executeRegexEditChunkCommand( {where}, {len(inputText)}, {command} )" )
    adjustedText = inputText

    myRegexSearchString = f'({command.searchText})'
    myRegexReplaceString = f'Rx-{command.replaceText}-Rx' if LEAVE_REPLACEMENT_INDICATORS else command.replaceText
    if command.preText:
        # myRegexSearchString = f'({command.preText}){myRegexSearchString}'
        # myRegexReplaceString = f'\\1{myRegexReplaceString}'
        myRegexSearchString = f'(?{command.preText}){myRegexSearchString}'
        dPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"Have PRE TEXT '{command.preText}' before '{myRegexSearchString}'" )
    elif 'w' in command.tags: # search after a word break -- matches after \b or after _
        myRegexSearchString = f'\\b{myRegexSearchString}|(?<=_){myRegexSearchString}'
    if command.postText:
        # myRegexSearchString = f'{myRegexSearchString}({command.postText})'
        # myRegexReplaceString = f'{myRegexReplaceString}\\3'
        myRegexSearchString = f'{myRegexSearchString}(?{command.postText})'
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
    BibleOrgSysGlobals.addStandardOptionsAndProcess( parser )

    main()

    BibleOrgSysGlobals.closedown( PROGRAM_NAME, PROGRAM_VERSION )
# end of ScriptedBibleEditor.py
