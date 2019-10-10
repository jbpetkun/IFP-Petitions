
from datetime import datetime as dt
from pprint import pprint
import os
import traceback
import re
import csv
from lxml import etree as ET
from xmlFiles import *
from CaseLevelFunctions import *
from GeneralFunctions import *
from StringIO import StringIO
from collections import namedtuple
from ClassActionUtilities import CLASS_MOTION, MDL

import sys
sys.path.append('/home/gelbach/pydockets/python/utilities')

import logging

Party = namedtuple('Party', 'partycounter partyname partytype partyterminated attorneyDataList') 
Attorney = namedtuple('Attorney', 
                      'partycounter attorneycounter attorneyname attorneystatus firmname firmaddress firmcity firmstate firmzip'
) 

regex_CLASS_ACTION = re.compile(CLASS_MOTION)
regex_MDL = re.compile(MDL)

def stringify(list):
     return str(''.join([str(i) for i in list]))

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
    """Class to read docket files, spit out results, and log operations.

     To process a docket file, execute python script with code including:

     import logging
     formatter = logging.Formatter('%(filename)s[%(funcName)s/%(lineno)d][%(levelname)s] at %(asctime)s:\n\t%(message)s')
     myLoggerFh = logging.FileHandler('python_script_name.log',mode='w')
     myLoggerFh.setFormatter(formatter)
     mylogger = logging.getLogger()
     mylogger.setLevel(logging.DEBUG) #logging.INFO will also work
     mylogger.addHandler(myLoggerFh)
     mylogger.info('Starting python_script_name.py....')
     listOfFiles = [list,of,xml,files,you,want,to,process,with,absolute,paths]
     myFirstLine="comma,separated,list,of,variable,names,to,appear,on,first,line"
     for file in listOfFiles: 
          mylogger.info("Starting %s" % file)
          docketsFileReader(file, csvDir='./csv/',
                            processDocketFunction=pdf, #pdf having been created in caller file
                            firstLine=myFirstLine, #see above
                            logger=mylogger, #passing logger object to docketsFileReader object
          )
          logging.info("Done with file %s.", file)
     logging.info("Datetime at end is %s.\n\tDONE.", dt.now())

    +-------+
    | Notes |
    +-------+

    1. The 'pdf' function.
            A. To be provided by user (presumably higher up in python_script_name.py).
            B. Must return a string that will be written to the csv file. Can return ''.

    2. The 'myFirstLine' variable.
            A. It must be a string. 
            B. It will be written to the top of ./csv/file.csv.

    3. The csvDir option.
            A. It defaults to './csv/'
            B. Any valid directory name will work.
            C. If csvDir="<dir>/csv/", then file-specific logs will live in "<dir>/logs".

    4. The logger option.
            A. It defaults to None.
            B. Allows user to pass a logging object to docketsFileReader for logging use.
            C. Even if it is None, docketsFileReader will still log results,
               in <dir>/logs/file.log.

    5. useDocketEntries option.
            A. It defaults to False.
            B. Currently unused/undocumented.

    6. The variables option.
            A. Currently unused.

    7. The nowrite option.
            A. Defaults to False.
            B. If False, then each docket's output is written to csv (output assumed to be string)
            C. If nowrite is anything else, then self.output_list will be extended by 
               each docket's output, i.e., if you do this:

                    yourObjectName = docketFileReader([stuff],nowrite=True)

               then the list yourObjectName.output_list will contain a list of output from
               the dockets processed, in order.
    """

    def checkLogDirExistsAndCreateIfNot(self):
         if not os.path.exists(self.logDir):
              os.makedirs(self.logDir)

    def openLog(self):
         self.checkLogDirExistsAndCreateIfNot()
         if self.logger is None:
              self.logger = logging.getLogger(__name__)
              self.logger.setLevel(logging.DEBUG)

         self.formatter = logging.Formatter(
              "%(filename)s[%(funcName)s/%(lineno)d][%(levelname)s] at %(asctime)s:\n\t%(message)s" 
         )
         self.logFileName = self.logDir+self.docketFileName+'.log'
         self.fileHandle = logging.FileHandler(self.logFileName,mode='w')
         self.fileHandle.setLevel(logging.DEBUG)
         self.fileHandle.setFormatter(self.formatter)
         self.logger.addHandler(self.fileHandle)
         self.logger.info('Starting file %s\n', self.docketFileName)

    def closeLog(self):
         self.fileHandle.close()
         self.logger.removeHandler(self.fileHandle)

    def getDocketFileNameDir(self):
         self.DocketFileNameRelativeDir = os.path.dirname(self.docketFileName)            
         self.DocketFileNameAbsoluteDir = os.path.dirname(os.path.abspath(self.docketFileName))

    def checkCsvDirExistsAndCreateIfNot(self):
         if not os.path.exists(self.csvDir):
              os.makedirs(self.csvDir)

    def openOutfile(self):
         self.checkCsvDirExistsAndCreateIfNot()
         self.outfileName = self.csvDir + self.docketFileName + '.csv'   
         self.outfile = open(self.outfileName,'w')

    def closeOutfile(self):
         self.outfile.close()

    def makeCsvDir(self,csvDir):
         "Create directory for csvDir"
         if re.match('^.*/$',csvDir):
              self.csvDir = csvDir
         else:
              self.csvDir = csvDir + '/'

    def makeLogDir(self):
         "Create directory for logDir"
         self.logDir = re.sub('csv/$','logs/',self.csvDir)

    def parseBadFileAsString(self,myfile):
         """Parse file into list of strings, some of which are hoped to have valid XML for a docket.
            Returns list of all 'good' dockets, where good means the string is well-formed XML.
            If any string in list has '<docket>' or '</docket>' in it, entire file will be rejected.
         """
    
         def removeTopDocketTags(string):
              return re.sub(r'<dockets>\n<docket>','',string)
    
         def removeBottomDocketTags(string):
              return re.sub(r'</docket>\n</dockets>$','',string)

         def makeListOfDocketsAsText(string):
              text = removeTopDocketTags(string)
              text = removeBottomDocketTags(text)
              return re.split(r'</docket>\n<docket>',text)

         def splitFileIntoListOfStringsOrThrowError(fileObject,myfile):
              docketListAsText = makeListOfDocketsAsText(fileObject.read())
              regex = re.compile('</*docket>')
              badDockets = []
              counter = 0
              for d in docketListAsText:
                   counter += 1
                   for m in [regex.search(d)]:
                        if m:
                             self.logger.error("****Docket # %s has %s in it:\n\t%s****" % (counter, m.group(0), d))
                             badDockets.append(m.group(0))
                             
              #badDockets = [m.group(0) for d in docketListAsText for m in [regex.search(d)] if m]
              if badDockets == []:
                   return docketListAsText
              else:
                   self.logger.info(
                        "There were %s dockets with '<docket>' or '</docket>' inside the docket-specific string.\n\t\t=>This file will have no output.", 
                        len(badDockets) 
                   )
                   raise JBGSyntaxError('JBGSyntaxError')

         def initializeRoot():
             return ET.Element("root")              

         def initializeLists():
              self.listOfGoodDockets = []
              self.listOfBadDockets = []
              self.listOfBadDocketNumbers = []
    
         #########################################################
         ##### MAIN PROCEDURAL BLOCK OF parseBadFileAsString #####
         #########################################################
    
         with open(myfile) as f:
              initializeLists()
              root = initializeRoot()
              try:
                   docketListAsText = splitFileIntoListOfStringsOrThrowError(f,myfile)
                   for d in docketListAsText:
                        self.allDocketsCounter += 1
                        d.strip()
                        try:
                             tree = ET.fromstring('<docket>%s</docket>' % d)
                             self.goodDocketsCounter += 1 #has to be after parse or we will count bad dockets here as well
                             root.append(tree)
                             self.listOfGoodDockets.append(tree)
                        except ET.XMLSyntaxError:
                             self.badDocketsCounter += 1
                             self.logger.info(
                                 " --> XMLSyntaxError for docket # %s", self.allDocketsCounter
                             )
                             self.listOfBadDocketNumbers.append(self.allDocketsCounter)
                             self.listOfBadDockets.append(d)
              except JBGSyntaxError:
                   pass
         self.logger.info("Total number of all  dockets in this file was %s", self.allDocketsCounter)
         self.logger.info("Total number of good dockets in this file was %s", self.goodDocketsCounter)
         self.logger.info("Total number of bad  dockets in this file was %s", self.badDocketsCounter)
         self.logger.info(
              "List of bad dockets' text starts on next line:\n" + 
              '\n'.join(["Next bad docket is number %s:\n\t%s" % (self.listOfBadDocketNumbers[index], badDocket) for index,badDocket in enumerate(self.listOfBadDockets)])
#              '\n'.join(['Next bad docket is number ' + self.listOfBadDocketNumbers[index] + ':\n\t' + badDocket for index,badDocket in self.listOfBadDockets])
         )
         return ET.ElementTree(root)

    def getDocketsRoot(self):
         "Get root of XML tree."

         """
         #next function is deprecated and will sloooooow everything down! 
         #use /data2/dockets/preprocessed/*.xml files, which are already preprocessed
         def preProcessDocketFile(filename):
              "Preprocess docket file to convert <links...> elements to text"
              tree = ET.fromstring('<a>b</a>') #nonsense on purpose
              spaces = re.compile(r' +')
              with open (filename,'r') as tfile:
                   myfile = ''
                   for line in tfile:
                        line = line.replace('<links.to.entry.number>',' |linksToEntryNumber| ')
                        line = line.replace('</links.to.entry.number>',' ')
                        line = line.replace('<links.to.attachment.number>',' |linksToAttachmentNumber| ')
                        line = line.replace('</links.to.attachment.number>',' ')
                        myfile = myfile + spaces.sub(' ', line)
                   tree = ET.parse(StringIO(myfile))
              return tree
         """

         try: 
              self.tree = ET.parse(self.docketAbsPath)
              #self.tree = preProcessDocketFile(self.docketAbsPath)
              self.badFile = False
         except ET.XMLSyntaxError:
              self.badFile = True
              self.tree = self.parseBadFileAsString(self.docketAbsPath)
         self.docketsRoot = self.tree.getroot() 
         return self.docketsRoot

    def initializeCounters(self):
         self.goodDocketsCounter = 0
         self.badDocketsCounter = 0
         self.allDocketsCounter = 0
         self.docketCounterWithinFile = 0

    def _getCaseHeaderVariables(self):
         "Method to make chosen caseheaderVariables values available as self.caseheaderVariables"
         caseheaderDict = dict()
         for var in self.variables:
              if var == 'wlfilename': 
                   caseheaderDict[var] = self.docketFileName
                   continue
              try:
                   caseheaderDict[var] = self.docket.find(".//"+self.xmlTagsForVariable[var]).text
              except AttributeError:
                   caseheaderDict[var] = None
         return caseheaderDict

    def _getDocketEntriesBlockElement(self):
         return self.docket.find(".//docket.entries.block")

    def _getDocketEntries(self): 
         def appendDocketEntry(entry,variableName,thisText):
              if list(entry.iter(thisText)) == []:
                   docketEntriesDict[variableName].append('.')
              else:
                   docketEntriesDict[variableName].append(list(entry.iter(thisText))[0].text)
              return True

         def appendDocketEntries(entry):
              for v in [
                        ['number','number'],
                        ['date','date'],
                        ['docketdescription','docket.description']
              ]:
                   appendDocketEntry(entry,v[0],v[1])
              docketDescriptionText = stringify(entry.xpath(".//docket.description/text()"))
              if regex_CLASS_ACTION.match( docketDescriptionText ):
                   docketEntriesDict['classactionflag'].append('1')
              else:
                   docketEntriesDict['classactionflag'].append('0')
              if regex_MDL.match( docketDescriptionText ):
                   docketEntriesDict['mdlflag'].append('1')
              else:
                   docketEntriesDict['mdlflag'].append('0')

         if self.useDocketEntries == True:
              self.docketEntriesBlockElement = self._getDocketEntriesBlockElement()
              docketEntriesNodeList = self.docketEntriesBlockElement.findall("./docket.entry")
              docketEntriesDict = {
                   'myDENCounter':[], 'number':[], 'date':[], 'docketdescription':[],
                   'classactionflag':[],'mdlflag':[],
              }
              myDENCounter = 0
              for entry in docketEntriesNodeList:
                   myDENCounter += 1
                   docketEntriesDict['myDENCounter'].append(myDENCounter)
                   appendDocketEntries(entry)
              return docketEntriesDict
         else:
              return {}

    def _getPartyBlockElement(self):
         return getGenericBlockFirstElement(self.docket,'party.block')

    def _getPartyBlockData(self):
         def _processAttorneyBlockOf(partySubBlock):
              #now get list of party.attorney.block elements. 
              #Note: need to process each such block b/c firm.name missing for pro se
              attorneyBlockList = partySubBlock.xpath(".//party.attorney.block")
              attorneyCounter = 0
              attorneyDataList = list()
              for attorneyBlock in attorneyBlockList:
                   attorneyCounter += 1
                   attorneyName = getValue('attorney.name',attorneyBlock)
                   attorneyStatus = stringify(attorneyBlock.xpath(".//attorney.status/text()"))
                   firmname = stringify(attorneyBlock.xpath(".//firm.name/text()"))
                   firmstreet = stringify(attorneyBlock.xpath(".//street/text()"))
                   firmcity = stringify(attorneyBlock.xpath(".//city/text()"))
                   firmstate = stringify(attorneyBlock.xpath(".//state/text()"))
                   firmzip = stringify(attorneyBlock.xpath(".//zip/text()"))
                   attorneyDataList.append(
                        Attorney(
                             partyCounter,attorneyCounter,
                             attorneyName,attorneyStatus,firmname,
                             firmstreet,firmcity,firmstate,firmzip
                        )
                   )
              return attorneyDataList

         def _processPartySubBlockOf(thisPartySubBlock,partyCounter):
              partyName = stringify(thisPartySubBlock.xpath(".//party.name/text()"))
              partyType = stringify(thisPartySubBlock.xpath(".//party.type/text()"))
              partyTerminated = stringify(thisPartySubBlock.xpath(".//party.terminated/text()"))
              partyAttorneyDataList = _processAttorneyBlockOf(thisPartySubBlock)
              return Party(partyCounter, 
                           partyName, partyType, partyTerminated, 
                           partyAttorneyDataList)

         self.partyBlockElement = self._getPartyBlockElement()
         self.partySubBlocks = list(self.partyBlockElement) #kids of partyBlockElement are parties
         #self.partySubBlocks = self.partyBlockElement.xpath(
         #     "//*[substring(name(), string-length(name()) - (string-length('party')+1) ) = 'party']"
         #)
         self.partyDataList = list()
         self.partyTypeTextList = list()
         self.partyNameTextList = list()
         partyCounter = 0
         for thisPartySubBlock in self.partySubBlocks:
              partyCounter += 1
              thisParty =  _processPartySubBlockOf( thisPartySubBlock, partyCounter )
              self.partyDataList.append( thisParty )

         #print "self.partyDataList={0}".format(self.partyDataList)
         return self.partyDataList

    def defaultProcessDocketFunction():
         "Would be nice to have this write some default collection of case-level variables"
         return ''

    def processThisDocket(self,docket):
         self.docket = docket
         self.caseheaderDict = self._getCaseHeaderVariables()
         self.docketEntriesDict = self._getDocketEntries()
         #print "caseheaderDict={0}".format(self.caseheaderDict)
         self.partyDataList = self._getPartyBlockData()
         #print "from dfr: partyDataList='{0}'".format(self.partyDataList)
         output = self.processDocketFunction(self)
         self.output_list.append( output )
         if self.nowrite is False:
              self.outfile.write( output )

    def processDocketTree(self):
         self.initializeCounters()
         for docket in self.getDocketsRoot():
              self.docketCounterWithinFile += 1
              self.processThisDocket(docket)
         if self.badFile is False:
              self.goodDocketsCounter = self.docketCounterWithinFile
              self.allDocketsCounter = self.docketCounterWithinFile
         if self.nowrite is False:
              outfile_text = "Output is in %s.\n\t" % (self.outfileName)
         else:
              outfile_text = ""
         self.logger.info(
              "There were %s dockets that lxml could not parse." % (self.badDocketsCounter) +
              "\n\tSuccessfully processed %s out of %s dockets.\n\t" % 
              (self.goodDocketsCounter,self.allDocketsCounter) +
              outfile_text +
              "Logfile is %s.\n\t" % (self.logFileName) +
              "Done with file %s at %s.\n\t##########\n" % (self.docketFileName, dt.now())
                     )

    def doFileOperations(self,filename,csvDir):
         self.docketAbsPath  = filename
         self.docketFileName = os.path.basename(filename)
         self.getDocketFileNameDir()
         if self.nowrite is False:
              self.makeCsvDir(csvDir)
         else:
              self.csvDir = csvDir #make sure this exists for purposes of self.makeLogDir call
         self.makeLogDir()
         self.openLog()


    xmlTagsForVariable  = {
         'court' : 'court',
         'primarytitle' : 'primary.title',
         'docketnumber' : 'docket.number',
         'judge' : 'judge',
         'filingdate' : 'filing.date',
         'closeddate' : 'closed.date',
         'natureofsuit' : 'nature.of.suit',
         'natureofsuitcode' : 'nature.of.suit.code',
    }
         
    def doVariableOperations(self,variables,useDocketEntries,useBlockTypes):
         self.variables = variables.split(',')
         self.useDocketEntries = useDocketEntries
         self.useBlockTypesList = useBlockTypes
         #print "self.useBlockTypesList='{0}'".format(self.useBlockTypesList)

    variableString = ','.join(['wlfilename',
                               'court','primarytitle','docketnumber','judge',
                               'filingdate','closeddate',
                               'natureofsuit','natureofsuitcode'
                          ])

    def __init__(self, filename, csvDir='./csv/',
                 useDocketEntries=False,
                 useBlockTypes = ['party','docketEntries'],
                 processDocketFunction=defaultProcessDocketFunction,
                 nowrite=False,
                 variables=variableString,
                 firstLine='',
                 logger=None,
    ):
         self.logger = logger
         self.nowrite = nowrite
         self.doFileOperations(filename,csvDir)
         self.doVariableOperations(variables,useDocketEntries,useBlockTypes)
         self.processDocketFunction = processDocketFunction
         self.output_list = []
         if self.nowrite is False:
              self.openOutfile()
              self.outfile.write(firstLine)
         else:
              pass

         try:
              self.processDocketTree()
              #print self.output_list[0]
              #print self.output_list
         except ET.XMLSyntaxError:
              self.logger.info("Woops: XMLSyntaxError.")
         self.closeLog()
         ####end __init__ for docketsFileReader class

class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class JBGSyntaxError(Error):
    """Exception raised for errors in the input.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message


class getDocketsData(object):
     """High level class for interfacing with docketsFileReader class.

        Still under development.
     """

     variableList  = {
         'court' : 'caseheader',
         'primarytitle' : 'caseheader',
         'docketnumber' : 'caseheader',
         'judge' : 'caseheader',
         'filingdate' : 'caseheader',
         'closeddate' : 'caseheader',
         'natureofsuit' : 'caseheader',
         'natureofsuitcode' : 'caseheader',
         'number' : 'docket.entries.block',
         'date' : 'docket.entries.block',
         'docketdescription' : 'docket.entries.block',
     }

     def listVariables(self):
          for key in sorted(self.variableList.keys()):
               self.logger.debug(key, "\t", self.variableList[key])

     def callDocketsFileReader():
          pass

     def __init__(self):
          pass

