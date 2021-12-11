""" Webscraper that collects course information from course description pages.

This script is used to scrape all the relevant information about each course from individual course description sites.
This includes the course code, credits, title, requisites, registration information, etc.

The input is one of the dataframes generated in the first script of this series and the output is a dataframe containg
all of the relevant html elements.

Chrome browser is required as a dependency.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
from tabulate import tabulate
from bs4 import BeautifulSoup as bs
import unicodedata
import html2text
h2t = html2text.HTML2Text()
h2t.ignore_links = True
h2t.ignore_emphasis = True
h2t.body_width = 0


# Read dataframe from script 1
sitesdf = pd.read_pickle('coursedescriptionsites.pkl')
courseblocks_df = pd.DataFrame()

s = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=s)

# Loop through each course description page (each page contains an entire department's courses)
for site in sitesdf.itertuples():
    url = site.link
    driver.get(url)
    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);var lenOfPage=document.body.scrollHeight;return lenOfPage;")
    time.sleep(.3)
    sitehtml = driver.page_source
    soup = bs(sitehtml, "html.parser")
    # Courseblock is the html container for each individual course description
    courseblocks = soup.find_all('div', {'class': 'courseblock'})
    for blocki, block in enumerate(courseblocks):
        rowsdf = pd.DataFrame()
        # Elements contains every html element within courseblock
        elements = pd.Series(list(block.children))
        elements = elements[elements != '\n']
        # An html break followed by bold text is likely a header (TODO test if splitting at every break & \n is valid)
        rowsdf['html'] = elements.apply(str).str.split('<br/><strong>').apply(pd.Series).stack().reset_index(drop=True)
        rowsdf = rowsdf.dropna()
        rowsdf['plaintext'] = rowsdf.html.apply(lambda x: unicodedata.normalize('NFKC', h2t.handle(x)).strip('\n'))
        rowsdf = rowsdf.loc[rowsdf.plaintext != '']
        rowsdf = rowsdf.dropna().reset_index(drop=True)
        # Assign unique ID for each course within a page and their associated elements
        rowsdf['blockid'] = blocki
        rowsdf['department'] = site.department
        courseblocks_df = pd.concat([courseblocks_df, rowsdf])
driver.close()

# Block index resets for every block, blockid resets for every department, while df.index doesn't reset
courseblocks_df['blockindex'] = courseblocks_df.index
courseblocks_df.index = courseblocks_df.groupby(['department', 'blockid'], sort=False).ngroup()

# Save and print first 100 entries
courseblocks_df.to_pickle('coursedescriptions.pkl')
print(tabulate(courseblocks_df[['plaintext', 'department']].head(100), headers='keys', tablefmt='psql'))
