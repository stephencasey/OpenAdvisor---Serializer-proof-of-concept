""" Course requisite parser and serializer.

The purpose of this script is to convert course requisites into a serialized code containing information such as
whether the requisite is a prereq, coreq, or can be either, and grade requirements. The script also gives an
indication of whether all the relevant course requisite information was parsed and encoded or not.

The program takes in the dataframe produced in script 4 and outputs a similar dataframe with all of the requisite
info serialized. If the requisite info is not fully parsed, the requisites entry for that specific course will be a
copy of the original, unparsed requisites. The program also gives a percentage of how many requisites were fully parsed
out of those that contain requisites (courses without requisites or equal to 'None' are ignored in this calculation).

Here is an example of the serialized output and the translation:

code:           (_C_MATH251_??_) and (_P_MATH151_C+_ or _P_MATH213_C+_)
translation:    Corequisite of MATH-251 and a prerequisite of either MATH-151 or MATH-213 (minimum grade of C+ in both)

The code for each individual requiste has one letter at the start that indicates whether it's a prerequisite (P),
corequisite (C), can be either coreq or prereq (B), or unknown (?). The middle section indicates the course code
(eg. MATH251). The end section indicates a grade requirement (question marks indicate none specificied). Parentheses
dilineate how the words 'and' and 'or' apply to the requirements (note that without parentheses, the above example would
be completely ambiguous).

Code can also include ranges of acceptable courses (e.g. _P_POLS300_??_to_499_) and minimum credit requirements
(e.g. _P_D100_??_to_499_3_credits_)

3rd party modules needed include Pandas, Numpy, and Tabulate
"""

import re
import shutil
import os
import pandas as pd
import numpy as np
from listtopattern import listtopattern
from listtopattern import listtononcapture
from tabulate import tabulate
import json
import warnings
warnings.filterwarnings("ignore", 'This pattern has match groups')

df = pd.read_pickle('organizedcoursedescriptions.pkl')

# Make backups of reqs and description
descopy = df.description.copy()
df['desc'] = df.description
df['reqs'] = df.requisites

# Make a list of all the different coursegroups for visualizing
alllist = df.coursegroups.apply(pd.Series).stack().reset_index(drop=True)
coursegroups = alllist.unique()
coursegroups.sort()

# Determine the coursecode structure
cdeptrange = (df.dept.apply(len).min(), df.dept.apply(len).max())
course_numbers = df.number.str.extract('([0-9]+)', expand=False).fillna('')
cnumrange = (course_numbers.apply(len).min(), course_numbers.apply(len).max())
course_letters = df.number.str.extract('([A-Z]+)', expand=False).fillna('')  # Optional letters that follow course num.
cletrange = (course_letters.apply(len).min(), course_letters.apply(len).max())
# Redefine course code patterns to reflect structure
cdept_pattern = '[A-Z]'*cdeptrange[0] + '[A-Z]?'*(cdeptrange[1]-cdeptrange[0])
cnum_pattern = '[0-9]'*cnumrange[0] + '[0-9]?'*(cnumrange[1]-cnumrange[0]) + '[A-Z]'*cletrange[0] + '[A-Z]?'*(cletrange[1]-cletrange[0])

# Remove delimiters between dept and num
df = df.replace('(' + cdept_pattern + ') ?-? ?(' + cnum_pattern + ')', r'\1\2', regex=True)
ccode_pattern = cdept_pattern + cnum_pattern

# Move prereqs and coreqs to requisites   Todo: Rewrite script so coreqs and prereqs are processed separately
df.reqs = df.apply(lambda x: (x.prerequisites + '. ' + x.reqs).strip('. ') if x.prerequisites else x.reqs, axis=1)
# Ensure coreqs are tagged with the word coreqs
df.corequisites = df.corequisites.str.replace('corequisites?', '', regex=True, flags=re.IGNORECASE)
coreqsnamed = df.corequisites.str.replace('(' + ccode_pattern + ')', r'corequisite \1', regex=True)
# Ensure coreq tag is always at the start (without duplicating it), even if there's no ccodes
coreqsnamed = coreqsnamed.str.replace(r'\A\(corequisite\)?', 'corequisite', regex=True)
coreqsnamed = coreqsnamed.str.replace(r'\Acorequisite\Z', '', regex=True)
df.reqs = (df.reqs + '. ' + coreqsnamed).apply(lambda x: x.strip(' .'))

