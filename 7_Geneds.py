"""Links unclassified requirements with hyperlinks to the tables located at those hyperlinks

This script takes unknown requirements from script 6 of this series and cross-references them to any tables contained
in their hyperlinks (if present). It also takes broken hyperlink fragments and finds suitable corrections so they
are associated with the correct tables (these broken fragments are surprisingly common).

The input is the dataframe from series 6 and the output is a dataframe containing the unorganized reference tables. The
output must then be run through script 6 again before moving on to script 8 (not ideal but works for now).

3rd party modules needed are Pandas, Selenium (with Chromedriver), BeautifulSoup4, TheFuzz, and Unicodedata.
"""

import pandas as pd
from selenium import webdriver
import time
from bs4 import BeautifulSoup as bs
from thefuzz import process
from thefuzz import fuzz
import re
import unicodedata
from verticalprinter import v

tablerowhtml_re = re.compile(r'<tr.+?</tr>', flags=re.DOTALL)
tablerowclass_pattern = '(?:class=")([^ "]*)'
'(?<=class=")(.+?)(?=")'
degreedf = pd.read_pickle('degreesorganized.pkl')

baseurl = degreedf.link[0][:degreedf.link[0].index('.edu')+4]
degreedf['links'] = degreedf.html.str.findall('(?<=<a href=")[^"]+(?=")')
# Fix fragments that are on the degree page so they include the entire directory
startswithhash = degreedf.links.apply(lambda x: sum([bool(re.match('#', string)) for string in x]) != 0).fillna(False)
degreedf['pageurl'] = degreedf.link.apply(lambda x: x[x.index('.edu')+4:])
degreedf.loc[startswithhash, 'links'] = degreedf.apply(lambda x: [x.pageurl + '/' + string for string in x.links],
                                                       axis=1)

# List of all unique links
alllinks = list(set([x for sublist in degreedf.links for x in sublist]))

driver = webdriver.Chrome(executable_path='C:/PythonExtraPath/chromedriver.exe')
siblings = []
linklist = []
oldlinklist = []
# Loop through each link, update it if broken, scrape page elements, and append relevant sibling elements
for link in alllinks:
    oldlink = link
    if '.edu' in link:
        url = link
    else:
        url = baseurl+link
    driver.get(url)
    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);var lenOfPage=document.body.scrollHeight;return lenOfPage;")
    time.sleep(.3)
    sitehtml = driver.page_source
    soup = bs(sitehtml, features='lxml')
    # Get a list of all 'a' tags (links)
    taglist = [tag['name'] for tag in soup.select('a[name]')]
    if '#' in url:    # Hashtag indicates a fragment
        groupheaderid = url[url.rindex('#')+1:]
        linkdirectory = link[:link.rindex('#')+1]
        headerchild = soup.find(None, {'name': groupheaderid})
        # Fix broken links (links to right page but wrong fragment)
        if headerchild is None:      # Means link is broken
            # Find matches using fuzzy matching (not ideal but works in lieu of more advanced NLP)
            match = process.extract(groupheaderid, taglist, scorer=fuzz.token_set_ratio, limit=1)
            if match[0][1] >= 60:        # This can be tweaked but 60 seems to provide very good results
                fixedheaderid = match[0][0]
                link = linkdirectory + fixedheaderid
                headerchild = soup.find(None, {'name': fixedheaderid})
            else:
                raise Exception('Cant find a good match for the url fragment')

        # Figure out whether the group header is in the element or in one of it's next siblings
        groupheader = headerchild.parent
        if groupheader.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            groupheader = headerchild.parent.parent
            if groupheader.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                groupheader = headerchild.parent.parent.parent
                if groupheader.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    groupheader = headerchild.nextSibling
                    if groupheader.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        groupheader = headerchild.nextSibling.nextSibling
                        if groupheader.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            raise Exception('Cant find header associated with fragment')
        siblings.append(str(groupheader))           # Groupheader is the first sibling element
        linklist.append(link)                       # Linklist contains the fixed links
        oldlinklist.append(oldlink)                 # Oldlinklist contains the original links
        headerlevel = int(groupheader.name[1])      # Headerlevel is used to determine the group of siblings
        for sibling in groupheader.next_siblings:
            if sibling.name is None:
                continue
            if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                if int(sibling.name[1]) <= headerlevel:     # If you reach a lower-level header, no more siblings exist
                    break
            elif sibling.name == 'div':                     # Drill down into div to get more sub-elements
                for child in sibling.children:
                    if child.name is None:
                        continue
                    if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        if int(sibling.name[1]) <= headerlevel:
                            break
                    elif child.nam == 'div':
                        raise Exception('Increase the number of times you can drill down into divs')
                    siblings.append(str(child))
                    linklist.append(link)
                    oldlinklist.append(oldlink)
            else:
                siblings.append(str(sibling))
                linklist.append(link)
                oldlinklist.append(oldlink)
