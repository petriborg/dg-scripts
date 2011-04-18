#!/usr/bin/python
#
# this was built on Ubuntu 10.04 - assumptions have been made
#

from __future__ import with_statement
from contextlib import contextmanager
from lxml import etree
import subprocess as sub
import sqlite3 as db_api
import traceback as tb
import os, sys, re, json, getopt, codecs


# global configuration variables
xml_parser = etree.XMLParser(recover=True)
sessionid = None
database = None
connection = None
todays_day_id = None
day_timeout = '-22 hours'

# turn
turn_url = "http://davesgalaxy.com/lastreport/"

# fleet
fleet_list_url = "http://davesgalaxy.com/fleets/list/all/%s/"

# planet
planet_list_url = 'http://davesgalaxy.com/planets/list/all/%s/'
planet_info_url = 'http://davesgalaxy.com/planets/%s/info/'
planet_manage_url = 'http://davesgalaxy.com/planets/%s/manage/'
planet_budget_url = 'http://davesgalaxy.com/planets/%s/budget/'
planet_upgrade_url = 'http://davesgalaxy.com/planets/%s/upgradelist/'


@contextmanager
def transaction():
    global connection
    if database is None:
        raise Exception("No database!")
    if connection is None:
        connection = db_api.connect(database)
    cursor = connection.cursor()
    try:
        yield cursor
    except:
        connection.rollback()
        raise
    else:
        connection.commit()

def get_cookie():
    return "sessionid=%s" % sessionid

#
# pull the page and pipe to stdout, this is read by sub.Popen call
#

def wget(*args):
    "swapable pull method using wget"
    return ['wget', '--load-cookies=cookies.txt', '-q', '-O-'] + list(args)

def curl(*args):
    "swappable pull method using curl"
    return ['curl', '--silent', '-b', get_cookie()] + list(args)

def cat(*args):
    "fake swappable pull method"
    return ['cat', 'data/test_planets_list_all_1']

#
# database and parsing functions
#

def find_todays_id(new_day=False):
    "Get todays day_id"
    global todays_day_id
    if todays_day_id is None:
        with transaction() as c:
            query = c.execute("""
                select day_id from days
                where creation_time > datetime('now', ?)
                order by creation_time desc limit 1""", (day_timeout,));
            data = query.fetchall()
            if len(data) > 0 and not new_day:
                day_id = data[0][0]
                print "Fetched from DB day:", day_id
                todays_day_id = day_id
            else:
                # insert an "empty" row - defaults will be used
                query = c.execute("insert into days (day_id) select null")
                todays_day_id = query.lastrowid
    print "Today's id:", todays_day_id
    return todays_day_id

def curl_raw_page(url):
    "Pull the page from the web, and push it into the DB"
    print "Fetching from web", url
    proc = sub.Popen(curl(url), stdout=sub.PIPE)
    raw_page = proc.stdout.read()

    with transaction() as c:
        c.execute("""insert into raw_pages 
            (day_id, url, page) values (?, ?, ?)""", 
            (todays_day_id, url, raw_page,))

    return raw_page

def get_raw_page(url):
    "Check if raw-page is in the DB, else pull from the web"
    with transaction() as c:
        pages_query = c.execute("""
            select page from raw_pages
            where day_id = ?
              and url = ?
            limit 1""", (todays_day_id, url) );
        pages_data = pages_query.fetchall()
        if len(pages_data) > 0:
            #print "Fetching from DB", url
            raw_page = pages_data[0][0]
            #print raw_page
            return raw_page
    raw_page = curl_raw_page(url)
    return raw_page

def dump_page(page, url=None, e=None):
    "writes page to disk for inspection"
    fn = url[23:].replace('/','_')
    print "Dump", fn
    fd = codecs.open(fn, 'w', 'utf-8-sig')
    if url is not None:
        fd.write(url)
        fd.write("\n\n")
    if e is not None:
        fd.write(e)
        fd.write("\n\n")
    fd.write(page)
    fd.close()