# Replace slash with or
df.reqs = df.reqs.str.replace('/', ' or ', regex=False)
df.reqs = df.reqs.str.replace('  +', ' ', regex=True)

# Replace decimals
df.replace(r'([0-9])\.([0-9])', r'\1_point_\2', regex=True, inplace=True)
# Remove periods if they are preceded by short word and followed by non-capitalized word (examples: gen. ed. req.)
df.replace(r'([( .][a-zA-Z][a-zA-Z]?[a-zA-Z]?[a-zA-Z]?)\.( ?[a-z])', r'\1\2', regex=True, inplace=True)
# Remove periods from words that contain a period in the middle which is unbroken by a space (examples: Ph.D. Me.Eng.)
df.replace(r'([a-zA-Z][a-zA-Z]?[a-zA-Z]?[a-zA-Z]?)\.([a-zA-Z][a-zA-Z]?[a-zA-Z]?[a-zA-Z]?).?', r'\1\2', regex=True,
           inplace=True)

# Check description for any misplaced requirements  Todo: Test if this is necessary (should have been done in script 4)
misplacedids = ['equisite:', 'REQUISITE:', 'equisites:', 'REQUISITES:', ' ourses:', ' ourses:', ' COURSES:', 'ourse:',
                'COURSE:']
reqcolon_desc = df.desc.apply(lambda x: [sentence + '.' for sentence in x.split('.') if
                                         any(substring in sentence for substring in misplacedids)]).str.join('')
misplaced_req_pattern = r'([^.]*?requisite(?:[- ,.;\(\[]+)' + ccode_pattern + r'[^.]*\.)'
reqccode_desc = df.desc.str.findall(misplaced_req_pattern, flags=re.IGNORECASE).str.join('').str.strip()
df.reqs = df.reqs.str.strip('.').str.cat(reqcolon_desc, '. ').str.strip('. ') + '.'
df.reqs = df.reqs.str.strip('.').str.cat(reqccode_desc, '. ').str.strip('. ') + '.'
df.loc[df.reqs == '.', 'reqs'] = ''
df.reqs = df.reqs.str.replace(r'(\A|\.) ?none.? ?(\.|\Z)', '', regex=True, flags=re.IGNORECASE)
reqscopy = df.reqs.copy()

# Fix important word misspellings & variations
preco_words = ['Pre or corequisites?', 'corequisite or prerequisite', 'prerequisite or corequisite']
prereq_words = ['prerequisites?', r'pre-?reqs?\.?', 'pre-requisites?', 'perquisites?', 'prerequsites?', 'prerquisites?',
                'prerequistes?', 'prererequisites?', 'who have completed']
coreq_words = ['corequisites?', 'corerequisites?', 'corequsites?', 'co-requisites?', r'co-?reqs?\.?']
recommended_words = ['Recommended', 'recommeded', 'department recommended']
min_words = ['minimum', 'minumum', 'mimimum', r'min\.?']
max_words = ['maximum', r'max\.?']
grade_words = ['grade?', 'minimum grade?', 'minimum grade of', '_P_requisite minimum grade']
restricted_words = ['restricted', 'excluded']

# Replace variations with standardized or encoded forms
df.replace('(?i)' + listtopattern(preco_words), '_B_requisite', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(prereq_words), '_P_requisite', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(coreq_words), '_C_requisite', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(recommended_words), 'recommended', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(min_words) + r' ', 'minimum ', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(max_words) + r' ', 'maximum ', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(grade_words) + """ (?="?'?[A-D][-+]?'?"?)""", 'grade ', regex=True, inplace=True)
df.replace('(?i)' + listtopattern(restricted_words) + ' ', 'restricted ', regex=True, inplace=True)

# Fix outros with non-sensical punctuation (might be misinterpreted later)    Todo: Remove this (too school specific)
bad_precooutros = [', may be taken concurrently']
df.reqs = df.reqs.str.replace(listtopattern(bad_precooutros), ' (may be taken concurrently)', regex=True)

# Visualize what's leftover in descriptions that contain prereq or coreq
# df.desc.str.extractall(r'([^.]*?(?:P_requisite|C_requisite)[^.]*\.)', flags=re.IGNORECASE).loc[:,0].unique()

# Remove redundancies           Todo: Test this more extensively to ensure nothing unexpected is getting removed
words_notneeded = ['completed', 'department enforced?', '(with )?(consent|permission|approval)',
                   '(with p)?(professor|instructor|teacher|(department )?chair)', 'with a', 'or (the )?equivalent',
                   'requisites?:?', 'enforced', '(may )?requires?', 'requires? a', 'requires enrollment in',
                   'of the following:?', 'of', '(this )?courses?', 'either', 'a', 'will be required',
                   '((is|are) )?required', 'requirements?', 'all', 'both']
