"""Degree requirement cross-reference tool, encoder, and serializer

This final script identifies requirements that are not represented as individual courses (such as general education
requirements, ranges of course codes, sub-groups of courses, and elective groups specific to a degree) and integrates
those with all other requirements and restrictions into one serilialized encoding per degree track. It also serializes
supplementary requirements (such as degree concentration paths, elective groups that are specific to a degree, and gen
ed requirements).

The input are the dataframes produced in scripts 5, 6, 7, and 8. The output consists of two dataframes: one consisting
of degree requirements, elective groups, gen ed groups, and other course groupings that have contain specific
instructions (eg. 'choose two courses from the following group'), and a second dataframe consisting of course groups
that do not contain specific instructions (eg. 'upper division psychology courses') which are referenced by the degree
requirements. Additionally, all relevent degree information and course group information is produced.

Below is an example and corresponding translation of the serialized code:

code:    _3_credits__AREC202_ | _4_credits__CHEM107_ | _1_credits__CHEM108_ | _3_credits__CO150_ | _3_credits__0003_
         _2_courses_ _1_groups_{{_LIFE102_ | _LIFE103_} | {_BZ110_ | _BZ111_ | _BZ120_}} | _6_credits__table_9011_

Translation:      3 credits of AREC 202
              AND 4 credits of CHEM 107
              AND 1 credits of CHEM 108
              AND 3 credits of CO 150
              AND 3 credits of General Education Humanities
              AND 2 courses, chosen from one of the following groups
                    Group A:  LIFE 102; LIFE 103
                    Group B:  BZ 110; BZ111; BZ120
              AND 6 credits from the agricultural biology electives list

Note that "|" represents a generic separation. Within groups where no requirement is listed inside the brackets (eg.
within Group A and B) they mean "or", however when separating codes that contain requirements (all other examples above)
they indicate "and".

Codes that begin with "_table_" reference another serialized code's ID elsewhere in the dataframe (eg. _table_9011_).
Codes that only contain four numeric digits (e.g. _0003_) reference serialized codes of course groups with no
requirements (these are found in the output dataframe labeled 'gdf').

Other codes not included in the above example are as follows:

_upperdiv_ - Modifies codes to specify that the courses/credits must be upper division (3000-4000 level)
    Example: 9_credits__2_courses_upperdiv_
_max_ - Modifies codes to indicate that the requirement is a maximum rather than a minimum requirement
    Example: 2_courses__6_credits_max_
_per_group_ - Modifies group requirements to indicate how many credits/courses must be obtained from each group
    Example: _6_courses__2_courses_per_group

Superscripts are referenced with angle brackets (eg. <3>), and corresponding superscript definitions are located in the
dataframe (however are not interpreted).

Requisites that are not parsed are reprinted as plain text within brackets
    Example:  _3_credits_{Lower-div. Written Communication}

The output dataframe also yields other info relevent to each degree plan and course group, such as a link (for
verifying the serialized codes are correct), the table class (courslists and plangrids are degree plans, while
electivelists are merely groups of courses), the degree name, track, degree type, and total credits required, and
also a column called degreeflags which indicates inconsistencies within the degree (such as when the individual credits
don't sum to the total or when the script interprets requirements that conflict).

3rd party modules needed include Numpy, Pandas, Json, and TheFuzz
"""

from verticalprinter import v
import re
import os
import numpy as np
from listtopattern import listtopattern
import pandas as pd
import json
from thefuzz import fuzz
from thefuzz import process
import difflib
from random import sample
desired_width = 320
pd.set_option('display.width', desired_width)
pd.set_option('display.max_columns', 10)

df = pd.read_pickle('actualdegreesorganized.pkl')           # Output from first run of script 6
coursedf = pd.read_pickle('courses.pkl')                    # Output from script 5
geneddf = pd.read_pickle('degreesorganized.pkl')            # Output from script 7 followed by second run of script 6

with open('cnum_pattern.json') as infile:
    cnum_pattern = json.load(infile)                           # School-specific course code regex patterns
with open('cdept_pattern.json') as infile:
    cdept_pattern = json.load(infile)

or_pattern = r'(?: or | ?/ ?| ?\| ?)'
and_pattern = r'(?: and | ?& ?)'

