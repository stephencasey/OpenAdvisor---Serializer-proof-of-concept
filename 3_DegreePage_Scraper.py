""" Webscraper and organizer for collecting all html elements from degree requirement pages.

This script scrapes the degree requirement page for all relevant html elements and organizes some of the data too. It's
chief purpose is to collect the html tables that contain all the degree requirements and convert each table to a
dataframe, however it also captures information from their associated headers and other sections (such as tables and
paragraphs that that contain superscript definitions). Their headers (including all superceding headers), their
sibling's headers, and superscript info is all saved with the table in a dataframe, along with other key info.

The input is a dataframe produced in the first script of this series and the output is a dataframe containing the
tables and their associated data.

Note: Within the html of these catalogs each important element typically has a unique class ID. Four year plan tables
have the class 'sc_plangrid', generic tables that contain courses are 'sc_courselist', footnotes containing superscript
definitions are 'sc_footnotes'. Within the tables, credits have the table header 'Units', course codes are 'Code', etc.

3rd party modules needed include Selenium, Pandas, and BeautifulSoup4.
"""

from verticalprinter import v
from random import sample
from selenium import webdriver
import time
import re
import pandas as pd
from bs4 import BeautifulSoup as bs
import unicodedata

# Open dataframe from script 1
urldf = pd.read_pickle('degreesites.pkl')

# Set regex definitions
htmltext_re = re.compile(r'(?<=>)[^<]+')
sscript_pattern = r'(?<=_SUPERSCRIPT_).+?(?=_)'     # sscript is abbreviation for superscript
tablerowhtml_re = re.compile(r'<tr.+?</tr>', flags=re.DOTALL)
tablerowclass_pattern = '(?:class=")([^ "]*)'