df.reqs = df.reqs.str.replace(listtopattern(words_notneeded), '', regex=True, flags=re.IGNORECASE)
df.reqs = df.reqs.str.replace('department _P_requisite', ' _P_requisite', regex=True, flags=re.IGNORECASE)
df.reqs = df.reqs.str.replace('(requisite)(?: :|:)?', r'\1', regex=True, flags=re.IGNORECASE)
df.reqs = df.reqs.str.replace(r'\(s\)', '', regex=True)
df.reqs = df.reqs.str.replace('(?:or (or)|(and) and)', r'\1', regex=True)
df.reqs = df.reqs.str.replace(r'\A ?\. ?\Z', '', regex=True)
df.reqs = df.reqs.str.replace('  +', ' ', regex=True)

# Replace parentheses that start with the word 'or' [eg. '(or xxxxx xxxx)' with 'or xxxxx xxxx']
df.reqs = df.reqs.str.replace(r'\((or [^()]+)\)', r'\1', regex=True, flags=re.IGNORECASE)

# Replace implied course codes and departments (eg. MATH241 or 243  -->  MATH241 or MATH243)
deptslash_pattern = '(?<!rade) (' + cdept_pattern + r'),? ?(?:/|or),? ?(' + cdept_pattern + ') ?-? ?(' + cnum_pattern + ')'
numslash_pattern = '(' + cdept_pattern + ') ?-? ?(' + cnum_pattern + r'),? ?(?:/|or),? ?(' + cnum_pattern + ')'
ccodeslash_pattern = '(' + ccode_pattern + r') ?/ ?(?=' + ccode_pattern + ')'
oldreqs = pd.Series(['']*len(df.reqs))
while (oldreqs != df.reqs).any():
    oldreqs = df.reqs.copy()
    df.reqs = df.reqs.str.replace(deptslash_pattern, r'\1\3 or \2\3', regex=True)
    df.reqs = df.reqs.str.replace(numslash_pattern, r'\1\2 or \1\3', regex=True)
    df.reqs = df.reqs.str.replace(ccodeslash_pattern, r'\1 or ', regex=True)

# Encode grade requirements
df.reqs = df.reqs.str.replace(r"""(g|G)rade "?'?([A-D][-+])'?"? or (higher|better)( in)?""", r'grade_\2_', regex=True)
df.reqs = df.reqs.str.replace(r"""(g|G)rade "?'?([A-D])'?"? or (higher|better)( in)?""", r'grade_\2__', regex=True)
df.reqs = df.reqs.str.replace(r"""(g|G)rade "?'?([A-D][+-])'?"?(?=[^a-zA-Z0-9])( in)?""", r'grade_\2_', regex=True)
df.reqs = df.reqs.str.replace(r"""(g|G)rade "?'?([A-D])'?"?(?=[^a-zA-Z0-9])( in)?""", r'grade_\2__', regex=True)
df.reqs = df.reqs.str.replace(r'\b([A-D][-+]) or (higher|better)( in)?', r'grade_\1_', regex=True)
df.reqs = df.reqs.str.replace(r'\b([A-D]) or (higher|better)( in)?', r'grade_\1__', regex=True)
grade_pattern = 'grade_[A-D][+_-]_'

# Move restrictions from requisites to restrictions column      Todo: Cleanup and consolidation
studentnames = ['students', 'freshmen', 'sophomores', 'juniors', 'seniors', 'majors', 'undergraduates', 'graduates',
                'class members', 'minors']