# Merge geneddf and df   Note: geneddf often contains more than gen ed requirements (anything with a hyperlink)
if not geneddf.empty:
    df = pd.concat([df, geneddf]).reset_index(drop=True)

# Move header superscripts so they aren't processed
superscriptcodes = df.code.str.extract('((?:<.>)+)').iloc[:, 0]
df.loc[superscriptcodes.notna() & df.headerlevel.notna(), 'headercodes'] = df.headercodes + superscriptcodes
df.loc[superscriptcodes.notna() & df.headerlevel.isna(), 'sscriptvalues'] = superscriptcodes
df.code = df.code.str.replace('<.>', '', regex=True)
df.codecopy = df.codecopy.str.replace('<.>', '', regex=True)

# Link elective tables to their degree plans
df['tableheader'] = df.headertext.apply(lambda x: x[x.rindex(' : ') + 3:].strip() if ' : ' in x else x)
df.tableheader = df.tableheader.str.replace('<..?>|[(][^()]*[)]', '', regex=True)  # Remove superscripts and parentheses
df.tableheader = df.tableheader.str.replace(r'\b((select |choose )?\d\d? )?credits?\b', '',
                                            regex=True, flags=re.IGNORECASE)  # Remove credit requirements too
# Cleancode is the original plaintext without redundancies or other superlatives that may interfere with name matching
df['cleancode'] = df.codecopy.str.replace('<..?>|[(][^()]*[)]', '', regex=True)
not_names_pattern = r'\b((see )?(lists? |electives? |groups? |courses? |requirements? |listed |see )below)|((select |choose )?\d\d? )?credits?\b'
df.cleancode = df.cleancode.str.replace(not_names_pattern, '', regex=True, flags=re.IGNORECASE)
df['cleancodecopy'] = df.codecopy
df['matchscore'] = 0

# Elective tables are generally the tables that accompany degree requirements and indicate concentrations and options
electivetabledf = df[~df.containssum].groupby('id').agg({'degree': 'first', 'tableheader': 'first'})
electivetabledf = electivetabledf.reset_index(drop=True)

# Loop through each elective table and find requirements whose title matches the table's title
for index, degree, tableheader in electivetabledf.itertuples():
    codelist = df.loc[df.degree.eq(degree) & df.containssum & df.unknownreq, 'cleancode'].unique()
    if codelist.shape == (0,):
        continue
    matches = process.extract(tableheader, codelist, scorer=fuzz.token_sort_ratio, limit=10)
    for match in matches:
        if match[1] >= 70:                  # Todo: Fuzzy matching needs to be replaced
            codematch = match[0]
            matchscore = int(match[1])      # Save match score so the match can be replaced if better match is found
            ismatchanddegree = df.matchscore.lt(matchscore) & df.degree.eq(degree)
            df.loc[df.cleancode.eq(codematch) & ismatchanddegree, 'tableheadermatch'] = tableheader
            df.loc[df.cleancode.eq(codematch) & ismatchanddegree, 'codematch'] = codematch
            df.loc[df.cleancode.eq(codematch) & ismatchanddegree, 'unknownreq'] = False
            df.loc[df.tableheader.eq(tableheader) & ismatchanddegree, 'ismatched'] = True
            # Replace df.code with tablecode
            df.loc[df.cleancode.eq(codematch) & ismatchanddegree, 'code'] = \
                '_table_' + df.loc[df.tableheader.eq(tableheader) & (df.degree.eq(degree)), 'id'].iloc[0].zfill(4) + '_'
            df.loc[df.cleancode.eq(codematch) & ismatchanddegree, 'matchscore'] = matchscore

# Get coursegroups from course descriptions
coursedf.coursegroups = coursedf.coursegroups.apply(lambda x: ' | '.join(x))
allcoursegroupstring = ' | '.join(coursedf.coursegroups.to_list())

