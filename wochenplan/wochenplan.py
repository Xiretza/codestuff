import xml.etree.ElementTree as ET
import sys
import re
import json
from datetime import datetime, date

filename = 'wochenplan.html'

num_menus = 3

allergens = 'ABCDEFGHLMNOPR'

days = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']

# data
#   start_date:
#   end_date:
#   menus
#     1
#       price:
#       days
#         Montag
#           items
#             0
#               name: 
#               allergens:
#             1
#               name:
#               allergens:

data = {
        'menus': {}
}

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

class Menu:
    def __init__(self, name):
        self.name = name
        self.days = {}

    def add_day(day, meals:"list of meals"):
        if not day in days:
            raise ValueError('Unknown day: %r' % day)
        for meal in meals:
            if not isinstance(meal, Meal):
                raise ValueError('Not a meal: %r' % meal)

        self.days['day'] = meals


def parse_fail(txt):
    print('%d:%d: parsing failed: %s' % (rownum, colnum, txt))
    sys.exit(2)

root = ET.parse(filename)
header = root.find('body/p')

header = ''.join(header.itertext()).translate(str.maketrans('\n', ' ', '\t'))

m = re.search('vom (\d{,2}.\d{,2}.) bis (\d{,2}.\d{,2}.) (\d{4})', header)

if m:
    start = m.group(1)
    end = m.group(2)
    year = m.group(3)

    data['start_date'] = datetime.strptime('%s%s' % (start, year), '%d.%m.%Y').date()
    data['end_date'] = datetime.strptime('%s%s' % (end, year), '%d.%m.%Y').date()
else:
    parse_fail('document header: %r' % header)

tab = root.find('.//table')

for rownum, row in enumerate(tab.iter('tr')):
    for colnum, col in enumerate(row.iter('td')):
        # get all text inside field
        text = ''.join(col.itertext())
        text = text.translate(str.maketrans('\n', ' ', '\t'))
        
        rowtype = rownum % 3

        # menu header
        if rowtype == 0:
            m = re.search('^Menü (\d+) um € (\d+,\d{2})$', text.strip())
            if m:
                menu_number = m.group(1)
                if int(menu_number) != rownum / 3 + 1:
                    parse_fail('menu/row desync, menu = %d, rownum = %d' % (menu_number, rownum))

                # price in cents
                price = int(100 * float(m.group(2).replace(',', '.')))
                if price % 10 != 0:
                    parse_fail('weird price: %d' % price)

                data['menus'][menu_number] = {
                        'price': price,
                        'days': {}
                    }
                        
            else:
                parse_fail('menu header: %r' % text)
        # days
        elif rowtype == 1:
            if text.strip() == days[colnum]:
                data['menus'][menu_number]['days'][days[colnum]] = {
                        'items': []
                    }
            else:
                parse_fail('wrong day: is %r, should be %r' % (text, days[colnum]))
        # food items
        elif rowtype == 2:
            items = [item.strip() for item in text.split('****')]
            if len(items) != 2:
                parse_fail('not two menus: %r' % items)

            for num, item in enumerate(items):
                item_regex = re.compile('^(.*?) +\(([%s]+)\)$' % allergens)
                m = re.search(item_regex, item)
                if m:
                    data['menus'][menu_number]['days'][days[colnum]]['items'].append({
                            'name': re.sub(' +', ' ', m.group(1)),
                            'allergens': m.group(2)
                        })
                else:
                    parse_fail('menu item: %r' % item)

for day in days:
    soups = [
        menu['days'][day]['items'][0]['name']
        for menu in data['menus'].values()
        ]

    if not len(set(soups)) == 1:
        parse_fail('soups not equal on %s: %s' % (day, soups))

class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()

        return json.JSONEncoder.default(self, obj)

#for day in days:
#    soup = data['menus']['1']['days'][days[0]]['items'][0]
#
#    meals = [[num, data['menus'][menu]['days'][day]['items'][1]] for (num, menu) in data['menus'].items()]
#
#    outstr = '%s\nSuppe: %s (%s)\n' % (day, soup['name'], soup['allergens'])
#
#    for (menu, meal) in meals:
#        outstr += 'Menü %d: %s (%s)\n' % (menu, meal['name'], meal['allergens'])
#
#    print(outstr)

print(json.dumps(data, cls=DateEncoder, indent=2))



#def strip_element(el):
#    log('el %s, ' % el)
#    if el.tag in stripped_tags:
#        log('stripping, ')
#        if len(el) == 0:
#            text = ''.join(el.itertext())
#            text = text.translate(str.maketrans('\t', ' ', '\r')) if len(text) > 0 else None
#            log('results in %s\n' % repr(text))
#        else:
#            log('has children\n')
#            return (strip_element(child) for child in list(el))
#    else:
#        log('not stripping, ')
#        children = (strip_element(child) for child in list(el))
#    
#        el.clear()
#
#        for child in children:
#            if isinstance(child, str):
#                log('text += %s, ' % repr(child))
#                el.text = (el.text if el.text else '') + child
#            elif isinstance(child, ET.Element):
#                log('appending %s, ' % child)
#                el.append(child)
#        
#        log('\n')
#        return el