restricted_to_pattern = r'[^.]*restricted to [^.]*' + listtononcapture(studentnames) + r'[^.]*\.|\Z'
restricted_from_pattern = r'[^.]*' + listtononcapture(studentnames) + r'[^.]*restricted from ' + r'[^.]*\.|\Z'
class_standing_pattern = r'(?:junior|senior|sophomore|graduate) standing[^.]*(?:\.|\Z)'
restrictedtos = df.reqs.str.findall(restricted_to_pattern, flags=re.IGNORECASE).str.join('').str.strip()
df.restrictions = df.restrictions.str.strip('.').str.cat(restrictedtos, '. ').str.strip('. ') + '.'
df.reqs = df.reqs.str.replace(restricted_to_pattern, '', regex=True, flags=re.IGNORECASE)
restrictedfroms = df.reqs.str.findall(restricted_from_pattern, flags=re.IGNORECASE).str.join('').str.strip()
df.restrictions = df.restrictions.str.strip('.').str.cat(restrictedfroms, '. ').str.strip('. ') + '.'
df.reqs = df.reqs.str.replace(restricted_from_pattern, '', regex=True, flags=re.IGNORECASE)
df.loc[df.restrictions == '.', 'restrictions'] = ''
classstandings = df.reqs.str.findall(class_standing_pattern, flags=re.IGNORECASE).str.join('').str.strip()
df.restrictions = df.restrictions.str.strip('.').str.cat(classstandings, '. ').str.strip('. ') + '.'
df.reqs = df.reqs.str.replace(class_standing_pattern, '', regex=True, flags=re.IGNORECASE)

# Move recommended courses (not really requisites if they are optional)
recommendeds_pattern = r'[^.]*recommended[^.]*\.|\Z'
recommendeds = df.reqs.str.findall(recommendeds_pattern, flags=re.IGNORECASE).str.join('').str.strip()
df['recommendeds'] = df.recommendeds.str.strip('.').str.cat(recommendeds, '. ').str.strip('. ') + '.'
df.reqs = df.reqs.str.replace(recommendeds_pattern, '', regex=True, flags=re.IGNORECASE).str.join('').str.strip()

# Remove extra spaces adjacent to parentheses
df.reqs = df.reqs.str.replace(r'\( ', r'(', regex=True)
df.reqs = df.reqs.str.replace(r' \)', r')', regex=True)
# Remove parentheses for singular objects in parentheses
df.reqs = df.reqs.str.replace(r'\(((?:' + ccode_pattern + ')|(?:' + grade_pattern + ')|' +
                              listtononcapture(df.dept.unique().tolist()) + r')\)', r'\1', regex=True)

# Replace commas in comma separated lists with either 'or' or 'and', depending on the context
# First, backfill 'or' or 'and' to comma separated groups within parentheses
or_and_parentheses_pattern = r'(?<=\()([^(]*), ?((?:\w+ )*\w+),? ?(or|and) ([^(]*)'
oldreqs = pd.Series(['']*len(df.reqs))
while (oldreqs != df.reqs).any():
    oldreqs = df.reqs.copy()
    df.reqs = df.reqs.str.replace(or_and_parentheses_pattern, r'\1 \3 \2 \3 \4', regex=True, flags=re.IGNORECASE)
# Second, backfill all other comma separated groups  Todo: Generalize this to nested parentheses like in delimitersplit
oldreqs = pd.Series(['']*len(df.reqs))
while (oldreqs != df.reqs).any():
    oldreqs = df.reqs.copy()
    df.reqs = df.reqs.str.replace(r', ((?:\w+ )*\w+),? (or|and)', r' \2 \1 \2', regex=True, flags=re.IGNORECASE)
# Replace comma separated lists without 'or' or 'and' with '_???_'
df.reqs = df.reqs.str.replace(r'(?<=,) ?(\w+) ?,', r'\1 _???_ ', regex=True, flags=re.IGNORECASE)
df.reqs = df.reqs.str.replace(r'(?:\A|(?<=[;:,.\(]))( ?\w+), ?', r'\1 _???_ ', regex=True, flags=re.IGNORECASE)
df.replace('  +', ' ', regex=True, inplace=True)

# Todo: Implement this with flag for reqs that fail test
# ensure all parentheses are balanced
# def matchedparentheses(string):
#     """Tests a substring to see if all its parentheses are matched and balanced"""
#     if string.count('(') != string.count(')'):
#         return False
#     balance = 0
#     for letter in string:
#         if letter == '(':
#             balance += 1
#         if letter == ')':
#             balance -= 1
#         if balance < 0:
#             return False
#     return True

# Todo: Implement other sanity checks
# ensure there are no doubled parentheses
# ensure there are no curly brackets or angle brackets
# ensure all delimiters are followed by one space
# convert square brackets to parentheses

# Delete lone periods
df.reqs = df.reqs.str.replace(r'\A ?[.] ?\Z', '', regex=True)

# Replace periods with parentheses (each individual sentence represents a separate requisite)
df.reqs = df.reqs.str.replace(r' ?([^.]+)\.?', r'{\1}', regex=True)
df.reqs = df.reqs.str.replace('}{', '} and {', regex=False)
df.reqs = df.reqs.str.replace('{', '(', regex=False)
df.reqs = df.reqs.str.replace('}', ')', regex=False)

