""" Organizes degree requirement tables and categorizes entries

This script takes relatively unmodified degree requirement tables (four year plans, lists of degree requirements, lists
of electives, etc.) and converts them to a highly organized and categorized form. This includes classifying each row
according to it's function (individual requirement, descriptive header, header that modifies requirements, summarization
of credits, etc.) based on definitions that are explicit (via html tags and class ID's) and implicit (inferred from
content, context, and relation to other elements). Other information is also determined such as overall credit
requirements, degree type, and concentration, and validated.

This script takes the dataframes generated from scripts 3 & 5 and outputs a dataframe containing all the organized
degree requirements in table form.

Third party modules needed include Tabulate, Numpy, and Pandas.
"""

import re
import numpy as np
from listtopattern import listtopattern
import pandas as pd
import json
from req_encode import req_encode
from req_encode import groupwords
import sys
import warnings
warnings.filterwarnings("ignore", 'This pattern has match groups')
desired_width = 320
pd.set_option('display.width', desired_width)
pd.set_option('display.max_columns', 10)

df = pd.read_pickle('degreetables.pkl')

# If no hyperlinks were found in script 7 save an empty dataframe Todo: fix this workaround properly
if df.empty:
    df.to_pickle('degreesorganized.pkl')
    sys.exit()

with open('cnum_pattern.json') as infile:
    cnum_pattern = json.load(infile)
with open('cdept_pattern.json') as infile:
    cdept_pattern = json.load(infile)

# Define regex patterns
credit_pattern = r'([0-9][0-9]?[0-9]?\.?[0-9]?) ?-? ?([0-9][0-9]?[0-9]?\.?[0-9]?)?'
mincredit_pattern = r'\A([0-9][0-9]?[0-9]?\.?[0-9]?)'
maxcredit_pattern = r'([0-9][0-9]?[0-9]?\.?[0-9]?)\Z'
or_pattern = r'(?: or | ?/ ?| ?[|] ?)'
and_pattern = r'(?: and | ?& ?)'

# region Standardize table formatting and simple requirements
df = df.fillna('')
df = df.replace('nan', '')
df = df.applymap(str)
df.headerflag = df.headerflag.eq('True')  # convert headerflag from string back to bool
df.credits = df.credits.str.replace('.0', '', regex=False)  # simplify string representations of floats
df = df.replace('  +', ' ', regex=True)
df.code = df.code.replace(' :', ':', regex=False)
df.degree = df.pagetitle        # set page-title as degree (not link title)

# Check that special characters used in this program aren't already in use
df.code = df.code.str.replace('<([^<>][^<>][^<>]+)>', r'(\1)', regex=True)     # Replace <> if more than 3 chars inside
df.code = df.code.str.replace('{([^{}]*)}', r'(\1)', regex=True)

if df.code.str.contains('[{}<>¥ß§Æ¿Ø]').any():
    raise Exception('Special characters are present in the code column')

# Reformat superscripts to angle bracket representation
df.code = df.code.str.replace(r' ?_SUPERSCRIPT_(..?)_ ?', r'<\1>', regex=True)
df.headertext = df.headertext.str.replace(r' ?_SUPERSCRIPT_(..?)_ ?', r'<\1>', regex=True)

# Fix ccodes without a space between it and 'or' or &
df.code = df.code.replace(r'\b(' + cdept_pattern + ')' + ' ?-? ?(' + cnum_pattern + r')' + r'(&|or) ', r'\1\2 \3 ',
                          regex=True)

# Remove hyphens and spaces from ccodes
df = df.replace(r'\b(' + cdept_pattern + ')' + ' ?-? ?(' + cnum_pattern + r')\b', r'_\1\2_', regex=True)
ccode_pattern = '_' + cdept_pattern + cnum_pattern + '_(?:<.>)*'  # ccode + superscripts