# Create new group dataframe, gdf to hold group names, their courses, and a unique ID
gdf = pd.DataFrame()
gdf = gdf.append({'group': 'electives', 'id': '_0000_', 'code': np.nan}, ignore_index=True)
# Fix variations of electives
electivewords = [r'((department )?approved |selected |required |free |general )?electives?( or \w+\Z)?']
df.cleancode = df.cleancode.str.replace(listtopattern(electivewords), 'electives', regex=True, flags=re.IGNORECASE)
df.loc[df.cleancode.str.fullmatch('electives'), 'unknownreq'] = False
df.loc[df.cleancode.str.fullmatch('electives'), 'code'] = '_0000_'
df.loc[df.cleancode.str.fullmatch('electives'), 'cleancode'] = '_0000_'

# Standardize general number code requirements (e.g. MAT 3XX --> MAT _cnum_3xxx_)
df.cleancode = df.cleancode.str.replace(r'([*][*][*][*]?|XXXX?|xxxx?|____?)', r'_cnum_xxxx_', regex=True)
df.cleancode = df.cleancode.str.replace(r'(\d)(?:\*\*\*?|XXX?|xxx?|___?)', r'_cnum_\1xxx_', regex=True)
# Standardize general department code requirements (e.g. MAT _cnum_3xxx_ --> _dept_MAT_ _cnum_3xxx_)
departmentlist = coursedf.dept.unique().tolist()
df.cleancode = df.cleancode.str.replace(listtopattern(departmentlist), r'_dept_\1_', regex=True)
# Combine general depts and nums (e.g. _dept_MAT_ _cnum_3xxx_ --> _MAT_3xxx_)
df.cleancode = df.cleancode.str.replace(r'\b_dept_([A-Z]+)_ ?-? ?_cnum_([x\d]+)_\b', r'_\1_\2_', regex=True)
gencode_pattern = r'\b_[A-Z]+_[x\d]+_\b'
# Standardize slash and 'or' separated course ranges (e.g. _MAT_3xxx_ or _cnum_4xxx --> _MAT_3xxx_ | _MAT_4xxx_)
# Todo: Fix so it replaces for groups greater than 2 (maybe do this in implicit to explicit section in script 6)
df.cleancode = df.cleancode.str.replace(r'\b(_[A-Z]+_)([x\d]+_)\b' + or_pattern + r'_cnum_([x\d]+_)', r'\1\2 | \1\3',
                                        regex=True)
df.cleancode = df.cleancode.str.replace(r'\b(_[A-Z]+_)([x\d]+_)\b' + ' ?- ?' + r'_cnum_([x\d]+_)', r'\1\2 - \1\3',
                                        regex=True)

# Make a list of all the course range codes (i.e gencodes)
gencode_list = list(set([x for sublist in df.cleancode.str.findall(gencode_pattern).to_list() for x in sublist]))
gencodes = pd.DataFrame({'group': gencode_list})
if not gencodes.empty:
    # Extract the departments and course numbers for gencodes
    gencodes['cdept'] = gencodes.group.apply(lambda x: x[1:x[1:].index('_') + 1])
    gencodes['cnum'] = (gencodes.group.apply(lambda x: x[x[1:].index('_') + 2:-1]) + '?').str.replace('x', r'\d',
                                                                                                      regex=True)
    # Extract the lists of courses for each gencode from coursedf (e.g. MAT3XX --> MAT301, MAT302, MAT311, etc.)
    gencodes['code'] = gencodes.apply(lambda x: (x.cdept + coursedf.loc[coursedf.dept.eq(x.cdept) & coursedf.number.str.fullmatch(x.cnum), 'number']).to_list(), axis=1)
    # Add these course groups to gdf as a '|' separated string
    gendf = pd.DataFrame([gencodes.group, gencodes.code.apply(lambda x: ' | '.join(x))]).T
    gdf = pd.concat([gdf, gendf]).reset_index(drop=True)
    gdf.id = gdf.index.to_series().apply(lambda x: '_' + str(x).zfill(4) + '_')     # Give each group a unique ID number

    # Replace all references to gencodes with their respective ID number (i.e. group code)
    for code in gencodes.group.to_list():
        df.loc[df.cleancode.str.fullmatch(code), 'unknownreq'] = False
        df.loc[df.cleancode.str.fullmatch(code), 'code'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]
        df.loc[df.cleancode.str.fullmatch(code), 'cleancode'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]