# For requisites that are not explicitly indicated as prereq or coreq (or either) we have to determine if they are
# implicitly defined. The method that follows involves first splitting strings using parentheses into their respective
# groupings using the function delimitersplit then broadcasting the requisite within the group using the function
# heirarchical_fill.


def delimitersplit(delimiter_list, method):
    """ Converts a sentence that is split by a variety of delimiters into one that is soley split by parentheses.

    Takes a sentence that is split by delimiters, either explicit (commas, semicolons, parentheses) or implicit
    (words that imply grouping from context) into a sentence that explicitly shows separations with parentheses.

    Inputs a list containing the delimiters. If the method is specified as 'keep', then the function will not delete
    the delimiters (for instance with implied delimiters where you don't want to remove the delimiting words)

    Output is None (modifies df.reqs inplace)

    This works with any level or combination of delimiters, including in strings with complex nested parentheses and
    with a combination of other delimiters, and also modifies the placement of 'and' and 'or' to account for these
    groupings.

    Example:
    For the string "_P_requisite CSCI1300 or CSCI1310 or ECEN1310 grade_C-_ and _C_requisite MATH1300 or MATH1310", the
    words '_P_requisite' and '_C_requisite' indicate implied groupings (CSCI1300, CSCI1310, and ECEN1310 are in the
    prereq grouping, while MATH1300 and MATH1310 are in the coreq grouping). To split this sentence, we treat the
    substring ' and _C_requisite' as an implied delimiter. Using delimitersplit with the 'keep' method, this transforms
    the string to "(_P_requisite CSCI1300 or CSCI1310 or ECEN1310 grade_C-_) and (_C_requisite MATH1300 or MATH1310)"
    """
    olderreqs = pd.Series(['']*len(df.reqs))
    while (olderreqs != df.reqs).any():     # Evaluate all inner parentheses on each loop
        olderreqs = df.reqs.copy()
        for d in delimiter_list:      # Loop through each delimiter and group with parentheses
            olderreqs = df.reqs.copy()
            # Group everything to the left of the first delimiter
            if method == 'keep':
                pattern1 = r'([({])([^{)(]+?)(' + d + ')(?=[^{(]*[)}])'
                pattern2 = r'} ([^})]+?)(' + d + ')'
                pattern3 = r'} ([^})]+?)([)}])'
            else:
                pattern1 = r'([({])([^{)(' + d + r']+)()' + d + '(?=[^{(]*[)}])'
                pattern2 = r'} ([^})' + d + ']+)()(?:' + d + ')'
                pattern3 = r'} ([^})' + d + ']+)([)}])'
            df.reqs = df.reqs.str.replace(pattern1, r'\1{\2}\3', regex=True)
            oldreqs2 = pd.Series(['']*len(df.reqs))
            while (oldreqs2 != df.reqs).any():                   # Group all the middle delimiters
                oldreqs2 = df.reqs.copy()
                df.reqs = df.reqs.str.replace(pattern2, r'}{\1}\2', regex=True)
            df.reqs = df.reqs.str.replace(pattern3, r'}{\1}\2', regex=True)
        # Replace inner parentheses with <>    Note: changing from () to <> ensures they are ignored in subsequent loops
        df.reqs = df.reqs.str.replace(r'\(([^(]+?)\)', r'<\1>', regex=True)
        # Replace {} with <>
        df.reqs = df.reqs.str.replace(r'{', r'<', regex=True)
        df.reqs = df.reqs.str.replace(r'}', r'>', regex=True)
    # Replace <> with ()
    df.reqs = df.reqs.str.replace(r'<', r'(', regex=True)
    df.reqs = df.reqs.str.replace(r'>', r')', regex=True)
    # Move and's and or's that lead a parentheses to before (outside) the parentheses
    df.reqs = df.reqs.str.replace(r'\)\((or|and|\?\?\?) ', r') \1 (', regex=True)


# Apply delimitersplit to implied groupings
delimitersplit([' and _[PCB]_requisite', ' or _[PCB]_requisite'], 'keep')
# Apply to explicit delimiters
delimitersplit([';', ','], 'delete')


