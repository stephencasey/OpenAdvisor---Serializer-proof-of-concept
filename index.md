# OpenAdvisor

Series of scripts that scrape, clean, organize, and encode online college catalogs.

## Motivation

For most college students, building a degree plan can be complicated and generally limited to whatever their school’s advisor suggests. Most students don’t realize they may be able to take courses outside of their university at community colleges (locally or online) that give the exact same credit towards their degree for a fraction of the cost, saving them potentially thousands of dollars. Furthermore, determining what courses fit into their degree plans can be overwhelming, much less searching through numerous community colleges websites to build a cohesive degree plan. My intention is to create an app that can provide a user with potential transfer courses for a given degree along with the cost savings estimates.

The first step towards building this app is standardizing college degree and course information from multiple schools into one unified database, and representing them in a form that captures all of their diverse details. Critically, to make this scalable to the roughly 1400 public universities in the US, this process would need to be fully automated with little to no manual coercion of the data. **This project provides a proof-of-concept for an automated degree requirement normalizer and encoder backend.**

The normalized degree requirements are represented as an easy-to-read serialized code that represents all of the individual requirements and their relations. Below is an example:



**Link to original (click to compare):** https://catalog.colostate.edu/general-catalog/colleges/agricultural-sciences/agricultural-biology/agricultural-biology-major/#requirementstext

## Project Strategy & Goals
The majority of online college catalogs are hosted by one of three different course catalog management services. Under-the-hood, catalogs hosted on the same service share many of the same architectures and schemas for HTML class naming, simplifying the process of scraping and organizing their underlying data, despite the apparent differences between each school’s website. The initial goal (and what is presented here) was to build this proof-of-concept for the largest of the catalog management services (CourseLeaf) and apply this to a single state (Colorado) to evaluate the results and gauge scalability for other states and platforms. On average, the code currently parses 89% of degree requirements with less than 3% error. The program has been tested on 6 out of the 8 schools in Colorado that use CourseLeaf, including the two largest universities in the state, representing 55,000 individual degree requirements and 25,000 courses. 

The primary focus in the development of this project was to have the highest degree of automation possible so that it can be eventually scaled up to the rest of the schools that use CourseLeaf. By evaluating the scalability on CourseLeaf, this may also give some indication of applicability to the other platforms as well. In order to achieve scalability without excessive complexity, parsing special cases unique to a school or representing a small fraction of requirements will not be a priority. Rather, other methods will have to be implemented later to accommodate for this, such as crowdsourcing or having an interface for school staff to verify their own data. 

The long-term goal is to have an app that can provide cheaper course alternatives for the majority of those present in a degree. Even if only 50% of the possible alternatives are identified, this can still represent thousands of dollars of savings. Therefore, the goal is to eventually have an app that can identify greater than 70% of transferrable options, with Type-1 error below 5%.

The project is divided in three sections, and each section has a Jupyter notebook devoted to their methods, individual strategies, and code:
1.	Web-scraping and Data Collection
2.	Normalization and Transformation
3.	Integration and Encoding

## Usage
The scripts can be run sequentially using either the bash script, OA_BashDriver.sh, or the python script, OA_PythonDriver.py. The core project (all the scripts excluding script 5) can also be run using the three Jupyter notebooks included in the main directory, or viewed as HTML in the links directly above. 
