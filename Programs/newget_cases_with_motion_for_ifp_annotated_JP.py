
from datetime import datetime as dt
import os
import traceback
import re
import csv
from lxml import etree as ET

import sys
sys.path.append('/data2/dockets/utilities')

import logging


from xmlFiles import *
from CaseLevelFunctions import *
from GeneralFunctions import *
from docketsFileReader import *

# TO DO LIST
#    Additional items to attemp:
#         - Flag motions found as moot ("FINDING AS MOOT"; "DENYING AS MOOT")
#         - Fix bug limiting number of plaintiff/defendant names I can match on
#         - Don't count orders starting with "PROPOSED"
#         - Exclude from orders all the text following "ATTACHMENTS:"

#logging function
def setupLogging():
     formatter = logging.Formatter('%(filename)s[%(funcName)s/%(lineno)d][%(levelname)s] at %(asctime)s:\n\t%(message)s')

     myLoggerFh = logging.FileHandler('newget_cases_with_motion_for_ifp.log',mode='w')
     myLoggerFh.setFormatter(formatter)

     console = logging.StreamHandler()
     console.setFormatter(formatter)

     logger = logging.getLogger('newget_cases_with_motion_for_ifp')#__name__)
     logger.setLevel(logging.DEBUG)
     logger.addHandler(myLoggerFh)
     logger.addHandler(console)
     logger.setLevel(logging.DEBUG)
     console.setLevel(logging.ERROR)

     logger.info('Starting newget_cases_with_motion_for_ifp.py.\n\n')
     return logger

mylogger = setupLogging()

### Additional case-level functions
# Return list of plaintiffs
def getPlaintiffs(docket):
     if docket.find('party.block').findall('plaintiff.party') is None:
          plaintiffList = ['']
     else:
          plaintiffList = docket.find('party.block').findall('./plaintiff.party')
     plaintiffListTemp = []
     for plaintiff in plaintiffList:
          if plaintiff.find('party.type') is not None and not re.search('Cross|cross|Counter|counter',plaintiff.find('party.type').text):
               if plaintiff.find('party.name.block') is not None and plaintiff.find('party.name.block').find('party.name') is not None:
                    plaintiffListTemp.append(ET.tostring(plaintiff.find('party.name.block').find('party.name'),method="text").replace('"',''))
     plaintiffListTemp = list(set(plaintiffListTemp))
     return '; '.join(plaintiffListTemp[0:99])

# Return indicator for whether plaintiff was Pro Se
#get proSePlaintiff(docket):

# Return list of defendants
def getDefendants(docket):
     if docket.find('party.block').findall('defendant.party') is None:
          defendantList = ['']
     else:
          defendantList = docket.find('party.block').findall('./defendant.party')
     defendantListTemp = []
     for defendant in defendantList:
          if defendant.find('party.type') is not None and not re.search('Cross|cross|Counter|counter',defendant.find('party.type').text):
               if defendant.find('party.name.block') is not None and defendant.find('party.name.block').find('party.name') is not None:
                    defendantListTemp.append(ET.tostring(defendant.find('party.name.block').find('party.name'),method="text").replace('"',''))
     defendantListTemp = list(set(defendantListTemp))
     return '; '.join(defendantListTemp[0:99])

# Return parties' attorneys; we'll use this in order to determine the moving party
def getAttorneys(docket):
     attorneyListRaw = {'plaintiff':[], 'defendant':[]}
     attorneyList = {'plaintiff':[], 'defendant':[]}
     # if docket.find('party.block').findall('plaintiff.party') is None:
     #      return attorneyList['plaintiff']
     # else:
     for plaintiff in docket.find('party.block').findall('./plaintiff.party'):
          if plaintiff.find('party.type') is not None and not re.search('Cross|cross|Counter|counter',plaintiff.find('party.type').text):
               for attorney in plaintiff.findall('party.attorney.block'):
                    if attorney.find('attorney.name') is not None:
                         attorneyListRaw['plaintiff'].append(ET.tostring(attorney.find('attorney.name'),method="text"))
     for defendant in docket.find('party.block').findall('./defendant.party'):
          if defendant.find('party.type') is not None and not re.search('Cross|cross|Counter|counter',defendant.find('party.type').text):
               for attorney in defendant.findall('party.attorney.block'):
                    if attorney.find('attorney.name') is not None:
                         attorneyListRaw['defendant'].append(ET.tostring(attorney.find('attorney.name'),method="text"))
     for party in 'plaintiff', 'defendant':
          for attorney in attorneyListRaw[party]:
               attorney = re.split(',',attorney,1)[0]
               attorney = re.sub('[^A-Za-z0-9\. ]+','',attorney)
               attorney = re.sub('GOVERNMENT','',attorney)
               names = re.split(' ',attorney,2)
               if len(names) == 3:
                    attorneyName = '(' + names[2] + ', ' + names[0] + ')'
                    attorneyList[party].append(attorneyName)
               elif len(names) == 2:
                    attorneyName = '(' + names[1] + ', ' + names[0] + ')'
                    attorneyList[party].append(attorneyName)
          attorneyList[party] = list(set(attorneyList[party])) # removes duplicates
     return attorneyList