def heirarchical_fill(string, method, classifierexample):
    """Appends modifier ID's to course codes according to heirarchical groupings.

    For requisite groups containing complex nested parentheses, this function broadcasts modifiers (e.g. grade_C+_ or
    _C_requisite) to those requisites within the same group, or when appropriate, a sibling group. The use of ffill or
    bfill within groups is context dependent (grades are usually listed at the end of a group, prereq or coreq
    indication is listed at the beginning)

    Keyword arguments:
    string -- A hierarchical grouping, where groups and subgroups are indicated by placement in parentheses.
    method -- 'bfill' or 'ffill'
    classiferexample -- example classifier string with a tagname (fixed) and a classifier ID (variable; fixed in length)

    Modifiers must be formatted as follows:
    For front-fill:  (underscore)(ID)(underscore)(tagname)        eg: _P_requisite
    for back-fill:  (tagname)(underscore)(ID)(underscore)         eg: grade_C+_
    """
    global ccode_pattern
    if not string:
        return string
    classifierlength = classifierexample.rindex('_') - classifierexample.index('_') - 1
    taglength = len(classifierexample) - classifierlength - 2
    if method == 'bfill':
        tagname = classifierexample[:taglength][::-1]
        string = string[::-1]
        string = re.sub(r'\(', '`', string)
        string = re.sub(r'\)', '(', string)
        string = re.sub('`', ')', string)
        ccode_pat = '[' + '['.join(ccode_pattern.split('[')[::-1])[:-1]
    else:
        tagname = classifierexample[classifierlength+2:]
        ccode_pat = ccode_pattern
    bracketindex = [i for i, x in enumerate(string) if x in ')(']
    highestlevel = 10                    # Parameter that sets how many levels are possible in the heirarchy
    reqtype = [classifierlength*'?' + '_']*highestlevel
    level = 1
    newstring = ''
    # Loop through every bracket from left to right, and keep count of how many open/close brackets you've crossed
    for bracketi, bracketstart in enumerate(bracketindex[:-1]):
        nextbracketstart = bracketindex[bracketi+1]
        nextbracket = string[nextbracketstart]
        bracketstring = string[bracketstart:nextbracketstart]
        reqstarts = [x.start()+1 for x in re.finditer('_' + tagname, bracketstring)]
        if reqstarts:
            newstring += re.sub('(' + ccode_pat + ')', '_' + reqtype[level] + r'\1',
                                bracketstring[:reqstarts[0] - classifierlength-2])
            for starti, start in enumerate(reqstarts):
                if start == reqstarts[-1]:
                    reqstring = bracketstring[start + taglength + 1:]
                else:
                    reqstring = bracketstring[start + taglength + 1:reqstarts[starti + 1] - classifierlength-2]
                if nextbracket == '(':                          # Then save the reqtype for use in the next brackets
                    reqtype[level:] = [bracketstring[start-(1+classifierlength):start]]*(highestlevel-level)
                    newstring += re.sub('(' + ccode_pat + ')', '_' + reqtype[level] + r'\1', reqstring)
                else:                                           # Just apply the current req type and forget it
                    newstring += re.sub('(' + ccode_pat + ')', '_' + bracketstring[start-classifierlength-1:start] +
                                        r'\1', reqstring)
        else:
            newstring += re.sub('(' + ccode_pat + ')', '_' + reqtype[level] + r'\1', bracketstring)
        # Level keeps track of how deep in the bracket heirarchy you are
        # Level=1 means you are inside one bracket, level=2 means nested in two, level=3 means nested in 3, etc...
        if nextbracket == ')':
            level -= 1
            reqtype[level:] = [reqtype[level]] * (highestlevel - level)     # reset reqtype to parent group's type
        else:
            level += 1
    newstring += ')'
    if method == 'bfill':
        newstring = newstring[::-1]
        newstring = re.sub(r'\(', '`', newstring)
        newstring = re.sub(r'\)', '(', newstring)
        newstring = re.sub('`', ')', newstring)
    return newstring


# Run code_ffill for requisites and grades
df.reqs = df.reqs.apply(lambda x: heirarchical_fill(x, method='ffill', classifierexample='_P_requisite'))
df.reqs = df.reqs.apply(lambda x: heirarchical_fill(x, method='bfill', classifierexample='grade_F-_'))

# Use actual cdepts if cdept_pattern is too long (to speed things up)
if cdept_pattern.count('?') > 3:
    titleccodes = df.dept.str.extract('([A-Z]+)', expand=False).unique().tolist()
    equivccodes = [x for sublist in df.equivalents.str.findall(r'(\b[A-Z]+(?=\b|\d))').to_list() for x in sublist]
    cdept_pattern = listtononcapture(titleccodes + list(set(equivccodes)))
    ccode_pattern = cdept_pattern + cnum_pattern

