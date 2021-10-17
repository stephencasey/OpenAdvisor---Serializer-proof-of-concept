from listtopattern import listtopattern
import re

reqcode_pattern = r'_\d\d?\d?(?:-\d\d?\d?)?_[a-z_]+_(?<!__)'
groupwords = ['groups?', 'concentrations?', 'lists?', 'tracks?', 'options?', 'subfields?',
              'fields', 'areas', 'course groups?']
coursewords = ['courses?', 'classes']
creditswords = ['credits?', '(credit|semester) hours?', 'hours?', ]
twowords = ['one pair of', 'both']
fourwords = ['two pairs of']
perwords = ['from each', 'from every']
fromwords = ['belonging to', 'in']
labwords = ['labs?', 'laboratory']
maxwords = ['not? more than', 'max(imum)?( of)?', 'as (many|much) as', 'at most', 'up to',
            'may( choose| select)?']  # Todo: test to make sure 'may' isn't too general
upperdivwords = ['3000?-? or 4000?-? ?level', 'upper-? ?level', 'upper ?-? ?division']


def req_encode(series):
    """Named-entity Recognition:
    Converts numerical requirements within a series of strings to code (eg. _3_credits_, _2_courses_per_group_)"""

    # Check that special characters aren't present
    if series.str.contains('[¥ß§Æ¿Ø]').any():
        raise Exception('Special characters are present in the code column')

    # Replace synonyms
    series = series.str.replace(listtopattern(coursewords), 'courses', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(groupwords), 'groups', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(creditswords), 'credits', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(twowords), 'two', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(fourwords), 'four', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(perwords), 'per', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(fromwords), ' from ', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(labwords), 'labs', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(maxwords), 'max', regex=True, flags=re.IGNORECASE)
    series = series.str.replace(listtopattern(upperdivwords), 'upperdiv', regex=True, flags=re.IGNORECASE)

    # Convert number words to digits
    numbers = [r'(?i)\bone\b', r'(?i)\btwo\b', r'(?i)\bthree\b', r'(?i)\bfour\b', r'(?i)\bfive\b', r'(?i)\bsix\b',
               r'(?i)\bseven\b', r'(?i)\beight\b', r'(?i)\bnine\b', r'(?i)\bten\b', r'(?i)\beleven\b',
               r'(?i)\btwelve\b', r'(?i)\bthirteen\b', r'(?i)\bfourteen\b', r'(?i)\bfifteen\b', r'(?i)\bsixteen\b',
               r'(?i)\bseventeen\b', r'(?i)\beighteen\b', r'(?i)\bnineteen\b', r'(?i)\btwenty\b', r'(?i)\bthirty\b']
    digits = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19',
              '20', '30']
    series = series.replace(numbers, digits, regex=True)
    # Fix number ranges so they're hyphenated
    series = series.str.replace(r'\b(\d\d?) ?(?:-|to) ?(\d\d?)\b', r'\1-\2', regex=True)

    # Get rid of course and credit values that merely reference the total number of options in the group
    noncodewords = [r'(of|from) the following', r'the']  # Todo: test to make sure 'the' isn't too general
    series = series.str.replace(listtopattern(noncodewords) + r' \d\d?\b( (credits|courses|groups))?', '', regex=True,
                                flags=re.IGNORECASE)

    # Get rid of noun keywords immediately followed by numbers (eg. group 1, lab 4, course 3)
    series = series.str.replace(r'\b(groups|labs|courses) \d\d?:?\b', '', regex=True)

    # Remove words that come in between keywords and numbers, and keywords and modifiers
    # First convert keywords to unique characters
    series = series.str.replace(r'\bcredits\b', '¥', regex=True)

    # Labs and other coursetypes need be ID'd before courses so 'labs' gets moved next to the number
    series = series.str.replace(r'\blabs\b', 'ß', regex=True)
    series = series.str.replace(r'\bcourses\b', 'Æ', regex=True)
    series = series.str.replace(r'\bgroups\b', '¿', regex=True)
    series = series.str.replace(r'\bupperdiv\b', 'Ø', regex=True)
    series = series.str.replace(r'\bper\b', '§', regex=True)

    # Make sure to only move keywords if there isn't another keyword between it and the number
    series = series.str.replace(r'\b(?:(\d\d?\d?) )([^()\d¥ß§Æ¿]*?)¥', r'\1 ¥ \2', regex=True)
    # Note that course can be between num and lab
    series = series.str.replace(r'\b(?:(\d\d?) )([^()\d¥ß§¿]*?)ß', r'\1 ß \2', regex=True)
    series = series.str.replace(r'\b(?:(\d\d?) )([^()\d¥ß§Æ¿]*?)Æ', r'\1 Æ \2', regex=True)
    series = series.str.replace(r'\b(?:(\d\d?) )([^()\d¥ß§Æ¿]*?)¿', r'\1 ¿ \2', regex=True)
    series = series.str.replace(r'\b(?:(\d\d?\d?) )([^()\d¥ß§Æ¿]*?)Ø', r'\1 Ø \2', regex=True)
    series = series.str.replace(r'§ ([^\d¥()ß§Æ¿]*?)¿', r'§ ¿ \1', regex=True)

    # Convert symbols back to words
    series = series.str.replace('¥', 'credits', regex=False)
    series = series.str.replace('ß', 'labs', regex=False)
    series = series.str.replace('Æ', 'courses', regex=False)
    series = series.str.replace('¿', 'groups', regex=False)
    series = series.str.replace('Ø', 'upperdiv', regex=False)
    series = series.str.replace('§', 'per', regex=False)
    series = series.str.replace('  +', ' ', regex=True)
    series = series.replace(' :', ':', regex=False)

    # Convert numbers followed by keywords to headercodes
    series = series.str.replace(r'\b(\d\d?)( |-)credits\b', r'_\1_credits_', regex=True)
    series = series.str.replace(r'\b(\d\d?)( |-)courses\b', r'_\1_courses_', regex=True)
    series = series.str.replace(r'\b(\d\d?)( |-)labs\b', r'_\1_labs_', regex=True)
    series = series.str.replace(r'\b(\d\d?)( |-)groups\b', r'_\1_groups_', regex=True)
    # Convert any remaining number dashes ahead of headercodes (indicates a credit range)
    series = series.str.replace(r'\b(\d\d?)-_(\d\d?_[a-z]+_)', r'_\1-\2', regex=True)
    # Todo: Convert implied singular keywords to headercodes (e.g. Choose one:)

    # Move and append modifiers to headercodes
    series = series.str.replace(r'([a-z]_)\b([^_]*)per groups\b', r'\1per_group_ \2', regex=True)
    series = series.str.replace(r'([a-z]_)\b([^_0-9]*)upperdiv\b', r'\1upperdiv_ \2', regex=True)
    series = series.str.replace(r'\bmax (_\d\d?_)(credits_|courses_|credits_upperdiv_)\b', r'\1\2max_', regex=True)
    series = series.str.replace(r'\b(_\d\d?_)(credits_|courses_|credits_upperdiv_)\b([^_.]*?)\bmax\b', r'\1\2max_\3',
                                regex=True)
    # ID implicitly defined modifiers (missing 'courses' or 'credits') using the closest prior keyword
    series = series.str.replace(r'(credits_|courses_)\b([^_\d]*\b)(\d\d?) upperdiv\b', r'\1\2_\3_\1upperdiv_',
                                regex=True)
    series = series.str.replace(r'(credits_|courses_)\b([^_\d]*\b)(\d\d?) max\b', r'\1\2_\3_\1max_', regex=True)
    # Left over 'max' + digits should be references to courses requirement
    series = series.str.replace(r'\A([^_]*)\bmax (\d\d?)\b([^_]*)\Z', r'\1_\2_courses_max_ \3', regex=True)
    return series