# Fill in 'or' or 'and' seperated ccodes that lack either the dept or number (dept or number is implied)
df_old = (['']*len(df.code))
while (df.code != df_old).any():
    df_old = df.code.copy()
    df.code = df.code.str.replace(
        r'\b(_' + cdept_pattern + ')(' + cnum_pattern + '_)' + or_pattern + '(' + cnum_pattern + r')\b',
        r'\1\2 | \1\3_', regex=True)
    df.code = df.code.str.replace(
        r'\b(_' + cdept_pattern + ')(' + cnum_pattern + '_)' + and_pattern + '(' + cnum_pattern + r')\b',
        r'\1\2 & \1\3_', regex=True)
    df.code = df.code.str.replace(
        r'\b(' + cdept_pattern + ')' + or_pattern + '(_' + cdept_pattern + ')' + '(' + cnum_pattern + r'_)\b',
        r'_\1\3 | \2\3', regex=True)
    df.code = df.code.str.replace(
        r'\b(' + cdept_pattern + ')' + and_pattern + '(_' + cdept_pattern + ')' + '(' + cnum_pattern + r'_)\b',
        r'_\1\3 & \2\3', regex=True)

# Convert '&' and 'or' seperated ccodes into one unit
df = df.replace('(' + ccode_pattern + ') ?& ?', r'\1 & ', regex=True)

# Merge rows that begin with 'or' and their preceding row(s) into one XOR group
startswithor = df.code.str.match('or ', flags=re.IGNORECASE)
df.loc[startswithor, 'code'] = df.loc[startswithor, 'code'].str.replace('or ', '', flags=re.IGNORECASE)
orgroups = (~startswithor).cumsum()
df = df.groupby(orgroups, as_index=False).agg(
    {'code': ' | '.join, 'title': ' | '.join, 'coregroup': 'first', 'credits': 'first', 'headerflag': 'first',
     'pagenumber': 'first', 'tabnumber': 'first', 'degree': 'first', 'link': 'first', 'headertext': 'first',
     'siblingheaders': 'first',
     'superscripts': 'first', 'htmlclass': 'first', 'id': 'first', 'html': 'first', 'rowclass': 'first'})

# Replace 'or' when it separates two courses and place brackets around the group so it's serialized correctly later
allccodeor = df.code.str.fullmatch(ccode_pattern + '(' + or_pattern + ccode_pattern + ')+')
allccodeand = df.code.str.fullmatch(ccode_pattern + '(' + and_pattern + ccode_pattern + ')+')
df.loc[allccodeor, 'code'] = df.code.str.replace(or_pattern, ' | ', regex=True)
df.loc[allccodeand, 'code'] = df.code.str.replace(and_pattern, ' & ', regex=True)
df.loc[allccodeor | allccodeand, 'code'] = '{' + df.loc[allccodeor | allccodeand, 'code'] + '}'

# Delete (s)        example: course(s) --> course
df.code = df.code.replace('(s)', '', regex=False)
# endregion

df['codecopy'] = df.code

# Replace numerical requirement substrings with encoded numerical requirements (i.e. Named-entity recognition)
df.code = req_encode(df.code)

# Copy all header codes over to a new column
df['headercodes'] = df.code.str.findall(r'_[^ ]+[a-z][a-z][a-z]_\b').apply(lambda x: ' '.join(x))

# Flag headers with multiple conflicting requirements
nonumbersheadercodes = df.headercodes.str.replace(r'\d\d?-\d\d?|\d\d?', '', regex=True)
df['codeconflict'] = nonumbersheadercodes.apply(lambda x: len(x.split()) != len(set(x.split())))
df['degreeflags'] = ''
df.degreeflags = df.codeconflict.groupby(df.id).transform(lambda x: 'codeconflict ' if x.any() else '')

# region ID headers and credit summations

# ID headers that have row in an html header class
isrowheader = df.html.str.contains('areaheader', regex=False)
isrowsubheader = df.html.str.contains('areasubheader', regex=False)

# ID headers based on presence of a colon
iscolonheader = df.code.str.contains(r': ?\Z')

# ID headers based on indentation
df.html = df.html.str.replace('<br', 'Ð')         # Replace with special character so we can avoid it in next step
isindented = df.html.str.contains(r'\A[^Ð]* style="margin-left:')
indentlevel = df.html.str.extract(r'\A[^Ð]* style="margin-left:(\d\d?\d?)px').iloc[:, 0].fillna('0')
df.html.str.replace('Ð', '<br')
if len(indentlevel.unique()) > 2:
    raise Exception('Tables have multiple levels of indent. Update table header heirarchy.')
