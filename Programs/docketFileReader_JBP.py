import datetime as dt
import os
import traceback
import re
import csv
from lxml import etree as ET

import sys
sys.path.append('/Users/jbpetkun/Dropbox (MIT)/Research/IFP/Programs/utilities')

import logging

class csvDirError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class docketProcessor(object):
    "Process a single docket"
    def __init__(self,docketsRoot):
        self.docket = docketsRoot.find('docket')

class docketsFileReader(object):
    
    def checkLogDirExistsAndCreateIfNot(self):
        if not os.path.exists(self.logDir):
            os.makedirs(self.logDir)

    def openLog(self):
        self.checkLogDirExistsAndCreateIfNot()
        if self.logger is None:
            self.logger = logging.getLogger(__name__) # __name__ evaluates to name of current module
            