# Make more gencodes for combinations of gencodes (eg. 'MAT3XX or MAT4XX')
isgencodeor = df.cleancode.str.fullmatch(gencode_pattern + '(' + or_pattern + gencode_pattern + ')+')
if isgencodeor.any():
    gencodeors = pd.DataFrame({'group': df.loc[isgencodeor, 'cleancode'].unique().tolist()})
    gencodeors.group = gencodeors.group.str.replace(or_pattern, ' | ', regex=True)
    gencodeors['grouplist'] = gencodeors.group.apply(lambda x: x.split(' | '))
    gencodeors['code'] = \
        gencodeors.apply(lambda x: gdf.loc[gdf.group.isin(x.grouplist)].agg(lambda y: ' | '.join(y)).code, axis=1)
    gencodeors.drop(columns='grouplist', inplace=True)
    gdf = pd.concat([gdf, gencodeors]).reset_index(drop=True)
    gdf.id = gdf.index.to_series().apply(lambda x: '_' + str(x).zfill(4) + '_')
    # Replace references to gencode combos in df.cleancode with their ID's
    for code in gencodeors.group.to_list():
        df.loc[df.cleancode.str.fullmatch(code), 'unknownreq'] = False
        df.loc[df.cleancode.str.fullmatch(code), 'code'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]
        df.loc[df.cleancode.str.fullmatch(code), 'cleancode'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]

# Make gencodes for ranges of gencodes (e.g. _MAT_2xxx_ - _MAT_4xxx_)
isgencoderange = df.cleancode.str.fullmatch(gencode_pattern + ' ?- ?' + gencode_pattern)
if isgencoderange.any():
    gencoderangers = pd.DataFrame({'group': df.loc[isgencoderange, 'cleancode'].unique().tolist()})
    gencoderangers['firstcode'] = gencoderangers.group.apply(lambda x: x.split(' - ')).apply(lambda x: x[0])
    gencoderangers['secondcode'] = gencoderangers.group.apply(lambda x: x.split(' - ')).apply(lambda x: x[1])
    # Determine which digit varies between firstcode and secondcode
    # Todo: Generalize this so it works on more than one digit variation
    gencoderangers['ndiff'] = gencoderangers.apply(lambda x: ''.join(list(difflib.ndiff(x.firstcode, x.secondcode))),
                                                   axis=1)
    gencoderangers['ndiff'] = gencoderangers.ndiff.str.replace('  ', '')
    gencoderangers['cnum'] = gencoderangers.ndiff.str.replace(r'_[A-Z]+_- (\d)\+ (\d)xxx_', r'[\1-\2]\\d\\d\\d?',
                                                              regex=True)
    gencoderangers['cdept'] = gencoderangers.firstcode.str.extract(r'_([A-Z]+)_')
    gencoderangers['code'] = gencoderangers.apply(lambda x: (x.cdept + coursedf.loc[coursedf.dept.eq(x.cdept) & coursedf.number.str.fullmatch(x.cnum), 'number']).to_list(), axis=1)
    # Add the list of all courses within gencode range to gdf
    rangersdf = pd.DataFrame([gencoderangers.group, gencoderangers.code.apply(lambda x: ' | '.join(x))]).T
    gdf = pd.concat([gdf, rangersdf]).reset_index(drop=True)
    gdf.id = gdf.index.to_series().apply(lambda x: '_' + str(x).zfill(4) + '_')
    # Replace reference to gencode ranges in df.cleancode with their ID
    for code in gencoderangers.group.to_list():
        df.loc[df.cleancode.str.fullmatch(code), 'unknownreq'] = False
        df.loc[df.cleancode.str.fullmatch(code), 'code'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]
        df.loc[df.cleancode.str.fullmatch(code), 'cleancode'] = gdf.loc[gdf.group.eq(code), 'id'].iloc[0]