# group together indented objects
indentgroups = isindented.eq(False).cumsum()
indentgroups.loc[indentgroups.groupby(indentgroups).transform('count') == 1] = np.nan
# ID header of indented objects
isindentheader = pd.Series(index=indentgroups.index, dtype=bool)
isindentheader.loc[indentgroups.groupby(indentgroups).head(1).index] = True  # Why does this treat nan's as a group?!
isindentheader.loc[0] = False

# ID headers for the entire table
istableheader = df.headerflag.copy()
df.drop(columns='headerflag', inplace=True)

# ID headers for the year or semester in plangrids
istermheader = df.rowclass.isin(['plangridyear', 'plangridterm'])

# ID metaheaders (metaheaders indicate groups that contain sub-group requirements (eg: choose two of the groups below))
ismetaheader = df.headercodes.str.contains('group', flags=re.IGNORECASE)

# All headers together
isheader = isrowheader | isrowsubheader | isindentheader | iscolonheader | istableheader | istermheader | ismetaheader

# ID rows where indentation ends
reverseindentgroups = isindented[::-1].eq(False).cumsum()[::-1]
reverseindentgroups.loc[reverseindentgroups.groupby(reverseindentgroups).transform('count') == 1] = np.nan
isendofindent = pd.Series(index=indentgroups.index, dtype=bool)
isendofindent.loc[
    reverseindentgroups.groupby(reverseindentgroups).tail(1).index] = True
isendofindent.loc[0] = False

# ID tables with credit sums
creditsumnames = [r'(\w+ )?total (program )?(credits|units|hours)( required)?:?']
totalincode = df.code.str.fullmatch(listtopattern(creditsumnames), flags=re.IGNORECASE)
totalintitle = df.title.str.fullmatch(listtopattern(creditsumnames), flags=re.IGNORECASE)
alternatetotalmatch = df.title.str.fullmatch('total .+ (credits|units|hours)( required)?:?', flags=re.IGNORECASE)
creditsum_is_predefined = df.rowclass.isin(['listsum', 'plangridsum', 'plangridtotal'])

iscreditssum = creditsum_is_predefined | totalincode | totalintitle | alternatetotalmatch
df['containssum'] = iscreditssum.groupby(df.id).transform(lambda x: sum(x) != 0)
isplangrid = df.htmlclass.eq('sc_plangrid')
iscourselist = df.htmlclass.eq('sc_courselist') & df.containssum
iselectivelist = df.htmlclass.eq('sc_courselist') & ~df.containssum
df.loc[isplangrid, 'tableclass'] = 'plangrid'
df.loc[iscourselist, 'tableclass'] = 'courselist'
df.loc[iselectivelist, 'tableclass'] = 'electivelist'

if (~df.containssum & isplangrid).any():                # Todo: Replace exception with user prompt
    raise Exception('A plangrid doesnt have a credit sum')
# endregion

# region Extract degree type, concentrations, and credit info and validate
# Compare individual credits to program total credits
contains_credits = df.credits.str.fullmatch(credit_pattern)
varieswords = ['var(ies|iable)?.?']
creditsvary = df.credits.str.fullmatch(listtopattern(varieswords), flags=re.IGNORECASE)
df['maxcredits'] = df.credits.str.extract(maxcredit_pattern).iloc[:, 0].astype(float).fillna(0)
df['mincredits'] = df.credits.str.extract(mincredit_pattern).iloc[:, 0].astype(float).fillna(0)

# if df[~df.containssum].maxcredits.max() > 100:        # Todo: Replace exception with user prompt
#     raise Exception('An electives table has a high credits value (may be a degree requirement table)')

df.loc[creditsvary, 'maxcredits'] = 120  # 'credits vary' could mean anywhere from 0-120 credits at the extremes
df['creditsumblocks'] = (iscreditssum | istableheader)[::-1].cumsum()[::-1]
df.loc[~iscreditssum.groupby(df.creditsumblocks).transform('last'), 'creditsumblocks'] = np.NaN
df['maxsums'] = df.maxcredits.groupby(df.creditsumblocks).transform(lambda x: sum(x[~iscreditssum]))
df['minsums'] = df.mincredits.groupby(df.creditsumblocks).transform(lambda x: sum(x[~iscreditssum]))

