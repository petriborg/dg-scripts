#!/usr/bin/python
#
# this was built on Ubuntu 10.04 assumptions may have been made
#

from __future__ import with_statement
from contextlib import contextmanager
from lxml import etree
import subprocess as sub
import sqlite3 as db_api
import traceback as tb
import os, sys, re, json, getopt


# galaxy list
# http://davesgalaxy.com/planets/list/all/1/
#
# planet info
# http://davesgalaxy.com/planets/441551/info/
# http://davesgalaxy.com/planets/262155/manage/
# http://davesgalaxy.com/planets/262155/budget/
# http://davesgalaxy.com/planets/262155/upgradelist/
#
# data looks like
# <tr class="\"fleetrow\"" ...>
# 10x <td>...</td>
# the 5th td is the planet name

xml_parser = etree.XMLParser(recover=True)
sessionid = None
database = None
connection = None
todays_day_id = None
timeout = '-22 hours'

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

# wget the page and push to stdout
def wget(*args):
    return ['wget', '--load-cookies=cookies.txt', '-q', '-O-'] + list(args)

def curl(*args):
    return ['curl', '--silent', '-b', get_cookie()] + list(args)

def cat(*args):
    return ['cat', '../data/test_planets_list_all_1']

def find_todays_id():
    global todays_day_id
    if todays_day_id is None:
        with transaction() as c:
            query = c.execute("""
                select day_id from days
                where creation_time > datetime('now', ?)
                order by creation_time desc limit 1""", (timeout,));
            data = query.fetchall()
            if len(data) > 0:
                day_id = data[0][0]
                print "Fetched from DB day: %d", day_id
                todays_day_id = day_id
            else:
                query = c.execute("insert into days (day_id) select null")
                todays_day_id = query.lastrowid()
    return todays_day_id

def curl_raw_page(url):
    print "Fetching from web", url
    proc = sub.Popen(curl(url), stdout=sub.PIPE)
    raw_page = proc.stdout.read()

    with transaction() as c:
        c.execute("""insert into raw_pages 
            (day_id, url, page) values (?, ?, ?)""", 
            (todays_day_id, url, raw_page,))

    return raw_page

def get_raw_page(url):
    with transaction() as c:
        query = c.execute("""
            select page from raw_pages
            where day_id = ?
              and url = ?
            limit 1""", (todays_day_id, url) );
        data = query.fetchall()
        if len(data) > 0:
            print "Fetching from DB", url
            raw_page = data[0][0]
            #print raw_page
            return raw_page
    raw_page = curl_raw_page(url)
    return raw_page

def dump_page(page, url=None, e=None):
    # writes page to disk
    fn = url[23:].replace('/','_')
    print "Dump", fn
    fd = open(fn, 'w')
    if url is not None:
        fd.write(url)
        fd.write("\n\n")
    if e is not None:
        fd.write(e)
        fd.write("\n\n")
    fd.write(page)
    fd.close()

def get_xml(url, save_xml=False):
    raw_page = get_raw_page(url)
    json_decoder = json.JSONDecoder()
    json_obj = json_decoder.decode(raw_page)
    xml_page = json_obj.get('tab')
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
    paginator = root_elem.xpath('//div[@class="paginator"]')[0]
    count = len(paginator.getchildren())
    return count

def clean(key_str):
    key_str = key_str.strip().replace(' ', '_')
    m = re.search('[^:\s]+', key_str)
    if m:
        key_str = m.group()
    return key_str.lower()

def insert_planets(planets_elem):

    def get_planet_number(tr_elem):
        js_text = tr_elem.get('onmouseover')
        planet_number = js_text.split("'")[1]
        return planet_number

    def get_planet_name(tr_elem):
        planet_name = tr_elem.xpath('td[5]')[0].text
        return planet_name

    for planet in planets_elem:
        planet_number = get_planet_number(planet)
        planet_name = get_planet_name(planet)
        print "%s: %s" % (planet_name, planet_number)

        with transaction() as c:
            c.execute("""
                insert or ignore into planets
                (planet_id, name) values (?, ?)""",
                (planet_number, planet_name))

