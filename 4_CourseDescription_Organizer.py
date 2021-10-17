""" Organizer and categorizer for course description properties.

This script takes the raw text from the course descriptions and then segments and categorizes that text into groups,
such as course code, credits, title, prerequisite info, corequisites, registration info, departmental/gen. ed. groups,
grading basis, course fees, terms offered, etc. Note that there is also a group called "course description" which is the
free text description of the course (not to be confused with the collection of data as a whole which is also called
the course description).

The program takes the html elements generated in script 2 of this series and outputs a dataframe containing all the
relevant course info (one course per row).

3rd party modules needed include pandas and tabulate.
"""

import re
import pandas as pd
from verticalprinter import v
from listtopattern import listtopatternraw
from tabulate import tabulate
from random import sample
import warnings
warnings.filterwarnings("ignore", 'This pattern has match groups')

# Header keywords/phrases
creditsID = ['.*Credits?:']
descriptionsID = ['Course Description:']
requisitesID = ['Requisites?:']
prerequisitesID = ['Pre-?(req(uisite)?)?s?:']
corequisitesID = ['Co-?req(uisite)?s?:']
equivalentsID = ['Equivalent - Duplicate Degree Credit Not Granted:', 'Also Offered As:', 'Same as:',
                 r'Equivalent Course\(?s?\)?:', 'Equivalent with:?']
coursegroupsID = ['Additional Information:', 'Attributes:', 'Essential Learning Categories:']
gradingtypeID = ['Grading Basis:', 'Grade Modes?:', 'Grading Scheme:']
recommendedsID = ['Recommended:']
repeatablityID = [r'Repeatable(\.|:)', r'Course may be taken (?=multiple|\d)']
restrictionsID = ['Restrictions?:']
registrationinfoID = ['Registration Information:', 'Note:']
termofferedID = ['(Terms? )?(Typically )?Offered:']
coursefeesID = ['((Special )?Course )?Fees?:']
GTpathwaysID = ['Colorado Guaranteed Transfer']
ID_list = [descriptionsID, requisitesID, prerequisitesID, corequisitesID, equivalentsID, coursegroupsID, gradingtypeID,
           recommendedsID, repeatablityID, restrictionsID, registrationinfoID, termofferedID, coursefeesID,
           GTpathwaysID]
ID_names = ['description', 'requisites', 'prerequisites', 'corequisites', 'equivalents', 'coursegroups', 'gradingtype',
            'recommendeds', 'repeatablity', 'restrictions', 'registrationinfo', 'termoffered', 'coursefees',
            'GTpathways']

# Regex patterns
coursecode_pattern = r'([A-Z][A-Z]?[A-Z]?[A-Z]?[A-Z]?[A-Z]?[A-Z]?[A-Z]?)[- ]?([0-9][0-9]?[0-9]?[0-9]?[A-Z]?[A-Z]?[A-Z]?)'
ccredits_parenthesis_pattern = r'(?:\()([0-9][0-9]?\.?[0-9]? ?-? ?[0-9]?[0-9]?\.?[0-9]?)(?:\))'
ccredits_colon_pattern = r'(?:credits?|units?|hours?):? ?(?:var|varies|variable)? ?\[?([0-9][0-9]?\.?[0-9]? ?-? ?[0-9]?[0-9]?\.?[0-9]?)\]?'
ccredits_nocolon_pattern = r'(?:var|varies|variable)? ?\[?([0-9][0-9]?\.?[0-9]? ?-? ?[0-9]?[0-9]?\.?[0-9]?)\]? (?:credits?|units?|(?:semester )?h(?:ou)?rs?)'
ID_pattern = r'\A([^(/.|:)]+:)'

# Open dataframe from script 2
blocksdf = pd.read_pickle('coursedescriptions.pkl')
coursesdf = pd.DataFrame(columns=['dept', 'number', 'credits', 'title', 'description'])

# Split up any lines that have \n    Todo: Accomplish this in script 2 instead
blocksdf.plaintext = blocksdf.plaintext.apply(lambda x: x.split('\n'))
blocksdf = blocksdf.explode('plaintext')

# Reset block index
blocksdf.blockindex = blocksdf.blockid.groupby(blocksdf.index).transform(lambda x: range(len(x)))

# First line of course description usually contains coursecode, title and credits
firstlines = blocksdf.groupby([blocksdf.index]).first().plaintext.reset_index(drop=True)