lastcreditsum = pd.Series([False] * len(iscreditssum))  # Degree totals (not term totals)
lastcreditsum.loc[df.loc[iscreditssum, 'creditsumblocks'].groupby(df.id).tail(1).index] = True
df['credittotalblocks'] = (lastcreditsum | istableheader)[::-1].cumsum()[::-1]
df.loc[~lastcreditsum.groupby(df.credittotalblocks).transform('last'), 'credittotalblocks'] = np.NaN
df['maxtotals'] = df.maxcredits.groupby(df.credittotalblocks).transform(lambda x: sum(x[~iscreditssum]))
df['mintotals'] = df.mincredits.groupby(df.credittotalblocks).transform(lambda x: sum(x[~iscreditssum]))

# Verify sums and totals
sumnotinrange = ((df.maxcredits > df.maxsums) | (df.mincredits < df.minsums)) & iscreditssum & ~lastcreditsum
totalnotinrange = ((df.maxcredits > df.maxtotals) | (df.mincredits < df.mintotals)) & lastcreditsum
notinrange = sumnotinrange | totalnotinrange

# Flag mismatches
df.degreeflags = df.degreeflags + df.degreeflags.groupby(df.id).transform(lambda x: 'creditmismatch '
                                                                          if not x[notinrange].empty else '')
df.degreeflags = df.degreeflags + df.degreeflags.groupby(df.id).transform(lambda x: 'creditsvary '
                                                                          if not x[creditsvary].empty else '')

# ID degree types       Todo: Clean this up so code isn't duplicated
df.loc[df.degree.str.contains(r'\b(bachelor|major in|BA|BS|BM|BFA|BSN|BBA|BAS|BSME|BSRS|BSW|BME)\b',
                              flags=re.IGNORECASE), 'degreetype'] = 'bachelor'
df.loc[df.degree.str.contains(r'\b(associates?|AAS|AA|AS)\b', flags=re.IGNORECASE), 'degreetype'] = 'associate'
df.loc[df.degree.str.contains(r'\b(certificate|PCT)\b', flags=re.IGNORECASE), 'degreetype'] = 'certificate'
df.loc[df.degree.str.contains(r'\bminor\b', flags=re.IGNORECASE), 'degreetype'] = 'minor'
df.loc[df.degree.str.contains(r'\b(masters?|MS|ME|MA|MAED|MSN|MPAS|MBA)\b', flags=re.IGNORECASE), 'degreetype'] = 'master'
df.loc[df.degree.str.contains(r'\bdual degree\b', flags=re.IGNORECASE), 'degreetype'] = 'dual bachelor'
df.loc[df.degree.str.contains(r'\b3\+2 \b', flags=re.IGNORECASE), 'degreetype'] = 'combined B&M'
df.loc[df.degree.str.contains(r'\bp.?h.?d.?|doctor(ate)?\b', flags=re.IGNORECASE), 'degreetype'] = 'doctorate'

# If no degree types were found in degree column, look in the headertext
if df.degreetype.isna().all():
    df.loc[df.headertext.str.contains(r'\b(bachelor|major in|BA|BS|BM|BFA|BSN|BBA|BAS|BSME|BSRS|BSW|BME)\b',
                                      flags=re.IGNORECASE), 'degreetype'] = 'bachelor'
    df.loc[df.headertext.str.contains(r'\b(associates?|AAS|AA|AS)\b', flags=re.IGNORECASE), 'degreetype'] = 'associate'
    df.loc[df.headertext.str.contains(r'\b(certificate|PCT)\b', flags=re.IGNORECASE), 'degreetype'] = 'certificate'
    df.loc[df.headertext.str.contains(r'\bminor\b', flags=re.IGNORECASE), 'degreetype'] = 'minor'
    df.loc[df.headertext.str.contains(r'\b(masters?|MS|ME|MA|MAED|MSN|MPAS|MBA)\b',
                                      flags=re.IGNORECASE), 'degreetype'] = 'master'
    df.loc[df.headertext.str.contains(r'\bdual degree\b', flags=re.IGNORECASE), 'degreetype'] = 'dual bachelor'
    df.loc[df.headertext.str.contains(r'\b3\+2 \b', flags=re.IGNORECASE), 'degreetype'] = 'combined B&M'
    df.loc[df.headertext.str.contains(r'\bp.?h.?d.?|doctor(ate)?\b', flags=re.IGNORECASE), 'degreetype'] = 'doctorate'