# Replace references to gen ed requirements (these are the tables extracted in script 7)
geneddf2 = df.loc[df.id.apply(float) > 8999].copy()
geneddf2['oldlink'] = geneddf2.headertext         # Todo: Change this workaround so links arent in headertext
# Extract fragment links (used to id which table they belong to)
df['fragmentlink'] = df.html.str.extract('(?<=<a href=")([^"]+)(?=")', expand=False).fillna('')
# Replace the incorrect broken fragment links with their correced version (these were fixed in script 7)
startswithhash = df.fragmentlink.str.match('#')
df['pageurl'] = df.link.apply(lambda x: x[x.index('.edu')+4:] if '.edu' in x else '')
df.loc[startswithhash, 'fragmentlink'] = df.apply(lambda x: x.pageurl + x.fragmentlink, axis=1)
# Replace references to gen ed requirements with their their corresponding table ID
oldlinklist = geneddf2.oldlink.tolist()
idlist = geneddf2.id.tolist()
linkdict = dict(zip(oldlinklist, idlist))
df.loc[df.unknownreq & df.fragmentlink.notna(), 'cleancode'] = \
    df.fragmentlink.apply(lambda x: '_table_' + str(linkdict[x]) + '_' if x in linkdict else 'UNKNOWN')
df.loc[df.unknownreq & df.fragmentlink.notna(), 'code'] = \
    df.fragmentlink.apply(lambda x: '_table_' + str(linkdict[x]) + '_' if x in linkdict else 'UNKNOWN')
df.loc[df.unknownreq & df.fragmentlink.notna() & df.code.ne('UNKNOWN'), 'unknownreq'] = False

# Unknowns is used to visualize everything that doesn't get parsed
unknowns = df.codecopy[df.unknownreq]

# Fix misclassified headers (headers that now have codes in them)
coursegroup_pattern = r'(_\d\d\d\d_|_table_\d\d\d\d_|_' + cdept_pattern + cnum_pattern + '_)'
onlycodes_pattern = '{?' + coursegroup_pattern + '(( & | [|] |[{}])' + coursegroup_pattern + ')*}?(<..?>)*'
onlycodes = df.code.str.fullmatch(onlycodes_pattern)
notheaders = onlycodes & df.headerlevel.notna() & ~df.rowtype.eq('row header')
df.degreeflags = df.degreeflags + notheaders.groupby(df.id).transform(lambda x: 'headererror ' if x.any() else '')
df.loc[notheaders, 'headerlevel'] = np.nan
# Replace tablecodes and groupcodes in lines that are in fact headers
df.loc[onlycodes & df.headerlevel.notna() & df.rowtype.eq('row header'), 'code'] = df.codecopy.str.replace(r'<..?>', '',
                                                                                                           regex=True)

# Revert unknown requirements back to original text and surround with brackets so reqcodes and superscripts make sense
df.loc[df.unknownreq, 'code'] = '{' + df.codecopy + '}'

# Calculate totals
totalreqs = sum(df.headerlevel.isna())
totalheaderreqs = sum(df.headerlevel.notna() & df.headercodes.ne(''))
# Calculate ratio of unknown requirements
totalunknowns = sum(df.unknownreq)
unknownratio = totalunknowns/totalreqs

df = df.reset_index(drop=True)

# Create a dataframe showing the codes that were replaced with tablecodes so they can be verified
df['groupname'] = df.code.apply(lambda x: gdf.group[gdf.id.eq(x)].iloc[0] if not gdf.group[gdf.id.eq(x)].empty
                                else np.nan)
df['tableid'] = '_table_' + df.id.apply(lambda x: x.zfill(4)) + '_'
df['tablename'] = df.apply(lambda x: df.headertext[df.tableid == x.code].iloc[0]
                           if not df.headertext[df.tableid == x.code].empty else np.nan, axis=1)
df.loc[df.code.str.fullmatch(r'_\d\d\d\d_'), 'codenames'] = df.groupname
df.loc[df.code.str.fullmatch(r'_table_\d\d\d\d_'), 'codenames'] = df.tablename

# This is used to visualize and double check all the group names that were matched via fuzzy matching
has_been_replaced = df.code.str.fullmatch(r'(_\d\d\d\d_|_table_\d\d\d\d_)')
replaced = df.loc[has_been_replaced][['codecopy', 'codenames']].groupby(df.codecopy, as_index=False).agg('first')

# Move superscripts back to df.code so they are linked
df.loc[df.headerlevel.isna() & df.sscriptvalues.notna(), 'code'] = df.code + df.sscriptvalues

# Convert ID column to table ID's
df.id = df.id.apply(lambda x: '_table_' + x.zfill(4) + '_')

