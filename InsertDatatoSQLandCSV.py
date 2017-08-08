import csv
import sqlite3
import codecs
import pprint
import re
import xml.etree.cElementTree as ET

import cerberus

import schema

OSM_PATH = "RaleighStreetData"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

SCHEMA = schema.schema

street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

'''
dictionaries for the mapping of mispelled street abbreviations, city names, or
zipcodes so that the data can be cleaned properly
'''

ZIPCODE_MAPPINGS = {'NC 27587': '27587', '2612-6401': ''}

EXPECTED = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place",
            "Square", "Lane", "Road",
            "Trail", "Parkway", "Commons"]

STATE_MAPPINGS = {'nc': 'North Carolina', 'NC-': 'North Carolina', 'NC': 'North Carolina',
        'N. Carolina': 'North Carolina', 'N.C.': 'North Carolina'}

MAPPING = {"St": "Street",
           "St.": "Street",
           'ST': 'Street',
           'St,': 'Street',
           'Ave.': 'Avenue',
           'Ave': 'Avenue',
           'Blvd': 'Boulevard',
           'Blvd.': 'Boulevard',
           'Rd.': 'Road',
           'Rd': 'Road',
           'CIrcle': 'Circle',
           'Cir': 'Circle',
           'Ct': 'Court',
           'Dr': 'Drive',
           'Dr.': 'Drive',
           'Ext': 'Extension',
           'LaurelcherryStreet': 'Laurel Cherry Street',
           'Ln': 'Lane',
           'Pkwy': 'Parkway',
           'Pky': 'Parkway',
           'Pl': 'Place',
           'PI': 'Place'}

CITY_MAPPINGS = {'Apex, NC': 'Apex', 'Ralegh': 'Raleigh', 'Ralegih': 'Raleigh',
                 'Wake forest': 'Wake Forest', 'cary': 'Cary', 'durham': 'Durham',
                 'wake Forest': 'Wake Forest', ' Raleigh': 'Raleigh',
                 'raleigh': 'Raleigh'}

# Make sure the fields order in the csvs matches the column order
# in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version',
               'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

def shape_dict(child_dict):
    '''
    this function takes in the shape element dictionary and cleans the data
    of any errors or inconsistencies in spelling or abbreviations and changes
    them to fit a uniform spelling i.e. Street instead of St. or ST.  It does
    the same for city, and state data as well by using mapping dictionaries.
    For zipcodes it removes the last four digits and
    strips of lettering and white space
    '''

    if child_dict['type'] == 'addr':
        if child_dict['key'] == 'city':
            try:
                child_dict['value'] = CITY_MAPPINGS[child_dict['value']]
            except KeyError:
                pass
        elif child_dict['key'] == 'state':
            try:
                child_dict['value'] = STATE_MAPPINGS[child_dict['value']]
            except KeyError:
                pass
        elif child_dict['key'] == 'postcode':
            try:
                child_dict['value'] = ZIPCODE_MAPPINGS[child_dict['value']]
            except KeyError:
                child_dict['value'] = child_dict['value'][0:5]
        elif child_dict['key'] == 'street':
            street_split = child_dict['value'].split()
            for index in range(len(street_split)):
                try:
                    street_split[index] = MAPPING[street_split[index]]
                except KeyError:
                    pass
            child_dict['value'] = ' '.join(street_split)


    return child_dict

def shape_tiger_dict(tiger_list):
    '''
    this function takes in a list holding the TIGER data tags and shapes
    them to fit the normal OSM data of a street address and postcode schemas of
    the other data tags
    '''
    tiger_post_code = {}
    tiger_street_addr = {}
    street_name = []
    zip_code = ''
    tiger_post_code['id'] = tiger_list[0]['id']
    tiger_street_addr['id'] = tiger_list[0]['id']
    tiger_post_code['type'] = 'addr'
    tiger_street_addr['type'] = 'addr'
    tiger_post_code['key'] = 'postcode'
    tiger_street_addr['key'] = 'street'
    for dictionary in tiger_list:
        if dictionary['key'] == 'name_base':
            street_name.append(dictionary['value'])
        if dictionary['key'] == 'name_type':
            street_name.append(dictionary['value'])
        if dictionary['key'] == 'name_direction_suffix':
            street_name.append(dictionary['value'])
        if dictionary['key'] == 'zip_left':
            zip_code = dictionary['value']
    tiger_post_code['value'] = zip_code
    tiger_street_addr['value'] = ' '.join(street_name)

    return (tiger_post_code, tiger_street_addr)