df.loc[df.degree.eq('GENEDS'), 'degreetype'] = 'GENEDS'
if df.degreetype.isna().any():
    print(df.degree[df.degreetype.isna()].unique())
    print('Ignore these unidentified degrees? (y/n)')
    if input() != 'y':
        raise Exception('Terminated by User')

# Determine if there are multiple tracks for the same degree
hasmultipletracks = pd.Series([False] * len(isheader))
hasmultipletracks[isplangrid] = df[isplangrid].id.groupby([df.degree, df.tableclass]).transform(lambda x:
                                                                                                len(x.unique()) > 1)
hasmultipletracks[iscourselist] = df[iscourselist].id.groupby([df.degree, df.tableclass]).transform(lambda x:
                                                                                                    len(x.unique()) > 1)

# if not df.loc[hasmultipletracks, 'tableclass'].groupby(df.degree).transform(lambda x: len(x.unique()) > 1).empty:
#     raise Exception('Theres a degree with multiple fouryearplans AND multiple courselists')

# Extract concentration/track from page header, table headers, titles, or if absent, assign a unique ID
tableheader = df.headertext.apply(lambda x: x[x.rindex(' : ')+3:] if ' : ' in x else x)
numberofheaders = tableheader.groupby([df.degree, df.tableclass]).transform(lambda x: len(x.unique()))
numberoftoprows = df.code.groupby([df.degree, df.tableclass]).transform(lambda x: len(x.unique()))
numberoftables = df.id.groupby([df.degree, df.tableclass]).transform(lambda x: len(x.unique()))
toprowisheader = isheader.groupby(df.id).transform(lambda x: x.iloc[1] if len(x) > 1 else False)
alltoprowsareheader = toprowisheader.groupby([df.degree, df.tableclass]).transform('all')
toprows = df.code.groupby(df.id).transform(lambda x: x.iloc[1] if len(x) > 1 else np.nan)

# If headers vary, use those as track name; if toprows vary, use those; if nothing varies, use ID
df.loc[hasmultipletracks & (numberofheaders == numberoftables), 'track'] = tableheader
df.loc[hasmultipletracks & ~(numberofheaders == numberoftables) & (numberoftoprows == numberoftables), 'track'] = toprows
df.loc[hasmultipletracks & ~(numberofheaders == numberoftables) & ~(numberoftoprows == numberoftables), 'track'] = df.id
df.loc[df.track.notna(), 'track'] = df.degree + ' : ' + df.track
df.loc[df.track.isna(), 'track'] = df.degree

# Verify total credits makes sense for degree type
df['maxdegreecredits'] = df.maxcredits.groupby(df.track).transform(lambda x: max(x[iscreditssum])
                                                                   if not x[iscreditssum].empty else np.nan)
df['mindegreecredits'] = df.mincredits.groupby(df.track).transform(lambda x: max(x[iscreditssum])
                                                                   if not x[iscreditssum].empty else np.nan)
# # If less than 120 credits total for bachelors, this is only a partial sum
# df.loc[df.degreetype.isin(['bachelor', 'dual bachelor']) & (df['mindegreecredits'] < 120), 'maxdegreecredits'] = np.nan
# if df.degreetype.eq('master').any() and max(df.loc[df.degreetype.eq('master'), 'maxdegreecredits']) > 115:
#     raise Exception('theres a masters degree with more than 115 credits')
# if df.degreetype.eq('certificate').any() and max(df.loc[df.degreetype.eq('certificate'), 'maxdegreecredits']) > 65:
#     raise Exception('theres a certificate with more than 60 credits')
# if df.degreetype.eq('minor').any() and max(df.loc[df.degreetype.eq('minor'), 'maxdegreecredits']) > 40:
#     raise Exception('theres a minor with more than 40 credits')