fcodeqmark_pattern = r'_[?PCB]_' + ccode_pattern + r'_[?A-D][?_+-]_'
fcode_pattern = r'_[PCB]_' + ccode_pattern + r'_[?A-D][?_+-]_'

# Assign unknown reqs in reqs column as requisites (they're implied)
df.reqs = df.reqs.str.replace(r'_\?_([A-Z][A-Z]?[A-Z]?[A-Z]?[0-9][0-9][0-9][0-9]?[A-Z]?_[?A-D][?_+-]_)', r'_P_\1',
                              regex=True)

# Assign course ranges      Todo: Implement this section earlier
df.reqs = df.reqs.str.replace('(' + fcode_pattern + ')( to | ?-? ?)(' + cnum_pattern + ')', r'\1to_\3_', regex=True)
frange_pattern = fcode_pattern + 'to_' + cnum_pattern + '_'
# Assign credit requirements            Todo: Clean up code syntax
creditreq_outros = [r' - at least (\d\d?\d?) credits']
df.reqs = df.reqs.str.replace('(' + fcode_pattern + '|' + frange_pattern + ')' + listtononcapture(creditreq_outros),
                              r'\1\2_credits_', regex=True)
f_all_pattern = fcode_pattern + '(?:(?:to_' + cnum_pattern + r'_)?\d\d?\d?_credits_)?'
# Assign _B_requisite outros
df.reqs = df.reqs.str.replace('_P_(' + ccode_pattern + r'_[?A-D][?_+-]_' + r') ?\(may be taken concurrently\)',
                              r'_B_\1', regex=True)

# Simplify parentheses
# Remove parentheses from groups with zero items
df.reqs = df.reqs.str.replace(r' ?\(\)', r'', regex=True)
# Remove parentheses from singular groups
issingular = df.reqs.apply(lambda x: x.count('(')) == 1
df.loc[issingular, 'reqs'] = df.loc[issingular, 'reqs'].str.replace(r'\((.*)\)', r'\1', regex=True)
df.reqs = df.reqs.str.replace(r'\((' + fcodeqmark_pattern + r')\)', r'\1', regex=True)

# Assume ??? means 'and' if there is no other 'and' or 'or' present
hasandor = df.reqs.str.contains('( and | or )')
df.loc[~hasandor, 'reqs'] = df.reqs.str.replace(' _???_ ', ' and ', regex=False)

# Remove lone or or and (leftover from removing redundacies stage)
df.reqs = df.reqs.str.replace(r'\A ?(or|and) ?\Z', '', regex=True)

# Replace no reqs with ''
df.reqs[df.reqs.str.fullmatch('none', flags=re.IGNORECASE)] = ''

# Delete leading and trailing 'and' and 'or' (leftover from removing redundancies step)
df.reqs = df.reqs.str.replace(r'\A(.*?)( and| or)+ ?\Z', r'\1', regex=True)
df.reqs = df.reqs.str.replace(r'( and| or)+ ?([)])', r'\2', regex=True)
df.reqs = df.reqs.str.replace(r'\A ?(and |or )+(.*?)\Z', r'\2', regex=True)
df.reqs = df.reqs.str.replace(r'([(]) ?(and |or )+', r'\1', regex=True)

# Todo: Implement a more robust method to check if context is correct before deleting
# Determine what's fully parsed by deleting parsed items and checking for an empty string at the end
andorflags = pd.Series([False]*len(df))
pcollapse = df.reqs
pcollapse_old = pd.Series(['']*len(df.reqs))
while (pcollapse != pcollapse_old).any():
    pcollapse_old = pcollapse.copy()
    # Delete all fcodes from inner parentheses
    pcollapse_oldish = pd.Series(['']*len(df.reqs))
    while (pcollapse != pcollapse_oldish).any():
        pcollapse_oldish = pcollapse.copy()
        pcollapse = pcollapse.str.replace(r'(\([^()]*)' + f_all_pattern + r'([^()]*\))', r'\1\2', regex=True)
    # Check inner parentheses to see if there are a mix of ands or ors
    hasandor = pcollapse.str.contains(r'\([^()]* and [^()]* or [^()]*\)')
    hasorand = pcollapse.str.contains(r'\([^()]* or [^()]* and [^()]*\)')
    andorflags.loc[np.logical_or(hasandor, hasorand)] = True
    # Delete ands and ors in inner parentheses if they don't have a mix
    pcollapse_oldish = pd.Series(['']*len(df.reqs))
    while (pcollapse != pcollapse_oldish).any():
        pcollapse_oldish = pcollapse.copy()
        pcollapse[~np.logical_or(hasandor, hasorand)] = pcollapse.str.replace(r'(\([^()]*)( and | or )([^()]*\))',
                                                                              r'\1\3', regex=True)
    # Delete empty parentheses
    pcollapse.replace(r'\(\)', '')