def get_xml(url, json_key='tab', save_xml=False):
    "get 'url' somehow, then decode the json, and xml into a element tree"
    raw_page = get_raw_page(url)
    json_decoder = json.JSONDecoder()
    json_obj = json_decoder.decode(raw_page)
    xml_page = json_obj.get(json_key)
    if xml_page is None:
        print "Unmatched json key", json_key
        return None
    xml_page = xml_page.strip()
    try:
        xml_obj = etree.fromstring(xml_page, xml_parser)
    except etree.XMLSyntaxError, e:
        print e
        dump_page(xml_page, url, e)
        raise
    if save_xml:
        dump_page(xml_page, url)
    return xml_obj

def get_page_count(root_elem):
    "read the list/all page to find the number of page count"
    paginator = root_elem.xpath('//div[@class="paginator"]')[0]
    count = len(paginator.getchildren())
    return count

def clean(key_str):
    "strip and redress a value or key for db insert"
    key_str = key_str.strip().replace(' ', '_')
    m = re.search('[^:\s]+', key_str)
    if m:
        key_str = m.group()
    return key_str.lower()

def insert_planets(planets_elem):
    "insert info about a planet"

    def get_planet_number(tr_elem):
        js_text = tr_elem.get('onmouseover')
        planet_number = js_text.split("'")[1]
        return planet_number

    for planet in planets_elem:
        planet_number = get_planet_number(planet)
        planet_name = planet.xpath('td[5]')[0].text
        print "%s: %s" % (planet_name, planet_number)

        with transaction() as c:
            c.execute("""
                insert or ignore into planets
                (planet_id, name) values (?, ?)""",
                (planet_number, planet_name))

def insert_planet_data(planet_table, planet_data):
    with transaction() as c:
        sorted_keys = planet_data.keys()
        sorted_keys.sort()
        keys_count = len(sorted_keys)
        sorted_values = map(lambda k: str(planet_data.get(k)), sorted_keys)
        keys_str = ', '.join(sorted_keys)
        qs_str = ', '.join( (keys_count*('?',)) )
        query_str = """
            insert into %s 
            (%s) values (%s)""" % (planet_table, keys_str, qs_str)
        c.execute(query_str, sorted_values)

def planet_data_check(planet_table, planet_id):
    "check if we've processed this planet already today"
    with transaction() as c:
        info_query = """
            select planet_id from %s 
            where planet_id=%s 
              and day_id=%s""" % (
            planet_table, planet_id, todays_day_id)
        #print info_query
        data = c.execute(info_query).fetchall()
        return len(data) > 0
 

### planet info panel ####################################################
def planet_info(planet_id):
    "insert planet data from the info-panel"

    if planet_data_check('planet_info', planet_id):
        return

    # we haven't processed it, so do it already
    result = dict(planet_id=planet_id, day_id=todays_day_id)

    root = get_xml(planet_info_url % planet_id)

    society_level = root.xpath('//div[@class="info1"]/div[3]/text()')[0]
    result['society_level'] = society_level
    print "society_level:", society_level

    # fetch the repeatable tables
    info_table_elems = root.xpath('//table')

    # the first table
    tr_elems = info_table_elems[0].xpath('tr')
    for tr_elem in tr_elems:
        k = clean(tr_elem.getchildren()[0].text)
        v = tr_elem.getchildren()[1].text
        if k in ('name', 'owner'):
            continue
        if k == 'treasury':
            v = v.split()[0]
        v = clean(v)
        print "%s: %s" % (k,v)
        result[k] = v

    # the second table
    tr_elems = info_table_elems[1].xpath('tr[td]')
    for tr_elem in tr_elems:
        td_elems = tr_elem.getchildren()
        k = clean(td_elems[0].text)
        v_now = clean(td_elems[1].text)
        v_next = clean(td_elems[2].text)
        v_price = clean(td_elems[3].text)
        print "%s: %s, %s, %s" % (k, v_now, v_next, v_price)
        result[k+"_on_hand"] = v_now
        result[k+"_next_production"] = v_next
        result[k+"_price"] = v_price

    insert_planet_data('planet_info', result)