df.drop(columns=['maxcredits', 'mincredits', 'creditsumblocks', 'maxsums', 'minsums', 'credittotalblocks', 'maxtotals',
                 'mintotals'], inplace=True)
# endregion

# ID rowtypes
# Row characteristics
only_ccode = df.code.str.fullmatch(ccode_pattern)
only_ccodecombos = df.code.str.fullmatch('{' + ccode_pattern + r'(( \| | & )' + ccode_pattern + ')+}')

# Table and term headers
df.loc[istermheader, 'rowtype'] = 'term header'
df.loc[istableheader, 'rowtype'] = 'table header'
df.loc[ismetaheader, 'rowtype'] = 'metagroup header'
df.loc[isrowheader, 'rowtype'] = 'row header'
df.loc[isrowsubheader, 'rowtype'] = 'row subheader'
df.loc[iscreditssum, 'rowtype'] = 'credits sum'
# Required courses
df.loc[df.containssum & only_ccode & (contains_credits | creditsvary), 'rowtype'] = 'required course'
# Course groups
df.loc[df.containssum & only_ccodecombos & (contains_credits | creditsvary), 'rowtype'] = 'oneline group'
df.loc[df.containssum & isindented, 'rowtype'] = 'multiline group'
# Credit sums
df.loc[df.containssum & df.rowclass.isin(['plangridsum', 'plangridtotal']), 'rowtype'] = 'credits sum'
# Everything else in degree tables (i.e. tables that contain credit sums)
df.loc[df.containssum & df.rowtype.isna() & (contains_credits | creditsvary), 'rowtype'] = 'other requirement'
df.loc[df.containssum & df.rowtype.isna(), 'rowtype'] = 'unknown'
# Elective groups
df.loc[~df.containssum & only_ccode, 'rowtype'] = 'elective'
df.loc[~df.containssum & only_ccodecombos, 'rowtype'] = 'elective combo'
# Everything else in elective tables (i.e. tables that don't contain credit sums)
df.loc[~df.containssum & df.rowtype.isna(), 'rowtype'] = 'unknown elective'

# ID header heirarchy
hheirarchy = ['rowheader', 'rowsubheader', 'otherheader', 'indentheader']
formatheirarchy = ['allcaps', 'regular', 'allcapsindented', 'regularindented']
headertype = pd.Series([np.nan] * len(isheader))
headertype[isrowheader & ~(istermheader | istableheader)] = 'rowheader'
headertype[isrowsubheader & ~(istermheader | istableheader)] = 'rowsubheader'
headertype[iscolonheader & ~(istermheader | istableheader | isrowheader | isrowsubheader)] = 'otherheader'
headertype[isindentheader & ~(istermheader | istableheader | isrowheader | isrowsubheader)] = 'indentheader'
headertype.fillna('otherheader', inplace=True)  # Leftovers are group headers that don't have any special formatting
formattype = pd.Series([np.nan] * len(isheader))
formattype[df.codecopy.str.isupper() & ~isindented] = 'allcaps'
formattype[~df.codecopy.str.isupper() & ~isindented] = 'regular'
formattype[df.codecopy.str.isupper() & isindented] = 'allcapsindented'
formattype[~df.codecopy.str.isupper() & isindented] = 'regularindented'
headerdf = pd.DataFrame({'headertype': headertype, 'formattype': formattype, 'isheader': isheader, })

# Assign headerlevel based on header type and formating (this determines the groupings for serialization later)
# Levels are 0-3 for allcaps headers, 4-7 for regular headers, 8-11 for indented allcaps, 12-15 for indented regular
df['headerlevel'] = headerdf[isheader].apply(
    lambda x: hheirarchy.index(x.headertype) + formatheirarchy.index(x.formattype) * len(hheirarchy), axis=1)
# Ensure table headers and term headers are the lowest level
df.loc[istermheader, 'headerlevel'] = -1
df.loc[istableheader, 'headerlevel'] = -3
# Creditsums aren't headers but they act as one in the heirarchy (they represent a complete division in the table)
df.loc[iscreditssum, 'headerlevel'] = -2