driver.close()

# Make a dataframe of these elements and links and organize/clean up
df = pd.DataFrame({'flink': linklist, 'oldlink': oldlinklist, 'html': siblings})        # 'flink' is fragment link
if not df.empty:
    # Get html class and extract all sc_courselists     Todo: clean up naming scheme like in script 3
    df['htmlclass'] = df.html.str.extract('(?<=<)(.+?)(?=( |>))')[0]
    is_table = df.htmlclass.eq('table')
    df.loc[is_table, 'htmlclass'] = df.html.str.extract('(?<=class=")(.+?)(?=")').iloc[:, 0].str.split().str[0]
    df = df[df.groupby('flink').htmlclass.transform(lambda x: (x == 'sc_courselist').any())]
    df = df[df.htmlclass.eq('sc_courselist')]

    tablesseries = df.html.apply(lambda x: pd.read_html(x)[0])      # Unpack tables into an exploded series
    tablesseries.rename('tables', inplace=True)
    tablesseries = tablesseries.apply(lambda x: x.fillna(''))
    tablesseries = tablesseries.apply(lambda x: x.applymap(lambda y: unicodedata.normalize('NFKC', str(y).strip(' \n')).
                                                           encode('ascii', 'ignore').decode('utf-8')))
    # Mark current rows as not being a table header, then move column index to row and mark those as table headers
    tablesseries = tablesseries.apply(lambda x: x.assign(headerflag=False))
    tablesseries = tablesseries.apply(lambda x: x.T.reset_index().T.reset_index(drop=True))
    tablesseries.apply(lambda x: x.insert(2, "coregroup", '') if len(x.columns) == 4 else None)
    tablesseries.apply(lambda x: x.set_axis(['code', 'title', 'coregroup', 'credits', 'headerflag'], axis=1,
                                            inplace=True))
    tablesseries = tablesseries.apply(lambda x: x.assign(headerflag=x.headerflag.ne(False), axis=1))
    tabledf = pd.concat([tablesseries, df], axis=1)

    # Assign ID's for each unique link (not oldlink) starting at 9000 (so they are distinct to requirement df id's)
    tabledf = tabledf.sort_values(by='flink')
    istoprow = pd.Series([False]*len(tabledf))
    istoprow.index = tabledf.index
    istoprow.loc[tabledf.flink.groupby(df.flink).head(1).index] = True
    tabledf['id'] = istoprow.cumsum() + 9000
    tabledf = tabledf.assign(id=list(range(len(df))))  # id is a unique number for each table

    # Broadcast tablewide info to tabledf
    tabledf.tables = tabledf.apply(lambda x: x.tables.assign(flink=x.flink), axis=1)
    tabledf.tables = tabledf.apply(lambda x: x.tables.assign(headertext=x.oldlink), axis=1)  # Todo: Fix this workaround
    tabledf.tables = tabledf.apply(lambda x: x.tables.assign(id=x.id), axis=1)
    # Convert entire table html into html of individual rows
    tabledf.tables = tabledf.apply(lambda x: x.tables.assign(
        html=[''] * (len(x.tables) - len(tablerowhtml_re.findall(x.html))) + tablerowhtml_re.findall(x.html)), axis=1)
    tabledf.tables = tabledf.apply(lambda x: x.tables.assign(rowclass=x.tables.html.str.extract(tablerowclass_pattern)),
                                   axis=1)
    # Convert series containing dataframes into one big dataframe and clean up
    geneddf = pd.concat(tabledf.tables.to_list())
    # Make id unique from degree df id's
    geneddf.id = geneddf.id + 9000

    # Fill in blank columns so it processes correctly in script 6
    geneddf['degree'] = 'GENEDS'
    geneddf['siblingheaders'] = ''
    geneddf['superscripts'] = ''
    geneddf['tabnumber'] = ''
    geneddf['pagenumber'] = ''
    geneddf['pagetitle'] = 'GENEDS'
    geneddf['link'] = ''
    geneddf['htmlclass'] = 'sc_courselist'
else:
    geneddf = df

# Open and rename old degreetable   Todo: fix this workaround so script sequence is correct
olddf = pd.read_pickle('degreesorganized.pkl')
olddf.to_pickle('actualdegreesorganized.pkl')
# Save as degreetable
geneddf.to_pickle('degreetables.pkl')

# Now run 6 again, then finally 8