# Extract course codes (make sure 98% of firstlines contain course codes)
if sum(firstlines.str.match(coursecode_pattern)) > .98*len(firstlines):
    blocksdf = blocksdf.loc[firstlines.str.match(coursecode_pattern)]
    firstlines = firstlines.loc[firstlines.str.match(coursecode_pattern)]
    coursesdf['dept'] = firstlines.str.extract(coursecode_pattern).loc[:, 0]
    coursesdf['number'] = firstlines.str.extract(coursecode_pattern).loc[:, 1]
    firstlines = firstlines.str.replace(coursecode_pattern, '', regex=True, n=1).str.strip(' .')
else:
    raise Exception('the coursecode is not the first item on the firstlines')

# Extract credits (ensure 80% of firstlines contain credits)        Todo: Clean up and generalize
if sum(firstlines.str.contains(ccredits_colon_pattern, flags=re.IGNORECASE, regex=True)) > .8*len(firstlines):
    coursesdf['credits'] = firstlines.str.extract(ccredits_colon_pattern, flags=re.IGNORECASE)
    firstlines = firstlines.str.replace(ccredits_colon_pattern, '', regex=True, flags=re.IGNORECASE, n=1)
elif sum(firstlines.str.contains(ccredits_nocolon_pattern, flags=re.IGNORECASE, regex=True)) > .8*len(firstlines):
    coursesdf['credits'] = firstlines.str.extract(ccredits_nocolon_pattern, flags=re.IGNORECASE)
    firstlines = firstlines.str.replace(ccredits_nocolon_pattern, '', regex=True, flags=re.IGNORECASE, n=1)
elif sum(firstlines.str.contains(ccredits_parenthesis_pattern)) > .8:
    coursesdf['credits'] = firstlines.str.extract(ccredits_parenthesis_pattern)
    firstlines = firstlines.str.replace(ccredits_parenthesis_pattern, '', regex=True, n=1)
else:
    matchinglines = blocksdf.loc[blocksdf.plaintext.str.match(listtopatternraw(creditsID), flags=re.IGNORECASE),
                                 'plaintext']
    if sum(matchinglines.notna()) < .8*len(firstlines):
        raise Exception('cant find the credits on firstline')
    coursesdf['credits'] = matchinglines.str.replace(listtopatternraw(creditsID), '', regex=True, flags=re.IGNORECASE)
    blocksdf = blocksdf.loc[~blocksdf.plaintext.str.match(listtopatternraw(creditsID), flags=re.IGNORECASE)]

coursesdf.credits = coursesdf.credits.str.strip(' .')
firstlines = firstlines.str.strip(' .')

# If all the courses have something else at the end in parentheses, assume it's irrelevant (like a breakdown of credits)
if firstlines.str.contains(r'\)\Z').all():
    firstlines = firstlines.str.replace(r'\([^()]*?\)\Z', '', regex=True)

# If a small percentage of the remaining firstlines contain parenthesis and colons, then assume it's the course title
has_parentheses = firstlines.str.contains(r'\(')
has_colon = firstlines.str.contains(r':')
if (has_parentheses.sum() < .1*len(firstlines)) & (has_colon.sum() < .3*len(firstlines)):
    coursesdf['title'] = firstlines
else:
    print(list(set(firstlines.str.extract(r'(\([^()]*\))', expand=False).to_list())))
    print('Can we delete these parentheses? (y/n)')         # Print all parentheses items to verify
    if input() == 'y':
        firstlines.str.replace(r'(\([^()]*\))', '', regex=True)
    else:
        raise Exception('terminated by user')

blocksdf = blocksdf.loc[blocksdf.blockindex != 0]

# Extract all the other info
if blocksdf.iloc[-1].name + 1 == len(blocksdf):         # If there is only 1 block per course, everything is in it
    for i, ID in enumerate(ID_list):    # Look for matches in the middle of the paragraph Todo: Apply this in all cases
        middle_pattern = listtopatternraw(ID) + r'([^\n]*?)(\.(?![A-Za-z0-9])|\n|\Z)'
        matchingstring = blocksdf.plaintext.str.extract(middle_pattern, flags=re.IGNORECASE).iloc[:, 2].str.strip(' .')
        coursesdf[ID_names[i]] = matchingstring
        blocksdf.plaintext = blocksdf.plaintext.str.replace(middle_pattern, '', regex=True, flags=re.IGNORECASE)