driver = webdriver.Chrome(executable_path='C:/PythonExtraPath/chromedriver.exe')
htmldf = pd.DataFrame()
for pagei, page in urldf.iterrows():
    url = page.link
    driver.get(url)
    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);var lenOfPage=document.body.scrollHeight;return lenOfPage;")
    time.sleep(.3)
    sitehtml = driver.page_source

    # Replace html superscripts with plain text code so they don't lose their superscript designation when decoded
    for superscript in re.findall(r'(?<=<sup>)[^<]+', sitehtml):
        if ',' in superscript:  # For comma separated lists of superscripts
            replacements = ' _SUPERSCRIPT_' + '_ _SUPERSCRIPT_'.join(re.findall(r'[^ ,]+', superscript)) + '_'
            sitehtml = re.sub(r'<sup>.+?</sup>', replacements, sitehtml, count=1)
        elif ' ' in superscript:  # For space separated lists of superscripts (this is rare)
            replacements = ' _SUPERSCRIPT_' + '_ _SUPERSCRIPT_'.join(re.findall(r'[^ ]+', superscript)) + '_'
            sitehtml = re.sub(r'<sup>.+?</sup>', replacements, sitehtml, count=1)
        else:
            sitehtml = re.sub(r'<sup>.+?</sup>', (' _SUPERSCRIPT_' + superscript + '_'), sitehtml, count=1)

    # Remove invisible superscripts (these are errors from the webdeveloper)
    sitehtml = re.sub(r'_SUPERSCRIPT_ *_', '', sitehtml)

    soup = bs(sitehtml, features='lxml')

    siblings = []
    tabnumber = []
    # Extract elements from main page content then loop through each sub-element
    pagecontent = soup.find_all(None, {'class': 'page_content tab_content'})
    if not pagecontent:       # Not a page with sub-pages on tabs
        pagecontent = soup.find_all(None, {'class': 'page_content'})
    # Drill down from page -> tabs -> children -> grandchildren -> greatgrandchildren and append elements
    for tabi, tabpage in enumerate(pagecontent):
        for child in tabpage.children:
            if child.name == 'div':         # TODO: Generalize to n-levels
                for grandchild in child.children:
                    if grandchild.name == 'div':
                        for ggchild in grandchild.children:
                            if str(ggchild) != '\n':
                                siblings.append(str(ggchild))       # Save each html element
                                tabnumber.append(tabi)              # Save the tab number too
                    elif str(grandchild) != '\n':
                        siblings.append(str(grandchild))
                        tabnumber.append(tabi)
            elif str(child) != '\n':
                siblings.append(str(child))
                tabnumber.append(tabi)
    if not siblings:
        continue

    # Save elements to a dataframe
    siblingsdf = pd.DataFrame({'tabnumber': tabnumber, 'html': siblings})

    # Extract html class (use html class name for tables and html tagname for all other elements)  todo: clarify naming
    siblingsdf['htmlclass'] = siblingsdf.html.str.extract('(?<=<)(.+?)(?=( |>))')[0]
    tableclass = siblingsdf.html.str.extract('(?:class=")(.+?)(?:")', expand=False).str.split().str[0]
    siblingsdf.loc[siblingsdf.htmlclass.eq('table'), 'htmlclass'] = tableclass
    siblingsdf = siblingsdf[siblingsdf.htmlclass.ne('hr/')]
    siblingsdf = siblingsdf[siblingsdf.htmlclass.notna()]

    # Extract header importance
    siblingsdf['h'] = siblingsdf.htmlclass.str.extract(r'(?<=h)([1-6])(?=\Z)')
    siblingsdf.loc[siblingsdf.htmlclass.eq('pre'), 'h'] = 7         # Preformatted text is sometimes table header
    siblingsdf.loc[:, 'h'].fillna('8', inplace=True)                # Anything above 7 is not a header
    siblingsdf.loc[:, 'h'] = pd.to_numeric(siblingsdf.loc[:, 'h'])
    siblingsdf['string'] = siblingsdf.html.apply(lambda x: ''.join(htmltext_re.findall(x)))

    # Assign corresponding headers to each element heirarchicaly and save as headertext
    siblingsdf['headertext'] = ''
    for h in range(1, 8):
        if h in siblingsdf.h.values:
            for starti in siblingsdf.h[siblingsdf.h == h].index:
                if ~(siblingsdf.h.loc[starti + 1:] <= h).any():
                    stopi = max(siblingsdf.index)
                else:
                    stopi = siblingsdf.loc[starti + 1:, 'h'][siblingsdf.h.loc[starti + 1:] <= h].index[0] - 1
                siblingsdf.loc[starti:stopi, 'headertext'] = siblingsdf.headertext + siblingsdf.string[starti] + ' : '
    siblingsdf.headertext = siblingsdf.headertext.str.strip(' : ')

    # Delete header elements (their text is saved in headertext)
    siblingsdf = siblingsdf.loc[siblingsdf.h.eq(8)].reset_index(drop=True)
    siblingsdf.drop(columns="h", inplace=True)

    # Change htmlclass for elemnents to 'sc_footnotes' if they contain superscript definition   todo: clarify naming
    siblingsdf.loc[siblingsdf.string.str.match('_SUPERSCRIPT_'), 'htmlclass'] = 'sc_footnotes'

    # Merge adjacent text blocks with matching headers (but don't merge for tables)
    dontmerge = siblingsdf.html.str.match('<table ')
    groupedbyheader = (
                siblingsdf.headertext.ne(siblingsdf.headertext.shift()) | dontmerge | dontmerge.shift(1)).cumsum()
    siblingsdf = siblingsdf.groupby(groupedbyheader, as_index=False).agg(
        {'tabnumber': 'first', 'html': ' /n '.join, 'htmlclass': 'first', 'string': ' ; '.join, 'headertext': 'first'})

    # Get headers of siblings that precede tables (may contain degree name)
    siblingsdf.loc[
        ~siblingsdf.htmlclass.isin(['sc_plangrid', 'sc_courselist']), 'siblingheaders'] = siblingsdf.headertext
    tablegroups = siblingsdf[::-1].siblingheaders.isna().cumsum()[::-1]
    siblingsdf.siblingheaders = siblingsdf.siblingheaders.groupby(tablegroups).transform(lambda x: ' : '.join(x[:-1]))

    # Assign superscript definitions to the tables that reference them
    siblingsdf.loc[siblingsdf.htmlclass.eq('sc_footnotes'), 'sscripts'] = siblingsdf.string
    siblingsdf.loc[siblingsdf.html.str.match('<p> _SUPERSCRIPT_'), 'sscripts'] = siblingsdf.string
    siblingsdf.sscripts = siblingsdf.sscripts.bfill()     # Sometimes definitions are listed under a later element
    siblingsdf.sscripts = siblingsdf.sscripts.ffill()     # or before the element
    has_sscripts = siblingsdf.html.str.contains(sscript_pattern) | siblingsdf.headertext.str.contains(sscript_pattern)
    needs_sstable = has_sscripts & siblingsdf.htmlclass.ne('sc_footnotes')
    # if (siblingsdf.sscripts.isna() & siblingsdf.htmlclass.isin(['sc_courselist', 'sc_plangrid']) & needs_sstable).any():
    #     print('There is a table that contains superscripts but does not have superscript definitions. Ignore? (y/n)')
    #     if input() != 'y':
    #         raise Exception('Terminated by User')

    # Remove definitions if the table doesn't have any superscripts
    siblingsdf.loc[~needs_sstable & siblingsdf.htmlclass.isin(['sc_courselist', 'sc_plangrid']), 'sscripts'] = ''
    siblingsdf = siblingsdf[siblingsdf.htmlclass.ne('sc_footnotes')]
    if siblingsdf.empty:
        continue
    siblingsdf = siblingsdf.reset_index(drop=True)

    # Assign all the page-wide properties
    siblingsdf = siblingsdf.assign(link=url)
    siblingsdf = siblingsdf.assign(pagenumber=pagei)
    siblingsdf.loc[:, ['program', 'degree', 'school']] = pd.concat([page] * siblingsdf.index.size,
                                                                   axis=1, ignore_index=True).T
    # Extract the page title (it's usually the degree name)
    if soup.find(None, {'id': 'page-title'}) is None:
        if soup.find(None, {'class': 'page-title'}) is None:
            siblingsdf['pagetitle'] = soup.find(None, {'class': 'page-header'}).text
        else:
            siblingsdf['pagetitle'] = soup.find(None, {'class': 'page-title'}).text
    else:
        siblingsdf['pagetitle'] = soup.find(None, {'id': 'page-title'}).text

    # Concatenate the df's for all pages
    htmldf = pd.concat([htmldf, siblingsdf])