###functions used in this file's implementation
def thisIfConditionFunction(object):
     "ifConditionFunction function"

     def makeGlobOfText(block):
          return ET.tostring(block, method="text").upper()

     # def searchForMatchOnCase(string):
     #      return re.search("MOTION TO TRANSFER",string)
     
     def searchForMatchOnCase(string):
          return re.search('(IN FORMA PAUPERIS)|(IFP)|(FEE WAIVER)|(WAIVER OF FEE)',string)     

     def makeCaseMatchFlag(globOfText):
          match = searchForMatchOnCase(globOfText)
          if match:
               return True
          else:
               return False

     def getNoticeOfRemovalFlag(globOfText):
          match = re.search("NOTICE OF REMOVAL",globOfText)
          if match:
               return 1
          else:
               return 0

     def initializeObjectIfConditionContainers(object,myList):
          object.ifConditionContainer={}
          object.ifConditionContainer['noticeOfRemovalFlag']=''
          for m in myList:
               object.ifConditionContainer[m] = list()

     def getFullTextOfDocketDescription(element):
          dD = element.find('docket.description')
          if dD is None:
               return ''
          else:
               return ET.tostring(dD, method="text")
     
     # Return flag for the entry associated w/ the actual motion for summary judgment
     def getMotionFlag(string):
          match = re.search(
               '^(MOTION|APPLICATION|PETITION|REQUEST)\s(?:BY [^;\n<>]*)(?:FOR LEAVE)? TO PROCEED (IFP|IN FORMA PAUPERIS)',
               string.upper()
          )
          if match:
               return 1
          else:
               match = re.search(
                    '^(?:MOTION BY )[^;\n<>]*(?: (?:TO DISMISS OR )?FOR (?:PARTIAL )?FEE WAIVER)',
                    string.upper()
               )
               if match:
                    return 1
               else:
                    return 0
     
     def getOppositionFlag(string):
          match = re.search(
               '^(MEMORANDUM|RESPONSE|BRIEF) IN OPPOSITION', string.upper()
          )
          if match:
               return 1
          else:
               return 0
          
     def getReplyFlag(string):
          match = re.search(
               'REPLY', string.upper()
          )
          if match:
               return 1
          else:
               return 0
     
     # Return flag for entry associated with motion to certify order for interlocutory appeal     
     def getInterloc(string):
          match = re.search(
               '(INTERLOCUTORY|CERTIFICATE OF APPEALABILITY| 1292 | 1292\()',
               string.upper()
          )
          if match:
               return 1
          else:
               return 0

     # Return filing/moving party
     #    Note: this is probably the weakest function. Needs some work.
     def getMovant(object,string):
          # Check if entry looks like a document filed by the court
          courtMatch = re.search('(?:SIGNED |ORDERED )?BY (?:CHIEF |SENIOR |DISTRICT |MAGISTRATE )?(?:JUDGE|HONORABLE|THE HONORABLE)', string.upper())
          # Match on one of the attorneys' names
          allPlaintiffAttorneys = '(' + ')|('.join(getAttorneys(object.docket)['plaintiff'][0:45]) +')' # Bug in Python -- I can only match on ~ 40 names at a time
          allDefendantAttorneys = '(' + ')|('.join(getAttorneys(object.docket)['defendant'][0:45]) + ')'
          if allPlaintiffAttorneys != '()':
               plaintiffAttorneyMatch = re.search(allPlaintiffAttorneys,string.upper())
          else:
               plaintiffAttorneyMatch = False
          if allDefendantAttorneys != '()':
               defendantAttorneyMatch = re.search(allDefendantAttorneys,string.upper())
          else:
               defendantAttorneyMatch = False
          # Match on one of the parties' names
          allPlaintiffs = 'BY (' + re.sub('; ',')|(',re.escape(getPlaintiffs(object.docket))) + ')' # Make a list of plaintiffs to search for
          allDefendants = 'BY (' + re.sub('; ',')|(',re.escape(getDefendants(object.docket))) + ')'
          if allPlaintiffs != '()':
               plaintiffMatch = re.search(allPlaintiffs,string.upper())
          else:
               plaintiffMatch = False
          if allDefendants != '()':
               defendantMatch = re.search(allDefendants,string.upper())
          else:
               defendantMatch = False
          # Return moving/filing party
          if courtMatch:
               return 'Court'
          elif re.search('^(?:AMENDED |TEXT |FINAL )?(ORDER|OPINION|RULING|MEMORANDUM RULING|MINUTE ENTRY|MEMORANDUM(?: OPINION)? \& ORDER|MEMORANDUM(?: OPINION)? AND ORDER|DECISION \& ORDER|DECISION AND ORDER|JUDGMENT)',string.upper()):
               return 'Court'
          elif plaintiffAttorneyMatch:
               return 'Plaintiff'
          elif defendantAttorneyMatch:
               return 'Defendant'
          elif plaintiffMatch:
               return 'Plaintiff'
          elif defendantMatch:
               return 'Defendant'              
          elif re.search('FILED BY DEFENDANTS?',string.upper()):
               return 'Defendant'
          elif re.search('FILED BY PLAINTIFFS?',string.upper()):
               return 'Plaintiff'
          elif re.search('^DEFENDANT\'?S\'? MOTION',string.upper()):
               return 'Defendant'
          elif re.search('^PLAINTIFF\'?S\'? MOTION',string.upper()):
               return 'Plaintiff'
          else:
               return ''
     
     # Return flag for court order/ruling on motion     
     def getOrderFlag(string):
          match = re.search('^(?:AMENDED |TEXT |FINAL )?(ORDER|OPINION|RULING|MEMORANDUM RULING|MINUTE ENTRY|MEMORANDUM(?: OPINION)? \& ORDER|MEMORANDUM(?: OPINION)? AND ORDER|DECISION \& ORDER|DECISION AND ORDER|JUDGMENT)',string.upper()) 
          if match:
               return 1
          else:
               return 0
     
     # Return list of references to other entries in the docket
     def getEntryReferences(entry):
          description = entry.find('docket.description')
          refListTemp = []
          for link in description.iter('links.to.entry.number'):
               if link.text != None:
                    refListTemp.append(link.text)    
          return str('; '.join(refListTemp))
     
     def replaceEntryReferences(entry):
          entryStringNew = ET.tostring(entry,method="xml")
          formatList = ['DOC. NO. ','DOC. NO.','DKT. NO.','DOC. ','DOC.','DKT. NO. ','DKT. NO.','DKT. ENTRY NO. ','DKT. #','DKT. # ','DKT.','DKT. ','DKT#','DKT #','DOC #', 'DOC # ']
          for format in formatList:
               refList = re.findall(format+'\d{1,5}',entryStringNew)
               for fullReference in refList:
                    reference = re.search('(?P<opentag>'+format+')(?P<entrynumber>\d{1,5})',fullReference)
                    if not re.search('<links\.to\.entry\.number>'+reference.groupdict()['entrynumber']+'</links\.to\.entry\.number>',entryStringNew):
                         entryStringContainer = re.subn(format+reference.groupdict()['entrynumber'],'<links.to.entry.number>'+reference.groupdict()['entrynumber']+'</links.to.entry.number>',entryStringNew)
                         entryStringNew = entryStringContainer[0]
                         #print str(entryStringContainer[1]) + ' substitutions made for '+format+' '+reference.groupdict()['entrynumber']
          return entryStringNew
          
     # Return list of motions granted in this entry
     def getMotionsGranted(entry):
          #entryString = ET.tostring(entry,method="xml")
          entryString = replaceEntryReferences(entry)
          grantList = []
              
          if not re.search('<docket.description>REPORT (AND)|(&) RECOMMENDATION',entryString) and not re.search('<docket.description>PROPOSED',entryString):
               # Matches "GRANTING MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)GRANTING[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    grant = re.search('(?P<action>GRANTING[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    if not re.search('(IN PART|DENYING)',grant.groupdict()['action']):
                         grantList.append(grant.groupdict()['motion'])     
               # Matches "MOTION #X IS GRANTED" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?GRANTED[^;\n<>]*',entryString)
               for statement in stringList:
                    grant = re.search('(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)(?P<action>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?GRANTED[^;\n<>]*)',statement)
                    if not re.search('IN PART|DENIED',grant.groupdict()['action']):
                         grantList.append(grant.groupdict()['motion'])
               # Matches "THE COURT GRANTS MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)COURT GRANTS[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    grant = re.search('(?P<action>COURT GRANTS[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    if not re.search('(IN PART|DENIES)',grant.groupdict()['action']):
                         grantList.append(grant.groupdict()['motion'])
               grantList = list(set(grantList)) # drop duplicates
               # Look for text-only matches (no entry link)
               if grantList == [] and not re.search('MOTION FOR EXTENSION OF TIME',entryString):
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT IS (?:HEREBY )?GRANTED)',entryString)
                    for statement in stringList:
                         grant = re.search('(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)(?P<action> IS (?:HEREBY )?GRANTED)',statement)
                         grantList.append(grant.groupdict()['motion'])
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:COURT GRANTS |GRANTING )(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         grant = re.search('(?P<action>(?:COURT GRANTS |GRANTING ))(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',statement)
                         grantList.append(grant.groupdict()['motion'])                        
               return str('; '.join(grantList))
     
     # Return list of motions denied in this entry
     def getMotionsDenied(entry):
          entryString = replaceEntryReferences(entry)
          denyList = []
          
          if not re.search('<docket.description>REPORT (AND)|(&) RECOMMENDATION',entryString) and not re.search('<docket.description>PROPOSED',entryString):
               # Matches "DENYING MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)DENYING[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    deny = re.search('(?P<action>DENYING[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    if not re.search('(IN PART|GRANTING)',deny.groupdict()['action']):
                         denyList.append(deny.groupdict()['motion'])
               # Matches "MOTION #X IS DENIED" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?DENIED[^;\n<>]*',entryString)
               for statement in stringList:
                    deny = re.search('(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)(?P<action>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?DENIED[^;\n<>]*)',statement)
                    if not re.search('IN PART|GRANTED',deny.groupdict()['action']):
                         denyList.append(deny.groupdict()['motion'])
               # Matches "THE COURT DENIES MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)COURT DENIES[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    deny = re.search('(?P<action>COURT DENIES[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    if not re.search('(IN PART|GRANTS)',deny.groupdict()['action']):
                         denyList.append(deny.groupdict()['motion'])          
               denyList = list(set(denyList)) # drop duplicates
               # Look for text-only matches (no entry link)
               if denyList == [] and not re.search('MOTION FOR EXTENSION OF TIME',entryString):
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT IS (?:HEREBY )?DENIED)',entryString)
                    for statement in stringList:
                         deny = re.search('(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)(?P<action> IS (?:HEREBY )?DENIED)',statement)
                         denyList.append(deny.groupdict()['motion'])
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:COURT DENIES |DENYING )(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         deny = re.search('(?P<action>(?:COURT DENIES |DENYING ))(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',statement)
                         denyList.append(deny.groupdict()['motion'])                 
               return str('; '.join(denyList))     
     
     # Return list of motions granted in part in this entry
     def getMotionsGrantedInPart(entry):
          entryString = replaceEntryReferences(entry)
          grantInPartList = []
          
          if not re.search('<docket.description>REPORT (AND)|(&) RECOMMENDATION',entryString) and not re.search('<docket.description>PROPOSED',entryString):
               # Matches "GRANTING IN PART MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)GRANTING,? IN PART[^\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    grantInPart = re.search('(?P<action>GRANTING,? IN PART[^\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    grantInPartList.append(grantInPart.groupdict()['motion'])
               # Matches "MOTION #X IS GRANTED IN PART" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?GRANTED,? IN PART[^\n<>]*',entryString)
               for statement in stringList:
                    grantInPart = re.search('(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)(?P<action>[^;\n<>]*(?:SHALL BE, AND HEREBY )?IS(?:,)? (?:HEREBY )?GRANTED,? IN PART[^\n<>]*)',statement)
                    grantInPartList.append(grantInPart.groupdict()['motion'])
               # Matches "THE COURT GRANTS IN PART MOTION #X" syntax
               stringList = re.findall('(?!ATTACHMENTS:.*)COURT GRANTS[^;\n<>]IN PART<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
               for statement in stringList:
                    grantInPart = re.search('(?P<action>COURT GRANTS[^;\n<>]*IN PART)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    grantInPartList.append(grantInPart.groupdict()['motion'])                      
               grantInPartList = list(set(grantInPartList)) # drop duplicates
               # Look for text-only matches (no entry link)
               if grantInPartList == [] and not re.search('MOTION FOR EXTENSION OF TIME',entryString):
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT IS (?:HEREBY )?GRANTED,? IN PART)',entryString)
                    for statement in stringList:
                         grantInPart = re.search('(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)(?P<action> IS (?:HEREBY )?GRANTED,? IN PART)',statement)
                         grantInPartList.append(grantInPart.groupdict()['motion'])
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:COURT GRANTS,? IN PART |GRANTING,? IN PART )(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         grantInPart = re.search('(?P<action>(?:COURT GRANTS,? IN PART |GRANTING,? IN PART ))(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',statement)
                         grantInPartList.append(grantInPart.groupdict()['motion'])
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:COURT GRANTS |GRANTING )(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT,? IN PART )',entryString)
                    for statement in stringList:
                         grantInPart = re.search('(?P<action>(?:COURT GRANTS |GRANTING ))(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)(?P<end>,? IN PART )',statement)
                         grantInPartList.append(grantInPart.groupdict()['motion'])                             
               return str('; '.join(grantInPartList))
     
     def getMotionsFoundMoot(entry):
          #entryString = ET.tostring(entry,method="xml")
          entryString = replaceEntryReferences(entry)
          mootList = []
              
          if not re.search('<docket.description>REPORT (AND)|(&) RECOMMENDATION',entryString) and not re.search('<docket.description>PROPOSED',entryString):
               # Matches "FINDING AS MOOT MOTION #X" syntax
               stringList = re.findall('((?!ATTACHMENTS:.*)(?:FINDING|DENYING|DISMISSING) AS MOOT[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString)
               for statement in stringList:
                    moot = re.search('(?P<action>(?:FINDING|DENYING|DISMISSING) AS MOOT[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    mootList.append(moot.groupdict()['motion'])     
               # Matches "MOTION #X IS DENIED AS MOOT" syntax
               stringList = re.findall('((?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>[^;\n<>]*IS (?:HEREBY )?(?:FOUND|DISMISSED|DENIED) AS MOOT[^;\n<>]*)',entryString)
               for statement in stringList:
                    moot = re.search('(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)(?P<action>[^;\n<>]*IS (?:HEREBY )?(?:FOUND|DISMISSED|DENIED) AS MOOT[^;\n<>]*)',statement)
                    mootList.append(moot.groupdict()['motion'])
               # Matches "THE COURT FINDS AS MOOT MOTION #X" syntax
               stringList = re.findall('((?!ATTACHMENTS:.*)COURT (?:FINDS|DENIES|DISMISSES) AS MOOT[^;\n<>]*<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString)
               for statement in stringList:
                    moot = re.search('(?P<action>COURT (?:FINDS|DENIES|DISMISSES) AS MOOT[^;\n<>]*)(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    mootList.append(moot.groupdict()['motion'])
               mootList = list(set(mootList)) # drop duplicates
               # Look for text-only matches (no entry link)
               if mootList == []:
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT IS (?:HEREBY )?(?:FOUND|DISMISSED|DENIED) AS MOOT)',entryString)
                    for statement in stringList:
                         moot = re.search('(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)(?P<action> IS (?:HEREBY )?(?:FOUND|DISMISSED|DENIED) AS MOOT)',statement)
                         mootList.append(moot.groupdict()['motion'])
                    stringList = re.findall('((?!ATTACHMENTS:.*)(?:COURT (?:FINDS|DISMISSES|DENIES) AS MOOT |(?:FINDING|DISMISSING|DENYING) AS MOOT )(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         moot = re.search('(?P<action>(?:COURT (?:FINDS|DISMISSES|DENIES)|(?:FINDING|DISMISSING|DENYING)) AS MOOT )(?P<motion>(?:DEFENDANT|PLAINTIFF)\'?S?\'? MOTION FOR (?:PARTIAL)?SUMMARY JUDGMENT)',statement)
                         mootList.append(moot.groupdict()['motion'])                        
               return str('; '.join(mootList))

     # Return list of motions opposed
     def getOppositionBriefs(entry):
          #entryString = ET.tostring(entry,method="xml")
          entryString = replaceEntryReferences(entry)
          oppositionList = []
          
          if not re.search('MOTION FOR EXTENSION OF TIME',entryString):
               # Matches "MEMORANDUM/RESPONSE/BRIEF IN OPPOSITION TO/RE #X" syntax
               stringList = re.findall('(<docket.description>(?:AMENDED )?(?:MEMORANDUM|RESPONSE(?:/MEMORANDUM)?|BRIEF) IN OPPOSITION[^;\n<>]*(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString)
               for statement in stringList:
                    opposition = re.search('(?P<oppotag><docket.description>(?:AMENDED )?(?:MEMORANDUM|RESPONSE(?:/MEMORANDUM)?|BRIEF) IN OPPOSITION[^;\n<>]*(?!ATTACHMENTS:.*))(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)
                    oppositionList.append(opposition.groupdict()['motion'])
               # Look for text-only matches (no entry link)
               if oppositionList == []:
                    stringList = re.findall('(<docket.description>(?:AMENDED )?(?:MEMORANDUM|RESPONSE(?:/MEMORANDUM)?|BRIEF) IN OPPOSITION[^;\n<>]*MOTION FOR (?:PARTIAL )?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         opposition = re.search('(?P<oppotag><docket.description>(?:AMENDED )?(?:MEMORANDUM|RESPONSE(?:/MEMORANDUM)?|BRIEF) IN OPPOSITION[^;\n<>]*)(?P<motion>(MOTION FOR (?:PARTIAL )?SUMMARY JUDGMENT))',statement)
                         oppositionList.append(opposition.groupdict()['motion'])                  
               return str('; '.join(oppositionList))
     
     # Return list of reply filings
     def getReplyBriefs(entry):
          #entryString = ET.tostring(entry,method="xml")
          entryString = replaceEntryReferences(entry)
          replyList = []
          if not re.search('MOTION FOR EXTENSION OF TIME',entryString):
               # Matches any syntax starting with "REPLY" or "MEMORANDUM IN REPLY" "TO/RE #X"
               stringList = re.findall('(<docket.description>(?:AMENDED )?(?:CLAIMANT(?:\')?S(?:\')? )?(?:DEFENDANT(?:\')?S(?:\')? )?(?:PLAINTIFF(?:\')?S(?:\')? )?(?:MEMORANDUM IN )?(?:REPLY|RESPONSE IN SUPPORT) [^;\n<>]*(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString)
               for statement in stringList:
                    reply = re.search('(?P<replytag><docket.description>(?:AMENDED )?(?:CLAIMANT(?:\')?S(?:\')? )?(?:DEFENDANT(?:\')?S(?:\')? )?(?:PLAINTIFF(?:\')?S(?:\')? )?(?:MEMORANDUM IN )?(?:REPLY|RESPONSE IN SUPPORT) [^;\n<>]*(?!ATTACHMENTS:.*))(?P<opentag><links\.to\.entry\.number>)(?P<motion>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',statement)               
                    replyList.append(reply.groupdict()['motion'])
               # Look for text-only matches (no entry link)
               if replyList == []:
                    stringList = re.findall('(<docket.description>(?:AMENDED )?(?:CLAIMANT(?:\')?S(?:\')? )?(?:DEFENDANT(?:\')?S(?:\')? )?(?:PLAINTIFF(?:\')?S(?:\')? )?(?:MEMORANDUM IN )?(?:REPLY|RESPONSE IN SUPPORT) [^;\n<>]*MOTION FOR (?:PARTIAL )?SUMMARY JUDGMENT)',entryString)
                    for statement in stringList:
                         reply = re.search('(?P<replytag><docket.description>(?:AMENDED )?(?:CLAIMANT(?:\')?S(?:\')? )?(?:DEFENDANT(?:\')?S(?:\')? )?(?:PLAINTIFF(?:\')?S(?:\')? )?(?:MEMORANDUM IN )?(?:REPLY|RESPONSE IN SUPPORT) [^;\n<>]*)(?P<motion>MOTION FOR (?:PARTIAL )?SUMMARY JUDGMENT)',statement)
                         replyList.append(reply.groupdict()['motion'])                 
               return str('; '.join(replyList))
          
     def getNoticeOfAppeal(entry):
          #entryString = ET.tostring(entry,method="xml")
          entryString = replaceEntryReferences(entry)
          appealList = []
          if not re.search('MOTION FOR EXTENSION OF TIME',entryString):
               # NOTICE OF APPEAL RE: #X"
               #stringList = re.findall('(<docket.description>(?:AMENDED )?(?:JOINT )?NOTICE OF APPEAL [^;\n<>]*(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString)
               if re.search('(<docket.description>(?:AMENDED )?(?:JOINT )?NOTICE OF APPEAL [^;\n<>]*(?!ATTACHMENTS:.*)<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>)',entryString):
                    linkList = re.findall('<links\.to\.entry\.number>\d{1,5}</links\.to\.entry\.number>',entryString)
                    for link in linkList:
                         appeal = re.search('(?P<opentag><links\.to\.entry\.number>)(?P<order>\d{1,5})(?P<closetag></links\.to\.entry\.number>)',link)               
                         appealList.append(appeal.groupdict()['order'])
               # Look for text-only matches (no entry link)
               if appealList == []:
                    appeal = re.search('(?P<appealtag><docket.description>(?:AMENDED )?(?:JOINT )?NOTICE OF APPEAL)',entryString)
                    if appeal is not None:
                         appealList.append('UNKNOWN ORDER')
               return str('; '.join(appealList))              

     def extractInformationFromMatchingEntry(d,e):
          match = re.search(
               '(IN FORMA PAUPERIS)|(IFP)|(FEE WAIVER)|(WAIVER OF FEE)',
               d.upper()
          )
          # re.search(
          #      "(" +
          #      "MOTION FOR (?:PARTIAL\s)?SUMMARY JUDGMENT" +
          #      ")",
          #      d.upper()
          # )
          if not match:
               match = re.search(
                    "(" +
                    "NOTICE OF APPEAL" +
                    ")",
                    d.upper()
               )
          if not match:
               match = re.search(
                    "(" +
                    "INTERLOCUTORY|CERTIFICATE OF APPEALABILITY| 1292 | 1292\)" +
                    ")",
                    d.upper()
               ) 
          if match:
               object.ifConditionContainer['entryText'].append(re.sub("\s+$",'',d))
               dateText = getValue('date',e)
               object.ifConditionContainer['dateEntry'].append(dateText)
               entryNumberDummy = getValue('number',e)
               if entryNumberDummy == '':
                    entryNumberDummy = getValueNested(['number','number.block'],e)
               object.ifConditionContainer['entryNumber'].append(entryNumberDummy)
               object.ifConditionContainer['entryReferences'].append(getEntryReferences(e))
               object.ifConditionContainer['motionsGranted'].append(getMotionsGranted(e))
               object.ifConditionContainer['motionsDenied'].append(getMotionsDenied(e))
               object.ifConditionContainer['motionsGrantedInPart'].append(getMotionsGrantedInPart(e))
               object.ifConditionContainer['motionsFoundMoot'].append(getMotionsFoundMoot(e))
               object.ifConditionContainer['oppositionBriefs'].append(getOppositionBriefs(e))
               object.ifConditionContainer['replyBriefs'].append(getReplyBriefs(e))
               object.ifConditionContainer['noticeOfAppeal'].append(getNoticeOfAppeal(e))
               object.ifConditionContainer['motionFlag'].append(getMotionFlag(d))
               object.ifConditionContainer['movingParty'].append(getMovant(object,d))
               object.ifConditionContainer['orderFlag'].append(getOrderFlag(d))
               object.ifConditionContainer['oppositionFlag'].append(getOppositionFlag(d))
               object.ifConditionContainer['replyFlag'].append(getReplyFlag(d))
               object.ifConditionContainer['interlocFlag'].append(getInterloc(d))

     def getEntriesList(block):
          return block.findall("./docket.entry")

     def extractInformationFromMatchingEntries(entriesList):
          for e in entriesList:
               d = getFullTextOfDocketDescription(e)
               if type(d) is not str:
                    continue
               extractInformationFromMatchingEntry(d,e)

     def processEntriesList(object,block):
          initializeObjectIfConditionContainers(object,['dateEntry','entryNumber','entryText','entryReferences','motionsGranted','motionsDenied','motionsGrantedInPart','motionsFoundMoot','oppositionBriefs','replyBriefs','motionFlag','movingParty','orderFlag','oppositionFlag','replyFlag','noticeOfAppeal','interlocFlag'])
          entriesList = getEntriesList(block)
          extractInformationFromMatchingEntries(entriesList)

     #######################################
     ### start main procedure code block ###
     #######################################

     block = getDocketEntriesBlock(object.docket)
     globOfText = makeGlobOfText(getDocketEntriesBlock(object.docket))
     gotCaseMatchFlag = makeCaseMatchFlag(globOfText)

     if gotCaseMatchFlag is False:
          return False
     else:
          processEntriesList(object,block)
          object.ifConditionContainer['noticeOfRemovalFlag'] = getNoticeOfRemovalFlag(globOfText)
          return True
     ##### END thisIfConditionFunction FUNCTION DEF #####


def pdf(object):
     """
     Sample processDocketFunction function. 
     MUST RETURN A LIST! First item will be written to csv file
     """
     def makeFixedReturnString(object):
          docket = object.docket
          primaryTitle = getValue('primary.title',docket).replace('"','')
          court        = getCourt(getValue('court',docket))
          judge        = getJudgeName(docket)
          plaintiffs   = getPlaintiffs(docket)
          defendants   = getDefendants(docket)
          docketNumber = getValueNested(['docket.number','docket.block'],docket)
          filingDate   = getValueNested(['filing.date', 'filing.date.block'],docket)
          closedDate   = getDateClosed(docket)
          natureOfSuit = getNatureOfSuit(docket)
          natureOfSuitCode = getNatureOfSuitCode(docket)
          noticeOfRemovalFlag = object.ifConditionContainer['noticeOfRemovalFlag']
          docketFileName = object.docketFileName
          fixedReturnList = [primaryTitle,court,judge,plaintiffs,defendants,docketNumber,filingDate,closedDate,natureOfSuit]
          fixedReturnList = doubleQuote(cleanUpHTMLQuotes(fixedReturnList))
          fixedReturnList.extend([natureOfSuitCode,noticeOfRemovalFlag])
          fixedReturnList.append(doubleQuote(docketFileName))
          fixedReturnString = ''
          for i,f in enumerate(fixedReturnList):
               fixedReturnString += str(f) + ','
          return fixedReturnString

     def makeEntryReturnString(object,date,i):
          #may need to deal with edge case in which dateEntry=[] - need to add commas and newline char
          dateEntry = object.ifConditionContainer['dateEntry']
          entryNumber = object.ifConditionContainer['entryNumber']
          entryText = object.ifConditionContainer['entryText']
          entryReferences = object.ifConditionContainer['entryReferences']
          motionsGranted = object.ifConditionContainer['motionsGranted']
          motionsDenied = object.ifConditionContainer['motionsDenied']
          motionsGrantedInPart = object.ifConditionContainer['motionsGrantedInPart']
          motionsFoundMoot = object.ifConditionContainer['motionsFoundMoot']
          oppositionBriefs = object.ifConditionContainer['oppositionBriefs']
          replyBriefs = object.ifConditionContainer['replyBriefs']          
          motionFlag = object.ifConditionContainer['motionFlag']
          movingParty = object.ifConditionContainer['movingParty']
          orderFlag = object.ifConditionContainer['orderFlag']
          oppositionFlag = object.ifConditionContainer['oppositionFlag']
          replyFlag = object.ifConditionContainer['replyFlag']
          noticeOfAppeal = object.ifConditionContainer['noticeOfAppeal']
          interlocFlag = object.ifConditionContainer['interlocFlag']
          return (doubleQuote(dateEntry[i]) + ',' + entryNumber[i] + ',' + str(motionFlag[i]) + ',' + str(movingParty[i]) + ',' + str(orderFlag[i]) + ',' + str(oppositionFlag[i]) + ',' + str(replyFlag[i]) + ',' + doubleQuote(entryText[i].replace('"',"|"))
                  + ',' + str(entryReferences[i]) + ',' + str(motionsGranted[i]) + ',' + str(motionsDenied[i]) + ',' + str(motionsGrantedInPart[i]) + ',' + str(motionsFoundMoot[i]) + ',' + str(oppositionBriefs[i]) + ',' + str(replyBriefs[i]) + ',' + str(noticeOfAppeal[i]) + ',' + str(interlocFlag[i]))

     def getNumberOfDateEntries(object):
          return len(object.ifConditionContainer['dateEntry'])

     def makeLongReturnString(object):
          fixedReturnString = makeFixedReturnString(object)
          longReturnString = ''
          numberOfDateEntries = getNumberOfDateEntries(object)
          for i, date in enumerate(range(numberOfDateEntries)):
               longReturnString += fixedReturnString
               longReturnString += makeEntryReturnString(object,date,i)
               longReturnString += '\n'
          return longReturnString

     ############################################################
     ##### BEGIN MAIN PROCEDURE CODE BLOCK FOR pdf FUNCTION #####
     ############################################################

     if thisIfConditionFunction(object):
          return makeLongReturnString(object)
     else: return ''

################
# BOTTOM STUFF #
################
#myList = os.listdir("/data2/dockets/")
#searchAll = re.compile('.*xml$').search
searchAll = re.compile('.*OctDec2012.*30.*xml$').search # Use this to test code on small sample file
# This just restricts to a single file
listOfAllFiles = [ '/data2/dockets/'+l 
                    for l in os.listdir("/data2/dockets/") 
                    for m in (searchAll(l),) if m]
# For some reason the job keeps terminating with ~100 files left to go. The remaining files are:
#listOfAllFiles = ['/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+2.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+20.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+21.onxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+22.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+23.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+24.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+25.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+26.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+27.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+28.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+29.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+3.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+30.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+31.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+32.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+33.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+4.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+5.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+6.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+7.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+8.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+9.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+1.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+10.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+11.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+12.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+13.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+14.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+15.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+16.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+17.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+18.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+19.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+2.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+20.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+21.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+22.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+23.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+24.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+25.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+26.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+27.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+28.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+29.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+3.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+30.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+31.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+32.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+33.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+34.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+4.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+5.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+6.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+7.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+8.nxo_extracted_out.xml', '/data2/dockets/NFEDDIST_OctDec2012Yale.Extract+9.nxo_extracted_out.xml', '/data2/dockets/Remaining2005guids_N_DFEDDIST00_20120411.nxo_extracted_out.xml', '/data2/dockets/Remaining2006guids_N_DFEDDIST00_201204000000.nxo_extracted_out.xml', '/data2/dockets/Remaining2007guids_N_DFEDDIST00_201204000000.nxo_extracted_out.xml', '/data2/dockets/Remaining2008guids_N_DFEDDIST00_201204000000.nxo_extracted_out.xml', '/data2/dockets/Remaining2009guids_N_DFEDDIST00_20120406124739.nxo_extracted_out.xml', '/data2/dockets/Remaining2010_guids_N_DFEDDIST00_20120405100601.nxo_extracted_out.xml', '/data2/dockets/Remaining2011guids_N_DFEDDIST00_20120406101705.nxo_extracted_out.xml']
#listOfAllFiles = ['/data2/dockets/NFEDDIST_JulySept2012Yale.Extract+28.nxo_extracted_out.xml']
print listOfAllFiles

def printHeaderMaterial(listOfFiles):
     logging.info("List of files:\n\t%s" , listOfFiles)
     logging.info("Number of files=%s", len(listOfFiles))
     logging.info("Datetime at start is %s", dt.now())

def mainLoopFunction(listOfFiles):
     myFirstLine="primarytitle,court,judge,plaintiffs,defendants,docketnumber,filingdate,closeddate,natureofsuit,natureofsuitcode,noticeofremovalflag,wlfilename,dateentry,entrynumber,motionflag,movingparty,orderflag,oppositionflag,replyflag,entrytext,entryrefs,granted,denied,grantedinpart,mooted,opposed,replied,appealed,interlocflag\n"
     for file in listOfFiles:
     #for file in ['/data2/dockets/NFEDDISTCV01Dec2014Part1Yale.Extracts+1.nxo_extracted_out.xml']:
     #for file in ['/data2/dockets/NFEDDISTCV02Dec2014Part2Yale.Extracts+3.nxo_extracted_out.xml']:
     #for file in ['/data2/dockets/NFEDDIST2005Yale.Extracts+1.nxo_extracted_out.xml']:
          logging.info("Starting %s", file)
          docketsFileReader(file,
                            processDocketFunction=pdf,
                            firstLine=myFirstLine,
                            logger=mylogger,
                            useDocketEntries=False
                            )
          logging.info("Done with file %s.", file)
     logging.info("Datetime at end is %s.\n\tDONE.", dt.now())


#################################
##### MAIN PROCEDURAL BLOCK #####
#################################

printHeaderMaterial(listOfAllFiles)
mainLoopFunction(listOfAllFiles)

