from datetime import timedelta, datetime, date
import re
import xml.etree.ElementTree as ET

NUM_MENUS = 3

ALLERGENS = {
    'A': 'Gluten',
    'B': 'Krebstiere',
    'C': 'Eier',
    'D': 'Fisch',
    'E': 'Erdnüsse',
    'F': 'Soja',
    'G': 'Milch',
    'H': 'Schalenfrüchte',
    'L': 'Sellerie',
    'M': 'Senf',
    'N': 'Sesam',
    'O': 'Schwefeldioxid',
    'P': 'Lupinien',
    'R': 'Weichtiere'
}

DAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']


class Plan:
    def __init__(self):
        self.menus = []
        self.start_date = None
        self.end_date = None

    def set_timespan(self, dates):
        self.start_date = dates[0]
        self.end_date = dates[1]


class Menu:
    def __init__(self, name, price):
        self.name = name
        if not isinstance(price, int):
            raise ValueError('Price must be int: %r' % price)
        self.price = price
        self.days = {}

    def __str__(self):
        pretty = 'Menu %s, %.2f€:' % (self.name, self.price / 100)
        for day in DAYS:
            pretty += '\n%s:' % day
            for meal in self.get_day(day):
                pretty += '\n- %s' % meal

        return pretty

    def add_day(self, day, meals: "list of meals"):
        if day not in DAYS:
            raise ValueError('Unknown day: %r' % day)
        if day in self.days:
            raise ValueError('Day already set: %r' % day)
        for meal in meals:
            if not isinstance(meal, Meal):
                raise ValueError('Not a meal: %r' % meal)

        self.days[day] = meals

    def get_day(self, day):
        return self.days[day]


class Meal:
    def __init__(self, name, alls=None):
        self.name = name
        if not alls:
            alls = ''
        for c in alls:
            if c not in ALLERGENS:
                raise ValueError('Unknown allergen: %r' % c)
        self.allergens = alls

    def __str__(self):
        return '%s (%s)' % (self.name, self.allergens)

    def __repr__(self):
        return 'Meal(%r, %r)' % (self.name, self.allergens)


class ParseError(Exception):
    def __init__(self, text, context=None):
        if context is None:
            fmt = 'parsing failed: %(text)s'
        else:
            fmt = 'parsing failed: %(text)s (near %(context)r)'

        message = fmt % dict(text=text, context=context)
        Exception.__init__(self, message)
        self.message = message


def extract_timespan(tree):
    """Extract start and end date from ElementTree"""

    header = tree.find('body/p')

    header = ''.join(header.itertext()).translate(str.maketrans('\n', ' ', '\t'))

    m = re.search(r'vom (\d{,2}.\d{,2}.) bis (\d{,2}.\d{,2}.) (\d{4})', header)

    if m:
        start = m.group(1)
        end = m.group(2)
        year = m.group(3)

        start_date = datetime.strptime('%s%s' % (start, year),
                                       '%d.%m.%Y').date()
        end_date = datetime.strptime('%s%s' % (end, year),
                                     '%d.%m.%Y').date()

        return (start_date, end_date)
    else:
        raise ParseError('document header', header)


def parse_menu_header(text):
    """Return new, empty Menu() from description"""

    m = re.search(r'^Menü (\d+) um € (\d+,\d{2})$', text)

    if m:
        # price in cents
        price = int(100 * float(m.group(2).replace(',', '.')))
        if price % 10 != 0:
            raise ParseError('weird price: %d' % price, text)

        return Menu(m.group(1), price)
    else:
        raise ParseError('menu header', text)


def parse_day_menu(text):
    """Return list of Meal() for one day"""

    items = [item.strip() for item in text.split('****')]
    if len(items) != 2:
        raise ParseError('not two courses', items)

    meals = []
    for item in items:
        # group 1: name of meal, group 2: allergens
        item_regex = re.compile(r'^(.*?) +\(([%s]+)\)$' % ALLERGENS)
        m = re.search(item_regex, item)
        if m:
            meals.append(Meal(
                re.sub(' +', ' ', m.group(1)),
                m.group(2)
            ))
        else:
            raise ParseError('menu item', item)

    return meals


def validate(plan):
    """Run some sanity checking on a Plan"""

    if plan.end_date - plan.start_date != timedelta(days=4):
        raise ParseError('timespan is not a work-week: from %s to %s'
                         % (plan.start_date, plan.end_date))

    if plan.start_date.weekday() != 0:
        raise ParseError("plan doesn't start on Monday: %s" % plan.start_date)

    for day in DAYS:
        soups = [
            menu.get_day(day)[0].name
            for menu in plan.menus
        ]

        if not len(set(soups)) == 1:
            raise ParseError('soups not equal on %s' % day, soups)



#print(json.dumps(menus, cls=CustomEncoder, indent=2))
