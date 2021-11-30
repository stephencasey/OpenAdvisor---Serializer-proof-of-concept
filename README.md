# OpenAdvisor
Proof-of-concept for a college catalog encoder

Series of scripts that scrape, clean, organize, and encode online college catalogs.

## Motivation

For most college students, building a degree plan can be complicated, confusing, and generally limited to whatever their school’s advisor suggests. Most students don’t realize they may be able to take courses outside of their university at community colleges (locally or online) that give the exact same credit towards their degree for a fraction of the cost, saving them potentially thousands of dollars. Furthermore, determining what courses fit into their degree plans can be overwhelming, much less searching through numerous community colleges websites to build a cohesive degree plan. My intention is to create an app that automates this process and provides a list of potential transfer courses for a given degree along with the cost savings estimates.

The first step in this project, and what we cover on this page, is standardizing college degree and course information from multiple schools into one unified database, and representing them in a form that captures all of their diverse details. Critically, to make this scalable to the roughly 1400 public universities in the US, this process would need to be fully automated with little to no manual coercion of the data. This project provides a proof-of-concept for this data collection, processing, and transformation step, where a central database of normalized degree requirements is created.

The normalized degree requirements are represented as an easy-to-read serialized code that represents all of the individual requirements and their relations. They are normalized across different schools and degrees. Below is an example:

**Degree Table Code:** {_1_credits__AB120_<1><2> | _1_credits__AB130_<1><2> | _3_credits__AREC202_ | _4_credits__CHEM107_ |
_1_credits__CHEM108_ | _3_credits__CO150_ | _8_credits_ _1_groups_{{_LIFE102_ | _LIFE103_} | {_BZ110_ | _BZ111_ | _BZ120_}} |
_6_credits__table_9011_ | _3_credits__0000_ | {_1_credits__AB230_<1><2> | _2_credits__BSPM302_<1> | _4_credits__CHEM245_ |
_1_credits__CHEM246_ | _4_credits__MATH155_ | _3_credits__SPCM200_ | _1-2_credits_ _1_courses_{_BSPM303A_<1> | _BSPM303B_<1> |
_BSPM303C_<1>} | _3_credits_ _1_courses_{{_LAND220_ | _LIFE220_}<1> | _LIFE320_<1>} | _3_credits_ _1_courses_{_CO301B_ | _JTC300_
| _LB300_} | _3_credits_ _1_courses_{{_AGRI116_ | _IE116_} | {_HORT171_ | _SOCR171_} | _SOC220_} | _3_credits_
_1_courses_{_STAT301_ | _STAT307_}} | {_2_credits__AB330_<1> | _3_credits__BSPM308_<1> | _3_credits__BSPM361_<1> |
_3_credits__BSPM487_ | _3_credits__BZ220_<1> | _4_credits__BZ350_<1> | _4_credits__SOCR240_<1> | _3_credits__table_0001_<1> |
_5_credits__0000_} | {_3_credits__AB310_<1> | _3_credits__AB430_<1> | _3_credits__AGED210_ | _3_credits__BSPM451_<1> |
_9_credits__table_0001_<1> | _10-11_credits__0000_<3>}}

**Elective Table Code:** _1_courses_per_group_ _12_credits_{{_4_credits__BC351_ | _3_credits__BZ223_ | _4_credits__BZ331_ |
_4_credits__BZ338_ | _3_credits__BZ440_ | _4_credits__BZ450_ | _4_credits__HORT221_ | _4_credits__HORT231_ | _4_credits__HORT232_
| _4_credits__HORT260_ | _0047_ | _0053_ | _3_credits_{_SOCR460_ | _HORT460_}} | {_4_credits__BSPM365_ | _3_credits__BSPM450_ |
_3_credits__BSPM521_ | _4_credits__BZ333_ | _3_credits__MIP300_ | _4_credits_{{_MIP432_ | _ESS432_} | {_MIP433_ | _ESS433_}} |
_4_credits_{_SOCR455_ | _SOCR456_}} | {_3_credits__BSPM423_ | _4_credits__BSPM445_ | _5_credits_{_BSPM462_ | _BZ462_ | _MIP462_} |
_3_credits_{_BZ416_ | _SOCR416_}}}

**Link (click to compare):** https://catalog.colostate.edu/general-catalog/colleges/agricultural-sciences/agricultural-biology/agricultural-biology-major/#requirementstext

On average, the code parses 89% of degree requirements with less than 3% error. The initial goal was to build this proof-of-concept for the largest of the catalog management services (CourseLeaf) and apply this to a single state (Colorado) to evaluate the results and gauge scalability for other states and platforms. The program has been tested on 6 out of the 8 schools in Colorado that use CourseLeaf, including the two largest universities in the state, representing 55,000 individual degree requirements and 25,000 courses. 

## Project Strategy & Goals
The majority of online college catalogs are hosted by one of three different course catalog management services. Under-the-hood, catalogs hosted on the same service share many of the same architectures and schemas for HTML class naming, simplifying the process of scraping and organizing their underlying data, despite the apparent differences between each school’s website. 

This involves the development of an automated program that can capture the vast majority of degree requirements with minimal manual interventions, so that it can be scaled up easily. In order to achieve this without excessive complexity, parsing special cases unique to a school or representing a small fraction of requirements will not be a priority. Rather, other methods will have to be implemented later to accommodate for this, such as crowdsourcing or having an interface for school staff to verify their own data. The long-term goal is to have an app that can provide cheaper course alternatives for the majority of those present in a degree. Even if only 50% of the possible alternatives are identified, this can still represent thousands of dollars of savings. Therefore, the goal is to eventually have an app that can identify greater than 70% of transferrable options, with Type-1 error below 5%.

The project is divided in three sections, and each section has a Jupyter notebook devoted to their methods, individual strategies, and code:
1.	Web-scraping and Data Collection
2.	Normalization and Transformation
3.	Integration and Encoding

## Usage
The scripts can be run sequentially using either the bash script, OA_BashDriver.sh, or the python script, OA_PythonDriver.py. The core project (all the scripts excluding script 5) can also be run using the three Jupyter notebooks included in the main directory, or viewed as HTML in the links directly above. 
Simply choose which school to run the program on when prompted and follow the prompts.