### planet budget panel ##################################################
def planet_budget(planet_id):

    if planet_data_check('planet_budget', planet_id):
        return

    # we haven't processed it, so do it already
    result = dict(planet_id=planet_id, day_id=todays_day_id)
 
    budget_xml_obj = get_xml(planet_budget_url % planet_id)

    table_elems = budget_xml_obj.xpath('//table//table')

    credits_table = table_elems[0]
    debits_table = table_elems[1]

    # itemized tables
    tr_elems = credits_table.xpath('tr') + debits_table.xpath('tr')
    for tr_elem in tr_elems:
        k = clean(tr_elem.getchildren()[0].text)
        v = clean(tr_elem.getchildren()[1].text)
        print "%s: %s" % (k,v)
        result[k] = v

    # totals tables
    total_credits = table_elems[2].xpath('tr[2]/td/text()')[0]
    total_debits = table_elems[3].xpath('tr[2]/td/text()')[0]
    budget_surplus = table_elems[4].xpath('tr[2]/td/text()')[0]

    print "total_credits:", total_credits
    print "total_debits:", total_debits
    print "budget_surplus:", budget_surplus

    result['total_credits'] = total_credits
    result['total_debits'] = total_debits
    result['budget_surplus'] = budget_surplus

    insert_planet_data('planet_budget', result)

### planet upgrade panel #################################################
def planet_upgrade(planet_id):
    upgrade_xml_obj = get_xml(planet_upgrade_url % planet_id)

### planet manage panel ##################################################
def planet_manage(planet_id):
    manage_xml_obj = get_xml(planet_manage_url % planet_id)





def main():
    global sessionid, database, todays_day_id

    new_day = False

    try:
        (opts,args) = getopt.getopt(sys.argv[1:], 'h', 
            ['help', 'new', 'day=', 'sessionid=', 'database='])
        print 'opts:',opts
        print 'args:',args
        for (opt,val) in opts:
            print "opt:",opt,"val:",val
            if opt in ('-h',):
                print "No help monkey!"
                sys.exit(2)
            elif opt in ('--sessionid',):
                sessionid = val
            elif opt in ('--database',):
                database = val
            elif opt in ('--new',):
                new_day = True
            elif opt in ('--day'):
                todays_day_id = int(val)
            else:
                print "Unknown option:",opt
                sys.exit(2)
    except getopt.GetoptError, e:
        print e
        sys.exit(2)
    
    print "database:",database
    print "sessionid:",sessionid
    
    # fetch, or create the day_id
    find_todays_id(new_day=new_day)
    
    # fetch the planet list
    xml_obj = get_xml(planet_list_url % 1)
    insert_planets(xml_obj.xpath('/div//tr[@class="fleetrow"]'))
    page_count = get_page_count(xml_obj)
    print "found %d pages" % page_count

    if page_count > 1:
        for i in range(1, page_count+1):
            index = i+1
            url = planet_list_url % i
            xml_obj = get_xml(url)
            insert_planets(xml_obj.xpath('/div//tr[@class="fleetrow"]'))

    # fetch all the planets for day_id
    with transaction() as c:
        # find all the planets that we owned for todays_day_id
        query = c.execute("""
            select p.planet_id from planets p, days d
            where date(p.creation_time) <= date(d.creation_time)
              and d.day_id = ?
            """, (todays_day_id,))
        planet_ids = query.fetchall()
    print "planet ids:", len(planet_ids)
    
    #planet_ids = (planet_ids[0],)
    
    # process all the planet info for day_id
    for planet_id_tuple in planet_ids:
        planet_id = planet_id_tuple[0]

        planet_info(planet_id)
        planet_manage(planet_id)
        planet_budget(planet_id)
        planet_upgrade(planet_id)
   
    # fetch the turn report
    turn_xml = get_xml(turn_url, json_key='pagedata')
    turn = turn_xml.xpath('/div/pre/text()')[0]
    
    
    # exit mf
    if connection is not None:
        connection.close()

if __name__ == '__main__':
    main()