# Finally, serialize the code column
hlevels = df.headerlevel.dropna().unique()
hlevels.sort()
df = df.reset_index()
# Collapse groups one by one, starting with the ones with the highest header levels (most inner groups),
# then aggregate codes, surround with brackets, and attach requirements from header to front
for hlevel in hlevels[::-1]:
    # Froup everything by hlevel, then omit groups that don't include the current hlevel
    df['groups'] = ((df.headerlevel <= hlevel) | df.endofindent).cumsum()
    df.loc[df.headerlevel.groupby(df.groups).transform('first').ne(hlevel), 'groups'] = np.nan
    df.loc[df.groups.groupby(df.groups).transform('count') == 1, 'groups'] = np.nan
    firstismeta = df.rowtype.groupby(df.groups).transform('first') == 'metagroup header'
    # For metagroups, only use group headers
    df.loc[firstismeta & ~df.rowtype.isin(['group header', 'metagroup header']), 'groups'] = np.nan
    # Append headercodes to individual requirements
    df.loc[df.groups.notna() & df.headercodes.ne(''), 'code'] = df.headercodes + df.code
    # Aggregate all non header cells into their header cell, joining the codes with '|'
    aggcells = df.groupby('groups', as_index=False).agg(
        {'index': 'first', 'code': lambda x: '{' + ' | '.join(x[1:]) + '}' if len(x[1:]) != 1 else x[1:],
         'title': 'first', 'coregroup': 'first', 'credits': 'first', 'degree': 'first', 'link': 'first',
         'headertext': 'first', 'superscripts': 'first', 'htmlclass': 'first', 'id': 'first', 'html': 'first',
         'rowclass': 'first', 'codecopy': 'first', 'headercodes': 'first', 'containssum': 'first',
         'tableclass': 'first', 'degreeflags': 'first', 'degreetype': 'first', 'track': 'first',
         'maxdegreecredits': 'first', 'mindegreecredits': 'first', 'rowtype': 'first',
         'headerlevel': lambda x: 100, 'endofindent': 'first', 'groups': 'first'})
    df.drop(df[df.groups.notna()].index, inplace=True)
    df = pd.concat([df, aggcells]).sort_values('index').reset_index(drop=True)
    df.loc[df.headerlevel.shift(1).notna(), 'endofindent'] = False
    # Remove rows at the current hlevel without a code, headercode, or superscript (These are just descriptive names)
    df['keepers'] = (~df.headerlevel.eq(hlevel) | (
            df.code.str.contains(r' \| |<.>|' + cdept_pattern + cnum_pattern) | df.headercodes.ne('')))
    df = df.loc[df.headerlevel.isna() | df.keepers].reset_index(drop=True)

# Append any table-wide superscripts to the entire code
code_plus_headersuperscripts = df.headertext.str.extract('((?:<.>)+)').iloc[:, 0] + '{' + df.code + '}'
df.loc[df.headertext.str.contains('<.>', regex=True), 'code'] = code_plus_headersuperscripts

# Clean up and save
df = df[['tableclass', 'track', 'link', 'code', 'superscripts', 'degreeflags', 'degreetype', 'degree',
         'maxdegreecredits', 'mindegreecredits', 'id']]
with open('schoolname.json') as infile:
    schoolname = json.load(infile)
schooldirectory = 'Output_dataframes/' + schoolname
if os.path.isfile(schooldirectory + '/degreesserialized.pkl'):
    os.remove(schooldirectory + '/degreesserialized.pkl')
df.to_pickle(schooldirectory + '/degreesserialized.pkl')
if os.path.isfile(schooldirectory + '/groupsserialized.pkl'):
    os.remove(schooldirectory + '/groupsserialized.pkl')
gdf.to_pickle(schooldirectory + '/groupsserialized.pkl')
df.to_pickle('degreesserialized.pkl')
gdf.to_pickle('groupsserialized.pkl')

# Print out 10 random degree requirements / elective tables
v(df.loc[sorted(sample(df.index.to_list(), k=10))])
print(str(totalreqs) + ' total degree requirements')
print(str(totalreqs - totalunknowns) + ' degree requirements parsed (' + str(round((1-unknownratio) * 100, 2)) + ')%')