# Row after a metaheader must be a header for another group, or a comment
nextrowisnotheader = ismetaheader & (
        only_ccode | only_ccodecombos | istermheader | ismetaheader | istableheader | iscreditssum).shift(-1)
ismetaheader[nextrowisnotheader] = False

# ID metagroup starts (i.e. the metagroup headers)
df['metagroup'] = ismetaheader.cumsum()
df.loc[~ismetaheader.groupby(df.metagroup).transform('first').fillna(False), 'metagroup'] = np.NaN
if not df.loc[df.groupby('metagroup').code.transform('count') < 2, 'metagroup'].empty:
    raise Exception('theres a metagroup with no groups')
groupwordspresent = df.codecopy.str.findall(listtopattern(groupwords), flags=re.IGNORECASE)
groupwordspresent = groupwordspresent.apply(lambda x: list(set([string.rstrip('s').lower() for string in x])))
metaheadergroupname = groupwordspresent.groupby(df.metagroup).transform('first')
metaheadergroupname[metaheadergroupname.isna()] = pd.Series(
    [[]] * metaheadergroupname.isna().sum()).values  # sets nan as []
metasubheaderintersection = groupwordspresent.apply(set) - (
        groupwordspresent.apply(set) - metaheadergroupname.apply(set))
metaheadermatch = metasubheaderintersection.apply(len).ne(0)

# Metagroups must have a metaheader, followed by the first group header, then the first group, then the 2nd g. header...
# Group must have matching group word on the first line after the metaheader (i.e. 'group', 'list', 'field')
firstheadermatches = metaheadermatch.groupby(df.metagroup.fillna(-1)).transform(lambda x: x.iloc[1])

# Group must be matched more than once (can't be a group requirement with just one group)
groupismatched = firstheadermatches & metaheadermatch.groupby(df.metagroup.fillna(-1)).transform(
    lambda x: sum(x[1:]) > 1)

# Determine if metaheaders for unmatched groups are not metaheaders
# Row after metaheader must be header
nextisheader = df.headerlevel.groupby(df.metagroup.fillna(-1)).transform(lambda x: x.iloc[1]).notna()

# Must at least 2 groups, all with headers that match the first one's text formatting
nextlinehlevel = df.headerlevel.groupby(df.metagroup.fillna(-1)).transform(lambda x: x.iloc[1])
nextlinehascredits = contains_credits.groupby(df.metagroup.fillna(-1)).transform(lambda x: x.iloc[1])
hlevelmatch = nextlinehlevel == df.headerlevel
hcreditsmatch = contains_credits == nextlinehascredits
headermatch = hlevelmatch & hcreditsmatch & df.headerlevel.notna()

# First line can't be a sub-metaheader. This is used so secondheadermatch returns false for missing secondheaderindex's
headermatch.iloc[0] = False
secondheaderindex = isheader.groupby(df.metagroup.fillna(-1)).transform(
    lambda x: x[2:].loc[x].index[0] if x[2:].any() else 0)
secondheadermatch = headermatch.iloc[secondheaderindex].reset_index(drop=True)

# Get rid of non-matching metaheaders and ungroup their groups
ismetaheader.loc[~groupismatched & (~nextisheader | ~secondheadermatch)] = False
df.loc[~ismetaheader.groupby(df.metagroup).transform('first').fillna(False), 'metagroup'] = np.NaN

# Determine where metagroups end
# Find where the indentation of the group changes from indented to not indented
groupisindented = isindented.groupby(df.metagroup).transform(lambda x: x[~isheader].iloc[0])
# Backup option if there's no matching group word (metagroup ends at the next header that has a lower level)
islowerlevel = nextlinehlevel > df.headerlevel

# Regroup metagroup with end of metagroups
metagroupindicators = pd.Series([np.nan] * len(isheader))
metagroupindicators[groupismatched & ~groupisindented] = ismetaheader | (
        hlevelmatch & ~metaheadermatch) | islowerlevel | iscreditssum
metagroupindicators[groupismatched & groupisindented] = ismetaheader | (
        hlevelmatch & ~metaheadermatch) | islowerlevel | (~isheader & ~isindented) | iscreditssum
