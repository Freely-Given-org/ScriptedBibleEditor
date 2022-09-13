#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# extractYLT.py
#
# Module handling extractYLT functions
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
Module handling extractYLT functions.

"""
from gettext import gettext as _
from typing import Dict, List, Tuple
from pathlib import Path
from csv import DictReader
from collections import defaultdict
from datetime import datetime
import os
import logging

import BibleOrgSysGlobals
from BibleOrgSysGlobals import fnPrint, vPrint, dPrint


LAST_MODIFIED_DATE = '2022-09-01' # by RJH
SHORT_PROGRAM_NAME = "extractYLT"
PROGRAM_NAME = "Extract YLT USFM files"
PROGRAM_VERSION = '1.02'
PROGRAM_NAME_VERSION = f'{SHORT_PROGRAM_NAME} v{PROGRAM_VERSION}'

DEBUGGING_THIS_MODULE = True


YLT_INPUT_FILENAME = 'ylt.txt'
YLT_INPUT_FILEPATH = Path(f'/mnt/SSDs/Bibles/English translations/YLT/{YLT_INPUT_FILENAME}')
YLT_USFM_OUTPUT_FOLDERPATH = Path( '../TestFiles/source_YLT_USFM/' )
# USFM_OUTPUT_FILENAME_TEMPLATE = 'BBB_YLT.usfm' # Use BOS book codes
USFM_OUTPUT_FILENAME_TEMPLATE = 'UUU_YLT.usfm' # Use USFM book codes


BOOK_NAME_MAP = {
    1: 'Genesis', 2: 'Exodus', 3: 'Leviticus', 4: 'Numbers', 5: 'Deuteronomy',
    6: 'Joshua', 7: 'Judges', 8: 'Ruth', 9: '1 Samuel', 10: '2 Samuel',
    11: '1 Kings', 12: '2 Kings', 13: '1 Chronicles',  14: '2 Chronicles', 15: 'Ezra', 16: 'Nehemiah', 17: 'Esther', 18: 'Job',
    19: 'Psalm', 20: 'Proverbs', 21: 'Ecclesiastes',  22: 'Song', 23: 'Isaiah', 24: 'Jeremiah', 25: 'Lamentations',
    26: 'Ezekiel', 27: 'Daniel', 28: 'Hosea',  29: 'Joel', 30: 'Amos', 31: 'Obadiah',
    32: 'Jonah', 33: 'Micah', 34: 'Nahum',  35: 'Habakkuk', 36: 'Zephaniah', 37: 'Haggai', 38: 'Zechariah', 39: 'Malachi',
    40: 'Matthew',    41: 'Mark',    42: 'Luke',    43: 'John',    44: 'Acts',
    45: 'Romans',    46: '1 Corinthians',    47: '2 Corinthians',    48: 'Galatians',    49: 'Ephesians',    50: 'Philippians',    51: 'Colossians',
    52: '1 Thessalonians',    53: '2 Thessalonians',    54: '1 Timothy',    55: '2 Timothy',    56: 'Titus',    57: 'Philemon',
    58: 'Hebrews',
    59: 'James',    60: '1 Peter',    61: '2 Peter',    62: '1 John',    63: '2 John',    64: '3 John',    65: 'Jude',
    66: 'Revelation',
}
assert len(BOOK_NAME_MAP) == 66
USFM_BOOK_ID_MAP = {
            1: 'GEN', 2: 'EXO', 3: 'LEV', 4: 'NUM', 5: 'DEU',
            6: 'JOS', 7: 'JDG', 8: 'RUT', 9: '1SA', 10: '2SA',
            11: '1KI', 12: '2KI', 13: '1CH', 14: '2CH', 15: 'EZR', 16: 'NEH', 17: 'EST', 18: 'JOB',
            19: 'PSA', 20: 'PRO', 21: 'ECC', 22: 'SNG', 23: 'ISA', 24: 'JER', 25: 'LAM',
            26: 'EZK', 27: 'DAN', 28: 'HOS', 29: 'JOL', 30: 'AMO', 31: 'OBA',
            32: 'JON', 33: 'MIC', 34: 'NAM', 35: 'HAB', 36: 'ZEP', 37: 'HAG', 38: 'ZEC', 39: 'MAL',
            40: 'MAT', 41: 'MRK', 42: 'LUK', 43: 'JHN', 44: 'ACT',
            45: 'ROM', 46: '1CO', 47: '2CO', 48: 'GAL', 49: 'EPH', 50: 'PHP', 51: 'COL', 52: '1TH', 53: '2TH', 54: '1TI', 55: '2TI', 56: 'TIT', 57: 'PHM',
            58: 'HEB', 59: 'JAS', 60: '1PE', 61: '2PE', 62: '1JN', 63: '2JN', 64: '3JN', 65: 'JUD', 66: 'REV'}
assert len(USFM_BOOK_ID_MAP) == 66
BOS_BOOK_ID_MAP = {
            1: 'GEN', 2: 'EXO', 3: 'LEV', 4: 'NUM', 5: 'DEU',
            6: 'JOS', 7: 'JDG', 8: 'RUT', 9: 'SA1', 10: 'SA2',
            11: 'KI1', 12: 'KI2', 13: 'CH1', 14: 'CH2', 15: 'EZR', 16: 'NEH', 17: 'EST', 18: 'JOB',
            19: 'PSA', 20: 'PRO', 21: 'ECC', 22: 'SNG', 23: 'ISA', 24: 'JER', 25: 'LAM',
            26: 'EZK', 27: 'DAN', 28: 'HOS', 29: 'JOL', 30: 'AMO', 31: 'OBA',
            32: 'JNA', 33: 'MIC', 34: 'NAH', 35: 'HAB', 36: 'ZEP', 37: 'HAG', 38: 'ZEC', 39: 'MAL',
            40: 'MAT', 41: 'MRK', 42: 'LUK', 43: 'JHN', 44: 'ACT',
            45: 'ROM', 46: 'CO1', 47: 'CO2', 48: 'GAL', 49: 'EPH', 50: 'PHP', 51: 'COL', 52: 'TH1', 53: 'TH2', 54: 'TI1', 55: 'TI2', 56: 'TIT', 57: 'PHM',
            58: 'HEB', 59: 'JAM', 60: 'PE1', 61: 'PE2', 62: 'JN1', 63: 'JN2', 64: 'JN3', 65: 'JDE', 66: 'REV'}
assert len(BOS_BOOK_ID_MAP) == 66
NEWLINE = '\n'



def main() -> None:
    """
    """
    BibleOrgSysGlobals.introduceProgram( __name__, PROGRAM_NAME_VERSION, LAST_MODIFIED_DATE )

    if load_YLT_data():
        export_usfm()
# end of extractYLT.main


YLT_verse_dict = {}
def load_YLT_data() -> bool:
    """
    This is quite quick.
    """
    print(f"\nFinding YLT TSV file starting at {YLT_INPUT_FILEPATH}…")
    try_filepath = YLT_INPUT_FILEPATH
    while not os.access(try_filepath, os.R_OK):
        if try_filepath == YLT_INPUT_FILEPATH: try_filepath = YLT_INPUT_FILENAME
        else: try_filepath = f'../{try_filepath}'
        if try_filepath.startswith('../'*4): break
        print(f"  Trying to find YLT TSV file at {try_filepath}…")
    print(f"  Loading YLT TSV file from {try_filepath}…")
    with open(try_filepath, 'rt', encoding='utf-8') as text_file:
        for line in text_file:
            line = line.rstrip('\n')
            if line.startswith( 'Verse' ): continue # Skip first header line
            # line = line.replace(' ', '_', 1) # Reduce three columns to two
            bits = line.split('\t')
            assert len(bits) == 2
            YLT_verse_dict[bits[0]] = bits[1]
    # print(len(YLT_verse_dict), type(YLT_verse_dict), YLT_verse_dict.keys())
    print(f"    {len(YLT_verse_dict):,} verses loaded from YLT TSV.")
    return True


def export_usfm() -> bool:
    """
    Use the GlossOrder field to export the English gloss.

    Also uses the GlossInsert field to adjust word order.
    """
    print("\nExporting USFM plain text YLT files…")

    numFilesWritten = 0
    last_bookNumber = last_chapterNumber = 0
    usfm_text = ''
    for ref,verseText in YLT_verse_dict.items():
        bookNameBits = ref.split( ' ' )
        bookName = bookNameBits[0]
        if bookName.isdigit(): # like 2 John
            bookName = f'{bookNameBits[0]} {bookNameBits[1]}'
        # if bookNameBits[-1] == '1:1': print(bookName)

        for bookNumber,name in BOOK_NAME_MAP.items():
            if name == bookName: break
        else: logging.critical( f"Can't find '{bookName}' in our list!" )

        # print(f"{bookNameBits[-1]=}")
        chapterNumber, verseNumber = bookNameBits[-1].split( ':' )

        if bookNumber != last_bookNumber:
            # print(f"{bookNumber=} {last_bookNumber=}")
            assert bookNumber == last_bookNumber + 1

            if usfm_text:
                # assert '  ' not in usfm_text
                usfm_filepath = YLT_USFM_OUTPUT_FOLDERPATH.joinpath( USFM_OUTPUT_FILENAME_TEMPLATE
                                .replace( 'BBB', BOS_BOOK_ID_MAP[last_bookNumber] )
                                .replace( 'UUU', USFM_BOOK_ID_MAP[last_bookNumber] )
                                )
                with open(usfm_filepath, 'wt', encoding='utf-8') as output_file:
                    output_file.write(f"{usfm_text}\n")
                numFilesWritten += 1
            last_bookNumber = bookNumber

            # Now we are starting a new book
            USFM_book_code = USFM_BOOK_ID_MAP[bookNumber]
            BBB = BOS_BOOK_ID_MAP[bookNumber]
            last_chapterNumber = None

            usfm_text = f"""\\id {USFM_book_code}