else:
    for i, ID in enumerate(ID_list):            # Look for matches at the start of each line
        matchinglines = blocksdf.loc[blocksdf.plaintext.str.match(listtopatternraw(ID), flags=re.IGNORECASE),
                                     'plaintext']
        # Fix duplicated entries (e.g. two lines that say 'Prerequisites:' but one is blank)
        lengthsdf = pd.concat([matchinglines, matchinglines.apply(len)], axis=1)
        lengthsdf.columns = ['lines', 'length']
        if not lengthsdf.empty:     # Keep entry with longest string length  Todo: Ensure deleted is redundant or blank
            matchinglines = lengthsdf.groupby(lengthsdf.index).apply(lambda x: x.lines.iloc[x.length.argmax()])
        coursesdf[ID_names[i]] = matchinglines.str.replace(listtopatternraw(ID), '', regex=True,
                                                           flags=re.IGNORECASE).str.strip(' .')
        blocksdf = blocksdf.loc[~blocksdf.plaintext.str.match(listtopatternraw(ID), flags=re.IGNORECASE)]

# Locate the plaintext description
if coursesdf.description.isna().all():    # If descriptions is empty it must be in the remaining block
    # Assume course description is the first block; unparsed is after
    unparsed = blocksdf.groupby(blocksdf.index).apply(lambda x: x[1:] if len(x) != 1 else None)
    coursesdf['description'] = blocksdf.plaintext.groupby(blocksdf.index).apply(lambda x: x.iloc[0])
else:
    unparsed = blocksdf

if not unparsed.empty:
    # Verify first lines of remaining blocks are just plain text descriptions
    kvalue = min(400, len(blocksdf.index.to_list()))
    v(blocksdf.plaintext.groupby(blocksdf.index).first()[sorted(sample(blocksdf.index.to_list(), k=kvalue))])
    print('Do all these look like just descriptions? (y/n)')
    if input() != 'y':
        raise Exception('Terminated by user')

    # Verify remaining blocks can be merged with plain text description
    v(sorted(unparsed.plaintext.unique()))
    print('Move these unparsed items to the description? (y/n)')
    if input() == 'y':
        hasextras = blocksdf.groupby(blocksdf.index).apply(any)
        extrasjoined = blocksdf.plaintext.groupby(blocksdf.index).agg(lambda x: '. '.join(x))
        coursesdf.loc[hasextras.index, 'description'] = coursesdf.description + '. ' + extrasjoined
    else:
        raise Exception('Terminated by user')

# If prereqs, coreqs and requisites are all blank, look in the plain text description   Todo: Do this earlier in script
if coursesdf.requisites.isna().all() & coursesdf.prerequisites.isna().all():
    coursesdf.prerequisites = coursesdf.description.str.extract('Prerequisites?: ([^.]+)', expand=False)
    coursesdf.description = coursesdf.description.str.replace('Prerequisites?: ([^.]+)', '', regex=True)
    coursesdf.corequisites = coursesdf.description.str.extract('Corequisites?: ([^.]+)', expand=False)
    coursesdf.description = coursesdf.description.str.replace('Corequisites?: ([^.]+)', '', regex=True)
    if coursesdf.requisites.isna().all() & coursesdf.prerequisites.isna().all():
        raise Exception('Could not locate course requisites')

# Verify remaining instances of ID keywords/phrases are irrelevant
potentialIDs = blocksdf.plaintext.str.extract(ID_pattern).loc[:, 0].dropna().reset_index(drop=True)
if potentialIDs.groupby(potentialIDs).count().max() > .005*len(coursesdf):
    v(potentialIDs.groupby(potentialIDs).count().sort_values().tail(50))
    print('Ignore these? (y/n)')
    if input() != 'y':
        raise Exception('Terminated by user')

# Clean up
coursesdf = coursesdf.fillna('')
coursesdf.replace('  +', ' ', regex=True, inplace=True)
coursesdf.replace(r' \.', '.', regex=True, inplace=True)
coursesdf = coursesdf.applymap(lambda x: x.strip()).reset_index(drop=True)

# The punctuation that occurs the most in coursegroups is probably a delimiter. Split coursegroups using that
has_newlines = coursesdf.coursegroups.str.contains('\n')
has_semicolons = coursesdf.coursegroups.str.contains(';')
has_commas = coursesdf.coursegroups.str.contains(',')
delimiterdict = {'\n': sum(has_newlines), ';': sum(has_semicolons), ',': sum(has_commas)}
delimiter = max(delimiterdict, key=delimiterdict.get)
coursesdf.coursegroups = coursesdf.coursegroups.apply(lambda groups: [x.strip() for x in groups.split(delimiter)])

# Check if prerequisites is requisites based on whether coreqs is empty
if coursesdf.requisites.eq('').all() & coursesdf.corequisites.eq('').all():
    coursesdf['requisites'] = coursesdf.prerequisites
    coursesdf['prerequisites'] = ''

print(tabulate(coursesdf.head(300), headers='keys', tablefmt='psql'))
coursesdf.to_pickle('organizedcoursedescriptions.pkl')
