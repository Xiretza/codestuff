#!/usr/bin/env python

import xml.etree.ElementTree as ET
import sys
import re
import json
import argparse
from datetime import datetime, date

parser = argparse.ArgumentParser(description='Mensa-Wochenplan parsen')

parser.add_argument('file', type=argparse.FileType('r'))
args = parser.parse_args()

tree = ET.parse(args.file)

num_menus = 3

allergens = 'ABCDEFGHLMNOPR'

days = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']

class Data:
    pass

class Meal:
    def __init__(self, name, alls=None):
        self.name = name
        if not alls:
            alls = ''
        for c in alls:
            if c not in allergens:
                raise ValueError('Unknown allergen: %r' % c)
        self.allergens = alls

    def __str__(self):
        return '%s (%s)' % (self.name, self.allergens)

    def __repr__(self):
        return '%s(%r, %r)' % (self.__name__, self.name, self.allergens)

class Menu:
    def __init__(self, name, price):
        self.name = name
        if not isinstance(price, int):
            raise ValueError('Price must be int: %r' % price)
        self.price = price
        self.days = {}

    def __str__(self):
        pretty = 'Menu %s, %.2f€:' % (self.name, self.price / 100)
        for day in days:
            pretty += '\n%s:' % day
            for meal in self.get_day(day):
                pretty += '\n- %s' % meal

        return pretty

    def add_day(self, day, meals:"list of meals"):
        if day not in days:
            raise ValueError('Unknown day: %r' % day)
        if day in self.days:
            raise ValueError('Day already set: %r' % day)
        for meal in meals:
            if not isinstance(meal, Meal):
                raise ValueError('Not a meal: %r' % meal)

        self.days[day] = meals

    def get_day(self, day):
        return self.days[day]

class ParseError(Exception):
    pass

def parse_fail(txt):
    raise ParseError('%d:%d: parsing failed: %s' % (rownum, colnum, txt))

def extract_timespan(tree):
    """Extract start and end date from ElementTree"""

    header = tree.find('body/p')

    header = ''.join(header.itertext()).translate(str.maketrans('\n', ' ', '\t'))

    m = re.search('vom (\d{,2}.\d{,2}.) bis (\d{,2}.\d{,2}.) (\d{4})', header)

    if m:
        start = m.group(1)
        end = m.group(2)
        year = m.group(3)

        start_date = datetime.strptime('%s%s' % (start, year), '%d.%m.%Y').date()
        end_date = datetime.strptime('%s%s' % (end, year), '%d.%m.%Y').date()

        return (start_date, end_date)
    else:
        parse_fail('document header: %r' % header)

def parse_menu_header(text):
    """Return new, empty Menu() from description"""

    m = re.search('^Menü (\d+) um € (\d+,\d{2})$', text)

    if m:
        menu_number = m.group(1)
        if int(menu_number) != rownum / 3 + 1:
            parse_fail('menu/row desync, menu = %d, rownum = %d' % (menu_number, rownum))

        # price in cents
        price = int(100 * float(m.group(2).replace(',', '.')))
        if price % 10 != 0:
            parse_fail('weird price: %d' % price)

        return Menu(menu_number, price)
    else:
        parse_fail('menu header: %r' % text)

def parse_day_menu(text):
    """Return list of Meal() for one day"""

    items = [item.strip() for item in text.split('****')]
    if len(items) != 2:
        parse_fail('not two courses: %r' % items)

    meals = []
    for num, item in enumerate(items):
        # group 1: name of meal, group 2: allergens
        item_regex = re.compile('^(.*?) +\(([%s]+)\)$' % allergens)
        m = re.search(item_regex, item)
        if m:
            meals.append(Meal(
                re.sub(' +', ' ', m.group(1)),
                m.group(2)
            ))
        else:
            parse_fail('menu item: %r' % item)

    return meals

data = Data()

(data.start, data.end) = extract_timespan(tree)

tab = tree.find('.//table')

data.menus = []

for rownum, row in enumerate(tab.iter('tr')):
    rowtype = rownum % 3

    for colnum, col in enumerate(row.iter('td')):
        # get all text inside field
        text = ''.join(col.itertext())
        text = text.translate(str.maketrans('\n', ' ', '\t')).strip()

        # menu header
        if rowtype == 0:
            current_menu = parse_menu_header(text)
            data.menus.append(current_menu)
        # day
        elif rowtype == 1:
            if not text == days[colnum]:
                parse_fail('wrong day: is %r, should be %r' % (text, days[colnum]))
        # courses for one day
        elif rowtype == 2:
            meals = parse_day_menu(text)

            current_menu.add_day(days[colnum], meals)

for day in days:
    soups = [
        menu.get_day(day)[0].name
        for menu in data.menus
    ]

    if not len(set(soups)) == 1:
        parse_fail('soups not equal on %s: %r' % (day, soups))

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Menu):
            return {'__kind': 'Menu', 'name': obj.name, 'price': obj.price, 'days': obj.days}
        elif isinstance(obj, Meal):
            return {'__kind': 'Meal', 'name': obj.name, 'allergens': obj.allergens}

        return super().default(obj)

print('Plan vom %s bis %s\n' % (data.start, data.end))

for day in days:
    soup = data.menus[0].get_day(day)[0]

    outstr = '%s\nSuppe: %s\n' % (day, soup)

    for menu in data.menus:
        meal = menu.get_day(day)[1]
        outstr += 'Menü %s (%.2f€): %s\n' % (menu.name, menu.price / 100, meal)

    print(outstr)

#print(json.dumps(menus, cls=CustomEncoder, indent=2))
