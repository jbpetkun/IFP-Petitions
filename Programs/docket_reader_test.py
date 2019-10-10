import glob, os
import xml.etree.ElementTree as ET
import pandas as pd 

path = "/Users/jbpetkun/Dropbox (MIT)/Research/CJRA/Data/Raw/SummaryJudgmentDockets/"
os.chdir(path)
xml_list = glob.glob('./*.xml')

tree = ET.parse(xml_list[0])
root = tree.getroot()


docket_desc_iter = root.iter('docket.description')
docket_link_iter = root.iter('links.to.entry.number')

def next_docket_description():
    print(next(docket_desc_iter).text)

def next_docket_description_tail():
    print(next(docket_desc_iter).tail)

def next_docket_link():
    print(next(docket_link_iter).text)

def next_docket_link_tail():
    print(next(docket_link_iter).tail)

df = pd.DataFrame()

#df['docket_entry_descriptions'] = [entry.text for entry in docket_desc_iter]

df['docket_entry_descriptions'] = [ET.tostring(entry) for entry in docket_desc_iter]

df['docket_links'] = [link.text for link in docket_link_iter]

df['docket_link_tails'] = [link.tail for link in docket_link_iter]
