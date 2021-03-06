""" Webscraper for generating a list of course description and degree requirement URLs from university catalogs.

This is the first of 8 scripts that scrape, organize, and parse a university's course descriptions and degree
requirements from their online catalog. This works for the majority of universities using a certain company who develops
their online catalogs.

The purpose of this first script is to generate a list of all the possible URLs that contain course descriptions and
degree requirements.

The script inputs an excel file containing a list of example URLs from each school's catalog. The user is prompted to
select which school to run the script for. This will generate a dataframe containing the URLs and basic information
about each individual page (such as school, department, & degree). You may need to change the sleep timer, time.sleep(),
to up to 5 seconds depending on your internet connection speed.

After running this script, run script 2.

Chrome browser is required as a dependency.
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
import unicodedata
import json
from tabulate import tabulate

# Retrieve URLs
mainurlsdf = pd.read_excel('MainURLs.xlsx')
schools = mainurlsdf.loc[::2, 'School'].reset_index(drop=True)
schoolsdf = pd.DataFrame(schools)
schoolsdf.index.name = 'ID'

print(schoolsdf)
print('Enter the ID for the school you want to scrape:')
schoolid = None
while schoolid not in schoolsdf.index:
    schoolid = int(input())
schoolname = schoolsdf.School[schoolid]

coursedescription_urls = mainurlsdf.loc[schoolid*2:schoolid*2+1, 'Course description URLs'].reset_index(drop=True)
degreerequirement_urls = mainurlsdf.loc[schoolid*2:schoolid*2+1, 'Degree requirement URLs'].reset_index(drop=True)


def get_sibling_urls(urls, pickle_name):
    """Generates a dataframe containing all the pages within a site that match the input URLs' directory structure.

    Given two example URL's, this generates a dataframe containing all the sibling pages that have matching directory
    structures. For example, given the example URLs "www.example.com/abc/def/ghi" and "www.example.com/abc/xyz/ghi",
    get_siblings_URLs would match any URL of the form "www.example.com/abc/*/ghi", where "*" is a wildcard directory
    name. The dataframe also returns school, department, program, and degree names for each URL, where applicable, by
    infering via the directories that are shared. The dataframe is then saved as a .pkl file.

    :param urls: Series containing two example URLs
    :param pickle_name: A string representing the filename for the output .pkl file
    :return: None
    """
    # Determine the URL structure
    exampleurl1 = urls[0].strip('/')
    exampleurl2 = urls[1].strip('/')
    examplesplit1 = exampleurl1.split('/')
    examplesplit2 = exampleurl2.split('/')
    splitdf = pd.DataFrame({'e1': examplesplit1, 'e2': examplesplit2})
    # Delete last subdirectories if they match in both examples (likely a fragment)
    splitdf = splitdf.loc[splitdf.e1.ne(splitdf.e2).loc[::-1].cumsum()[::-1].ne(0)]

    # Make a list of the shared parent directories
    directoryi = 0
    parentdirectories = ['']*10                             # Pad list
    for i in range(len(splitdf)):
        if splitdf.e1[i] == splitdf.e2[i]:  # If directory in both example URLs match --> save as shared directory
            parentdirectories[directoryi] = parentdirectories[directoryi] + '/' + splitdf.e1[i]
        else:
            directoryi += 1
    parentdirectories[0] = parentdirectories[0].strip('/')
    parentdirectories = parentdirectories[:directoryi]      # Remove padding
    if directoryi == 1:
        directorynames = ['department']         # Course description url's are only dilineated by department
    elif directoryi == 2:
        directorynames = ['school', 'degree']       # Some degree url's are dilineated by school and degree
    elif directoryi == 3:
        directorynames = ['school', 'program', 'degree']    # Most degree url's are dilineated by all of these
    else:
        raise Exception('check url format')

    # Extract list of all sites that match the structure of the example URL's
    nextdirectoryurllist = ['']
    sitelinks = []
    # Loop through each shared directory, finding matching URL's
    for diri, directory in enumerate(parentdirectories):
        urllist = list(set(nextdirectoryurllist))
        nextdirectoryurllist = []
        for url in urllist:
            url = url + directory
            driver.get(url)
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);var lenOfPage=document.body.scrollHeight;return lenOfPage;")
            time.sleep(.3)      # increase this to 5 seconds if selenium is throwing exceptions
            # Get a list of all elements with a link starting with the matching parent URL
            # hrefstart_index = parentdirectories[0].rindex('.edu')+4
            # hrefstart = url[hrefstart_index:]
            # alllinks = driver.find_elements(By.XPATH, '//a[contains(@href,"' + hrefstart + '")]')
            alllinks = driver.find_elements(By.XPATH, '//a')       # Slower backup option to get all unfiltered links

            for link in alllinks:
                rawlink = link.get_attribute("href")
                if not rawlink:
                    continue
                linkurl = rawlink.strip('/')
                if ('@' in linkurl) or ('#' in linkurl) or ('.pdf' in linkurl):
                    continue
                if '/' not in linkurl:
                    continue
                if linkurl.rindex('/') == len(url):   # If linkurl is child of parent dir, not a grandchild --> append
                    linktitle = link.text.strip(' \n')
                    linktitle = unicodedata.normalize('NFKC', linktitle).encode('ascii', 'ignore').decode('utf-8')
                    if not linktitle:
                        linktitle = link.get_attribute('innerText').strip(' \n')
                        linktitle = unicodedata.normalize('NFKC', linktitle).encode('ascii', 'ignore').decode('utf-8')
                    sitelinks.append({"link": linkurl, directorynames[diri]: linktitle})
                    nextdirectoryurllist.append(linkurl)

    # Save all links and properties to a dataframe
    linksdf = pd.DataFrame(sitelinks)
    # Remove duplicates and keep the longest titles
    linksdf['linklength'] = linksdf.link.str.len()
    linksdf = linksdf.groupby(linksdf.link, as_index=False).apply(lambda x: x.iloc[x.linklength.argmax()])
    linksdf.drop(columns='linklength', inplace=True)
    # Broadcast all properties except degree (sites without a degree name need to be removed)
    linksdf.loc[:, directorynames[:-1]] = linksdf.sort_values('link').loc[:, directorynames[:-1]].ffill()
    linksdf = linksdf.dropna(subset=[directorynames[-1]])
    linksdf = linksdf.sort_values('link')
    linksdf.reset_index(inplace=True, drop=True)

    # Save school name
    with open('schoolname.json', 'w') as outfile:
        json.dump(schoolname, outfile)

    # Print out all the results and save
    print(tabulate(linksdf, headers='keys'))
    linksdf.to_pickle(pickle_name)


s = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=s)

get_sibling_urls(coursedescription_urls, 'coursedescriptionsites.pkl')
get_sibling_urls(degreerequirement_urls, 'degreesites.pkl')

driver.close()