metagroupindicators[~groupismatched & ~groupisindented] = ismetaheader | islowerlevel | iscreditssum
metagroupindicators[~groupismatched & groupisindented] = ismetaheader | islowerlevel | (
        ~isheader & ~isindented) | iscreditssum
df['metagroupindicators'] = metagroupindicators
df['metagroup'] = metagroupindicators.cumsum()
df.loc[df.metagroup.groupby(df.metagroup).transform('count') == 1, 'metagroup'] = np.nan
df.loc[~ismetaheader.groupby(df.metagroup).transform('first').fillna(False), 'metagroup'] = np.NaN
endofmetagroup = pd.Series([False] * len(isheader))
endofmetagroup.loc[df.groupby('metagroup').tail(1).index] = True
endofmetagroup = endofmetagroup.shift(1)

# ID the inner groups for each metagroup
innergroupindicators = pd.Series([False] * len(isheader))
innergroupindicators[groupismatched] = ismetaheader | endofmetagroup | (metaheadermatch & ~ismetaheader) | iscreditssum
innergroupindicators[~groupismatched & groupisindented] = ismetaheader | endofmetagroup | (
        metaheadermatch & ~ismetaheader) | iscreditssum | (~isheader & ~isindented)
innergroupindicators[~groupismatched & ~groupisindented] = ismetaheader | endofmetagroup | (
        metaheadermatch & ~ismetaheader) | iscreditssum
df['innergroup'] = innergroupindicators.cumsum()
df.loc[df.innergroup.groupby(df.innergroup).transform('count') == 1, 'innergroup'] = np.nan
df.loc[df.metagroup.isna() | ismetaheader, 'innergroup'] = np.NaN
isinnergroupheader = pd.Series([False] * len(isheader))
isinnergroupheader.loc[df.innergroup.groupby(df.innergroup).head(1).index] = True
isinnergroupheader.loc[0] = False
df.drop(columns=['metagroup', 'metagroupindicators', 'innergroup'], inplace=True)

# Reclassify headers based on the new info about what's a metaheader and what's not
df.loc[isinnergroupheader, 'rowtype'] = 'group header'
isheader = isheader | ismetaheader | isinnergroupheader

# Reassign header heirarchy
headerdf = pd.DataFrame({'headertype': headertype, 'formattype': formattype, 'isheader': isheader})
df['headerlevel'] = headerdf[isheader].apply(
    lambda x: hheirarchy.index(x.headertype) + formatheirarchy.index(x.formattype) * len(hheirarchy), axis=1)
df.loc[istermheader, 'headerlevel'] = -1
df.loc[iscreditssum, 'headerlevel'] = -2
df.loc[istableheader, 'headerlevel'] = -3
# Implied inner group headers need to be higher than metagroup header (but not higher than ones formatted differently)
df.loc[isinnergroupheader, 'headerlevel'] = df.headerlevel + .5

# Assign headercodes for credits requirements in credits column
df.credits = df.credits.replace(' ', '')
creditsreqs = ('_' + df.credits.str.extract(r'(\d\d?(?:-\d\d?)?)') + '_credits_').fillna('')
df['headercodes'] = df.headercodes + ' ' + creditsreqs.iloc[:, 0]                   # append creditsreq to headercodes
df.headercodes = df.headercodes.str.replace('  +', ' ', regex=True).str.strip()
df.headercodes.fillna('', inplace=True)
df.headercodes = df.headercodes.apply(lambda x: ' '.join(list(set(x.split()))))     # remove duplicate headercodes

df['endofindent'] = isendofindent & ~isheader

# Classify based on whether requirement is defined or not
df['unknownreq'] = ~(df.headerlevel.notna() | only_ccode | only_ccodecombos)

# Delete credits requirements from creditsums so they are removed in the serializer
df.loc[iscreditssum, 'headercodes'] = ''
# Get rid of singular groups
df = df[df.id.groupby(df.id).transform(lambda x: len(x)) != 1].reset_index(drop=True)

df.to_pickle('degreesorganized.pkl')
# v(df.loc[sorted(sample(df.index.to_list(), k=20))])