def shape_element(element, node_attr_fields=NODE_FIELDS,
    way_attr_fields=WAY_FIELDS,
    problem_chars=PROBLEMCHARS, default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""
    #this code I wrote from the original problem set however I added the 'type'
    # check to gather the tiger data into the list so that it could be cleaned
    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    tags = []
    if element.tag == 'node':
        for key in element.attrib:
            if key in node_attr_fields:
                node_attribs[key] = element.attrib[key]
        tiger_dict = []
        for child in element.findall('tag'):
            node_dict = {}
            child_dict = child.attrib
            node_dict['id'] = node_attribs['id']
            for key in child_dict:
                if key =='v':
                    node_dict['value']=child_dict['v']
                if key == 'k':
                    if LOWER_COLON.search(child_dict[key]):
                        split_key_value = child_dict[key].split(':', 1)
                        node_dict['key'] = split_key_value[1]
                        node_dict['type'] = split_key_value[0]
                    if PROBLEMCHARS.search(child_dict[key]):
                        node_dict['key']='PASS'
                    if not LOWER_COLON.search(child_dict[key]):
                        node_dict['key'] = child_dict['k']
                        node_dict['type'] = 'regular'
            if node_dict['type'] == 'tiger':
                tiger_dict.append(node_dict)

            node_dict = shape_dict(node_dict)
            if node_dict['key'] == 'PASS':
                pass
            else:
                tags.append(node_dict)

        if tiger_dict:
            for dictionary in shape_tiger_dict(tiger_dict):

                tags.append(shape_dict(dictionary))


    elif element.tag == 'way':
        for key in element.attrib:
            if key in WAY_FIELDS:
                way_attribs[key] = element.attrib[key]

        for child in element.findall('nd'):
            nd_dict = {}
            nd_dict['id']= way_attribs['id']
            nd_dict['node_id']= child.attrib['ref']
            nd_dict['position'] = element.getchildren().index(child)
            way_nodes.append(nd_dict)
        tiger_dict = []
        for child in element.findall('tag'):

            node_dict = {}
            child_dict = child.attrib
            node_dict['id']=way_attribs['id']
            for key in child_dict:
                if key =='v':
                    node_dict['value']=child_dict['v']
                if key == 'k':
                    if LOWER_COLON.search(child_dict[key]):
                        split_key_value = child_dict[key].split(':', 1)
                        node_dict['key'] = split_key_value[1]
                        node_dict['type'] = split_key_value[0]
                    if PROBLEMCHARS.search(child_dict[key]):
                        node_dict['key']='PASS'
                    if not LOWER_COLON.search(child_dict[key]):
                        node_dict['key'] = child_dict['k']
                        node_dict['type'] = 'regular'
            if node_dict['type'] == 'tiger':
                tiger_dict.append(node_dict)
            node_dict = shape_dict(node_dict)
            if node_dict['key'] == 'PASS':
                pass
            else:
                tags.append(node_dict)


        if tiger_dict != []:
            dict_tuple = shape_tiger_dict(tiger_dict)
            street_dict = dict_tuple[1]
            for dictionary in dict_tuple:
                tig_dict = shape_dict(dictionary)
                tags.append(tig_dict)

    if element.tag == 'node':
        return {'node': node_attribs, 'node_tags': tags}
    elif element.tag == 'way':
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


# ================================================== #
#               Helper Functions from problem set    #
# ================================================== #
def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)

        raise Exception(message_string.format(field, error_string))


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, str) else v) for k, v in row.items()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


# ================================================== #
#               Main Function                        #
# ================================================== #
def process_map(file_in, validate):
    """
    Iteratively process each XML element and write to csv(s)
    and insert them into an sql database as well after creating the appropriate
    tables in the database
    """


    connection = sqlite3.connect('Street_Data.db')
    cursor = connection.cursor()
    # opens up the sql script to create each table in the sql database
    # corresponding with nodes, nodes_tags, ways, ways_nodes, ways_tags
    with open('data_wrangling_schema.sql') as street_data:
        sql_commands = street_data.read()

    sql_comm_split = sql_commands.split(';')
    for command in sql_comm_split:
        cursor.execute(command)
    connection.commit()

    with codecs.open(NODES_PATH, 'w') as nodes_file, \ #this is code from the problem set
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = csv.DictWriter(nodes_file, NODE_FIELDS) #this is code I've updated
        node_tags_writer = csv.DictWriter(nodes_tags_file, NODE_TAGS_FIELDS) #to work in Python 3
        ways_writer = csv.DictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = csv.DictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = csv.DictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader() #this is code form the problem set
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node': #the first three lines are from the
                    nodes_writer.writerow(el['node']) #problem set the sql insertion code is mine
                    node_tags_writer.writerows(el['node_tags'])
                    nodes_v_list = [el['node']['id'], el['node']['lat'], el['node']['lon'],
                                    el['node']['user'], el['node']['uid'],
                                    el['node']['version'], el['node']['changeset'],
                                    el['node']['timestamp']]
                    cursor.execute('insert into nodes (id, lat, lon, user, uid,\
                                   version, changeset, timestamp) values\
                                   (?,?,?,?,?,?,?,?);',
                                   nodes_v_list)
                    nodes_tags_list = el['node_tags']
                    for dictionary in nodes_tags_list:
                        tag_list = [dictionary['id'], dictionary['key'], dictionary['value'],
                                    dictionary['type']]
                        cursor.execute('insert into nodes_tags(id, key, value, type)\
                                       values (?, ?, ?, ?);', tag_list)
                        connection.commit()

                elif element.tag == 'way': #the first three lines are problem set code
                    ways_writer.writerow(el['way']) #the sql insertions are my code
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])
                    ways_v_list=[el['way']['id'],
                                 el['way']['user'], el['way']['uid'],
                                 el['way']['version'], el['way']['changeset'],
                                 el['way']['timestamp']]
                    ways_tags_list = el['way_tags']
                    ways_nodes_list = el['way_nodes']

                    cursor.execute('insert into ways (id, user, uid,\
                                   version, changeset, timestamp) values\
                                   (?,?,?,?,?,?);', ways_v_list)
                    connection.commit()
                    for tag in ways_tags_list:
                        tag_list = [tag['id'], tag['key'], tag['value'],
                                    tag['type']]
                        cursor.execute('insert into ways_tags(id, key, value, type)\
                                       values (?, ?, ?, ?);', tag_list)
                        connection.commit()
                    for node in ways_nodes_list:
                        node_list = [node['id'], node['node_id'], node['position']]
                        cursor.execute('insert into ways_nodes (id, node_id, position)\
                                       values (?, ?, ?);', node_list)
                        connection.commit()

if __name__ == '__main__':
    # Note: Validation is ~ 10X slower. For the project consider using a small
    # sample of the map when validating.
    process_map(OSM_PATH, validate=False)