def insert_planet_info(planet_id, planet_info_elems):
    result = dict(planet_id=planet_id, day_id=todays_day_id)

    # the first table
    tr_elems = planet_info_elems[0].xpath('tr')
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
    tr_elems = planet_info_elems[1].xpath('tr[td]')
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

    with transaction() as c:
        sorted_keys = result.keys()
        sorted_keys.sort()
        keys_count = len(sorted_keys)
        #print "sorted_keys:", keys_count
        sorted_values = map(lambda k: str(result.get(k)), sorted_keys)
        keys_str = ', '.join(sorted_keys)
        qs_str = ', '.join( (keys_count*('?',)) )
        query_str = """
            insert into planet_info
            (%s) values (%s)""" % (keys_str, qs_str)
        #print query_str
        c.execute(query_str, sorted_values)

def planet_info(planet_id):
    with transaction() as c:
        query = c.execute("""select info_id from planet_info
            where planet_id=? and day_id=?""", (planet_id, todays_day_id))
        data = query.fetchall()
        if len(data) > 0:
            print "Already fetched planet_id %d for today!" % (
                planet_id,)
            return
    
    info_xml_obj = get_xml(planet_info_url % planet_id)
    info_table_elems = info_xml_obj.xpath('//table')
    insert_planet_info(planet_id, info_table_elems)

def planet_manage(planet_id):
    manage_xml_obj = get_xml(planet_manage_url % planet_id, True)

def planet_budget(planet_id):
    budget_xml_obj = get_xml(planet_budget_url % planet_id, True)

    tb_elems = budget_xml_obj.xpath('//table//table')
    fleet_tr = tb_elems[0].xpath('tr[td/text()=="Fleet Upkeep"]')
    fleet_upkeep = fleet_tr[0].getchildren()[1].text
    print "fleet upkeep", fleet_upkeep

def planet_upgrade(planet_id):
    upgrade_xml_obj = get_xml(planet_upgrade_url % planet_id, True)



def main():
    global sessionid, database
    try:
        (opts,args) = getopt.getopt(sys.argv[1:], 's:d:', 
            ['sessionid=', 'database='])
        print 'opts:',opts
        print 'args:',args
        for (opt,val) in opts:
            print "opt:",opt,"val:",val
            if opt in ('-s', '--sessionid'):
                sessionid = val
            elif opt in ('-d', '--database'):
                database = val
            else:
                print "Unknown option:",opt
                sys.exit(2)
    except getopt.GetoptError, e:
        print e
        sys.exit(2)
    
    print "database:",database
    print "sessionid:",sessionid
    
    find_todays_id()
    
    print "today's id:", todays_day_id
    
    list_all_url = 'http://davesgalaxy.com/planets/list/all/%s/'
    xml_obj = get_xml(list_all_url % 1)
    insert_planets(xml_obj.xpath('/div//tr[@class="fleetrow"]'))
    
    page_count = get_page_count(xml_obj)
    
    print "found %d pages" % page_count
    
    if page_count > 1:
        for i in range(1, page_count+1):
            index = i+1
            url = list_all_url % i
            xml_obj = get_xml(url)
            insert_planets(xml_obj.xpath('/div//tr[@class="fleetrow"]'))
    
    with transaction() as c:
        query = c.execute("""select planet_id from planets""")
        planet_ids = query.fetchall()
    
    print "planet ids:",len(planet_ids)
    
    planet_ids = (planet_ids[0],)
    
    for planet_id_tuple in planet_ids:
        planet_id = planet_id_tuple[0]
        
        planet_info(planet_id)
        planet_manage(planet_id)
        planet_budget(planet_id)
        planet_upgrade(planet_id)
    
    
    # exit mf
    if connection is not None:
        connection.close()

if __name__ == '__main__':
    main()