# Move reqs with mix of ands and ors in parentheses
df['?requirements'] = df.loc[andorflags, 'reqs']
df.loc[andorflags, 'reqs'] = ''

# Check for mix of ands and ors in the remaining pcollapse (indicates an ambiguous requirement)
noandor = ~pcollapse.str.contains(r' and .* or ')
noorand = ~pcollapse.str.contains(r' or .* and ')
# Check for extra junk left over
pcollapse = pcollapse.replace('(' + f_all_pattern + r'|or|and|[ ()])', '', regex=True)

# Final check for what's parsed and not ambiguous
noextras = pcollapse.eq('')
noissues = noandor & noorand & noextras

# Reset requisites column and move over completely parsed reqs to it
df['requisites'] = ''

# Only fcode and all or's; or only fcode and all and's
onlyorfcode = df.reqs.str.contains(r'\A' + fcode_pattern + '( or ' + fcode_pattern + r')*\Z')
onlyandfcode = df.reqs.str.contains(r'\A' + fcode_pattern + '( and ' + fcode_pattern + r')*\Z')
df.loc[noissues, 'requisites'] = df.loc[noissues, 'reqs']
df.loc[noissues, 'reqs'] = ''

# Identify ambiguous and's and or's
onegroupands = df.reqs.str.contains(r'\A[^()]* and [^()]*\Z')
onegroupors = df.reqs.str.contains(r'\A[^()]* or [^()]*\Z')
unknownconjunctions = df.reqs.str.contains(r' \?\?\? ')
df['?requirements'] = df.loc[np.logical_or(np.logical_and(onegroupands, onegroupors), unknownconjunctions), 'reqs']
df.loc[np.logical_or(np.logical_and(onegroupands, onegroupors), unknownconjunctions), 'reqs'] = ''

# Todo: Simplify logic statements

# Save ccode patterns for later scripts
with open('cnum_pattern.json', 'w') as outfile:
    json.dump(cnum_pattern, outfile)
with open('cdept_pattern.json', 'w') as outfile:
    json.dump(cdept_pattern, outfile)

df['requisites (original)'] = reqscopy
df['requisites (parsed & unambiguous only)'] = df.requisites
df['requisites (ambiguous)'] = df['?requirements'].fillna('')

df = df[['dept', 'number', 'credits', 'title', 'requisites (parsed & unambiguous only)', 'requisites (original)',
         'requisites (ambiguous)', 'description', 'equivalents', 'coursegroups', 'gradingtype', 'recommendeds',
         'repeatablity', 'restrictions', 'registrationinfo', 'termoffered', 'coursefees', 'GTpathways']]

# Save and print results
df.to_pickle('courses.pkl')
with open('schoolname.json') as infile:
    schoolname = json.load(infile)
schooldirectory = 'Output_dataframes/' + schoolname
if os.path.isdir(schooldirectory):
    shutil.rmtree(schooldirectory)
os.mkdir(schooldirectory)
df.to_pickle(schooldirectory + '/courses.pkl')

print(tabulate(df.head(100), headers='keys', tablefmt='psql'))
print(str(len(df)) + ' total courses')
print(str(sum(noextras)) + ' total parsed (' + str(round(100*sum(noextras)/len(df), 2)) + '%)')
isnontrivial = ~reqscopy.isin(['', 'None', ' None.'])       # Todo: Make this not string specific
print(str(sum(isnontrivial)) + ' non-trivial courses')
nontrivialparsed = sum(noextras & isnontrivial)
print(str(nontrivialparsed) + ' non-trivial parsed (' + str(round(100*nontrivialparsed/sum(isnontrivial), 2)) + '%)')
print(str(sum(df['requisites (ambiguous)'].ne(''))) + ' requirements are ambiguous')

# # Print out a random sample for verification
# parsed_reqs = df.loc[df['requisites (parsed & unambiguous only)'].ne('') | df['requisites (ambiguous)'].ne('')]
# print(tabulate(df.loc[sorted(sample(parsed_reqs.index.to_list(), k=100))], headers='keys', tablefmt='psql'))
