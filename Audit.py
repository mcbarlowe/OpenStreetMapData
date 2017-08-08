import xml.etree.cElementTree as ET
'''xml.etree.cElementTree is imported to parse the xml file'''
import pprint
'''
This program parses through the lines of an xml file and counts the number of
types of tags and returns the counts as a dictionary
'''
from collections import defaultdict
import re

#this is a test of github
OSMFILE = "RaleighStreetData.osm"
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

EXPECTED = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place",
            "Square", "Lane", "Road",
            "Trail", "Parkway", "Commons"]

EXPECTED_ZIPCODES = ['27602', '27606', '27610', '27614', '27619', '27624',
                     '27628', '27636', '27658', '27676', '27698', '27603',
                     '27607', '27611', '27615', '27620', '27625', '27640',
                     '27661', '27690', '27560', '27604', '27608', '27612',
                     '27616', '27621', '27626', '27634', '27650', '27668',
                     '27695', '27601', '27605', '27609', '27613', '27617',
                     '27622', '27627', '27627', '27635', '27656', '27675',
                     '27697']

EXPECTED_STATE = ['North Carolina']

def audit_street_type(street_types, street_name):
    '''
    this function takes in a list of expected street endings and
    searches the given street to see if those endings are in the
    name of the street if not it adds the street name to a dict
    '''
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type not in EXPECTED:
            street_types[street_type].add(street_name)


def audit_zip_type(zip_types, zip_codes):
    '''
    this function takes in a list of expected zipcodes and
    searches the given street to see if those endings are in the
    name of the street if not it adds the street name to a dict
    '''
    if zip_codes not in EXPECTED_ZIPCODES:
        zip_types.add(zip_codes)

def audit_city(city_dict, city):
        try:
            city_dict[city] += 1
        except:
            city_dict[city] = 1

def is_city(elem):
    return elem.attrib['k'] == 'addr:city'
def audit_state(state_types, state):
    '''
    this function takes in a list of expected street endings and
    searches the given street to see if those endings are in the
    name of the street if not it adds the street name to a dict
    '''
    if state not in EXPECTED_STATE:
        state_types.add(state)

def audit_tiger(tiger_dict, tiger_key, tiger_value):
        tiger_dict[tiger_key].add(tiger_value)


def is_tiger_data(elem):
    '''
    looks at 'k' value of tag element and checks to see whether it
    came from the tiger set of data
    '''
    return elem.attrib['k'][0:5] == 'tiger'

def is_street_name(elem):
    '''
    function takes in an element and checks the 'k' value to see if it
    is equal to a street address and returns true if so
    '''
    return elem.attrib['k'] == "addr:street"

def is_post_code(elem):
    '''
    checks an element's key tag to see whether it is a zip
    code tag or not
    '''
    return elem.attrib['k'] == 'addr:postcode'

def is_state(elem):
    '''
    checks element to see if the key is for nodes to see
    whereter it is a state node or not
    '''
    return elem.attrib['k'] == 'addr:state'

def count_tags(filename):
    '''
    function reads in an xml file and parses through the lines
    counting each type of node and storing it into a dictionary
    it uses a try except block incase the node has not yet been
    put in the tag_count_dict to avoid a KeyException error
    '''
    tag_count_dict = {}
    tree = ET.parse(filename)
    for element in tree.iter():
        for key in element.attrib.keys():
            if key == 'k':
                try:
                    tag_count_dict[element.attrib[key]] += 1
                except KeyError:
                    tag_count_dict[element.attrib[key]] = 1


    return tag_count_dict

def audit(osmfile):
    '''
    this function takes in the xml file and takes a look at the tags
    with street, zipcode, and state values and compares them against an expected
    and returns the values that don't fall in those values
    '''
    state_set = set()
    tiger_types = defaultdict(set)
    zipcode_set = set()
    street_types = defaultdict(set)
    city_set = {}
    with open(osmfile, 'r') as osm_file:
        for event, elem in ET.iterparse(osm_file, events=("start",)):
            if elem.tag == "node" or elem.tag == "way":
                for tag in elem.iter("tag"):
                    if is_street_name(tag):
                        audit_street_type(street_types, tag.attrib['v'])
                    elif is_post_code(tag):
                        audit_zip_type(zipcode_set, tag.attrib['v'])
                    elif is_state(tag):
                        audit_state(state_set, tag.attrib['v'])
                    elif is_tiger_data(tag):
                        audit_tiger(tiger_types, tag.attrib['k'], tag.attrib['v'])
                    elif is_city(tag):
                        audit_city(city_set, tag.attrib['v'])


    osm_file.close()
    return street_types, zipcode_set, state_set, tiger_types, city_set
def main():

    TAGS = audit(OSMFILE)
    pprint.pprint(TAGS)
    next_tags = count_tags(OSMFILE)
    pprint.pprint(next_tags)

if __name__== '__main__':
    main()

