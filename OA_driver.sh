#!/bin/bash
python OA_1_MainSites_Scraper.py &&
python OA_2_CourseDescriptIon_Scraper.py &&
python OA_3_DegreePage_Scraper.py &&
python OA_4_CourseDescription_Organizer.py &&
python OA_5_CourseDescription_Parser.py &&
python OA_6_Degree_Organizer.py &&
python OA_7_Geneds.py &&
python OA_6_Degree_Organizer.py &&
python OA_8_Degree_Integrator.py