driver.close()

# Extract just the tables that contain degree requirements
isdegreetable = htmldf.htmlclass.eq('sc_courselist') | htmldf.htmlclass.eq('sc_plangrid')
tables = htmldf.loc[isdegreetable, ['degree', 'headertext', 'siblingheaders', 'sscripts', 'tabnumber', 'pagenumber',
                                    'html', 'htmlclass', 'link', 'pagetitle']].reset_index(drop=True)


# At this point the tables are still just html
# Convert each individual html table to a dataframe, which is then nested as a single element in tablesseries
tablesseries = tables.html.apply(lambda x: pd.read_html(x)[0])
tablesseries.rename('tables', inplace=True)
tablesseries = tablesseries.apply(lambda x: x.fillna(''))

# Remove unicode junk
tablesseries = tablesseries.apply(lambda x: x.applymap(lambda y: unicodedata.normalize('NFKC', str(y).strip(' \n')).
                                                       encode('ascii', 'ignore').decode('utf-8')))
# Mark current rows as not being a table header, then move column index to row and mark those as table headers
tablesseries = tablesseries.apply(lambda x: x.assign(headerflag=False))

# Todo: Use existing html column headers instead of assigning them
# # Get rid of non-standard tables (like courseplans with multiple courses/semsters sharing a row)
# columnheaders = tablesseries.apply(lambda x: x.columns)
# hascode = columnheaders.apply(lambda x: 'Code' in x)
# hastitle = columnheaders.apply(lambda x: 'Title' in x)
# hascredits = columnheaders.apply(lambda x: 'Units' in x) | columnheaders.apply(lambda x: 'Credits' in x)
# tablesseries = tablesseries[hascode & hastitle & hascredits]
# tables = tables[hascode & hastitle & hascredits]

tablesseries = tablesseries.apply(lambda x: x.T.reset_index().T.reset_index(drop=True))
# Assign column names
# 'coregroup' is an optional column sometimes present in course tables (represents gen ed groups)
tablesseries.apply(lambda x: x.columns)
tablesseries.apply(lambda x: x.insert(2, "coregroup", '') if len(x.columns) == 4 else None)
tablesseries.apply(lambda x: x.set_axis(['code', 'title', 'coregroup', 'credits', 'headerflag'], axis=1, inplace=True))
# Move column indexes to rows and mark with headerflag
tablesseries = tablesseries.apply(lambda x: x.assign(headerflag=x.headerflag.ne(False), axis=1))


# Make new df containing each individual table and their table-wide info
tabledf = pd.concat([tablesseries, tables], axis=1)
tabledf = tabledf.assign(id=list(range(len(tables))))
# Broadcast table info from other rows of tabledf into the nested dataframes in the first column
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(degree=x.degree), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(pagetitle=x.pagetitle), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(headertext=x.headertext), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(siblingheaders=x.siblingheaders), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(tabnumber=x.tabnumber), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(pagenumber=x.pagenumber), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(superscripts=x.sscripts), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(htmlclass=x.htmlclass), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(link=x.link), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(id=x.id), axis=1)

# Convert entire table html into html of individual rows              *Accomodates for missing table headers*
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(
    html=[''] * (len(x.tables) - len(tablerowhtml_re.findall(x.html))) + tablerowhtml_re.findall(x.html)), axis=1)
tabledf.tables = tabledf.apply(lambda x: x.tables.assign(rowclass=x.tables.html.str.extract(tablerowclass_pattern)),
                               axis=1)

# Explode series containing dataframes into one big dataframe
df = pd.concat(tabledf.tables.to_list())

# Delete blank rows
df = df.loc[df.html.str.contains(r'(?<=>)[^<]+'), :]
df.reset_index(drop=True, inplace=True)

df.to_pickle('degreetables.pkl')
v(df.loc[sorted(sample(df.index.to_list(), k=20))])         # print a randomized selection
