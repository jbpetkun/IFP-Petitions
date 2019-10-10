from datetime import datetime as dt
import os
import traceback
import re
import csv
from lxml import etree as ET

import sys
sys.path.append('/Users/jbpetkun/Dropbox (MIT)/Research/IFP/Programs/utilities')

import logging

from docketsFileReader_JBP import *

# Set up logging function
def setupLogging():
    formatter = logging.Formatter('%(filename)s[%(funcName)s/%(lineno)d][%(levelname)s] at %(asctime)s:\n\t%(messages)s')

    myLoggerFh = logging.FileHandler('get_cases_with_motion_for_IFP.log',mode='w')
    myLoggerFh.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    logger = logging.getLogger('get_cases_with_motion_for_IFP')#__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(myLoggerFh)
    logger.addHandler(console)
    logger.setLevel(logging.DEBUG)
    console.setLevel(logging.ERROR)

    logger.info('Starting get_cases_with_motion_for_IFP.py.\n\n')
    return logger

mylogger = setupLogging()    

# Create list of files to process
searchAll = re.compile('.*xml$').search
listOfAllFiles = ['Users/jbpetkun/Dropbox (MIT)/Research/IFP/Data/Raw/dockets/'+l
                  for l in os.listdir("/Users/jbpetkun/Dropbox (MIT)/Research/IFP/Data/Raw/dockets/")
                  for m in (searchAll(l),) if m]
print(listOfAllFiles)

def mainLoopFunction(listOfFiles):
    for file in listOfFiles:
        logging.info("Starting %s", file)
        docketsFileReader(file,
                          logger=mylogger)
        logging.info("Done with file %s", file)
    logging.info("Datetime at end is %s.\n\tDone.", dt.now())

# Main Procedural Block

mainLoopFunction(listOfAllFiles)