\\usfm 3.0
\\ide UTF-8
\\rem USFM file created {datetime.now().strftime('%Y-%m-%d %H:%M')} by {PROGRAM_NAME_VERSION}
\\rem Robert Young's Literal Translation (1862) is now in the public domain
\\h {bookName}
\\toc1 {bookName}
\\toc2 {bookName}
\\toc3 {bookName}
\\mt1 {bookName}"""

        if chapterNumber != last_chapterNumber:
            usfm_text = f'{usfm_text}\n\\c {chapterNumber}'
            last_chapterNumber = chapterNumber

        usfm_text = f'{usfm_text}\n\\v {verseNumber} {verseText}'

    if usfm_text: # write the last book
        # assert '  ' not in usfm_text
        usfm_filepath = YLT_USFM_OUTPUT_FOLDERPATH.joinpath( USFM_OUTPUT_FILENAME_TEMPLATE
                                .replace( 'BBB', BOS_BOOK_ID_MAP[last_bookNumber] )
                                .replace( 'UUU', USFM_BOOK_ID_MAP[last_bookNumber] )
                                )
        with open(usfm_filepath, 'wt', encoding='utf-8') as output_file:
            output_file.write(f"{usfm_text}\n")
        numFilesWritten += 1

    vPrint( 'Quiet', DEBUGGING_THIS_MODULE, f"  Wrote {numFilesWritten} files to {YLT_USFM_OUTPUT_FOLDERPATH}.\n")
    return True
# end of extractYLT.export_usfm


if __name__ == '__main__':
    # from multiprocessing import freeze_support
    # freeze_support() # Multiprocessing support for frozen Windows executables

    # Configure basic Bible Organisational System (BOS) set-up
    parser = BibleOrgSysGlobals.setup( SHORT_PROGRAM_NAME, PROGRAM_VERSION, LAST_MODIFIED_DATE )
    BibleOrgSysGlobals.addStandardOptionsAndProcess( parser )

    main()

    BibleOrgSysGlobals.closedown( PROGRAM_NAME, PROGRAM_VERSION )
# end of extractYLT.py
