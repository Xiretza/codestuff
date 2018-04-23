#!/usr/bin/env python3

import requests
import json
import argparse
import collections
from tabulate import tabulate
from enum import Enum, unique
from datetime import date, datetime, timedelta

@unique
class ElementType(Enum):
    grade = 1
    teacher = 2
    subject = 3
    room = 4

@unique
class PeriodState(Enum):
    standard = 'STANDARD'
    cancelled = 'CANCEL'
    exam = 'EXAM'
    shift = 'SHIFT'
    additional = 'ADDITIONAL'

class ElementRegistry():
    """
    Stores Elements by their `type` and `id`
    """

    def __init__(self):
        self.elements = {t: {} for t in ElementType}

    def addElement(self, el):
        """Adds a dict representing an element to the registry"""

        t = ElementType(el['type'])

        self.elements[t][el['id']] = el

    def getElement(self, type_, id_):
        if not isinstance(type_, ElementType):
            raise TypeError('Expected ElementType, got %r' % type_)

        return self.elements[type_][id_]

    def getAllOfType(self, type_):
        if not isinstance(type_, ElementType):
            raise TypeError('Expected ElementType, got %r' % type_)

        return self.elements[type_]


class Period():
    def __init__(self, data, extraEls):
        """
        Instantiate a Period from JSON data.

        extraEls: ElementRegistry
        """

        day = datetime.strptime(str(data['date']), '%Y%m%d').date()
        self.start = datetime.combine(day,
                datetime.strptime(str(data['startTime']), '%H%M').time()
            )
        self.end = datetime.combine(day,
                datetime.strptime(str(data['endTime']), '%H%M').time()
            )

        if self.end - self.start not in [timedelta(minutes=m) for m in [45, 50]]:
            raise ValueError('Expected period to be 45 or 50 minutes, is %s (from %s to %s)' % (
                self.end-self.start, self.start.strftime('%H:%M'), self.end.strftime('%H:%M')))

        self.state = PeriodState(data['cellState'])

        self.elements = ElementRegistry()
        for el in data['elements']:
            self.elements.addElement(extraEls.getElement(
                ElementType(el['type']),
                el['id']
            ))

    def getElements(self, t):
        """
        Return list of all Elements of given ElementType
        """

        return self.elements.getAllOfType(t).values()

    def slot(self):
        return Timegrid.Slot(start=self.start.time(), end=self.end.time())

    def __str__(self):
        return '%s %s-%s: %s with %s in %s' % (
                self.start.strftime('%d.%m.'), self.start.strftime('%H:%M'), self.end.strftime('%H:%M'),
                ', '.join([e['name'] for e in self.getElements(ElementType.subject)]),
                ', '.join([e['name'] for e in self.getElements(ElementType.teacher)]),
                ', '.join([e['name'] for e in self.getElements(ElementType.room)]),
            )

    def pretty(self, shown_elements, terse=True):
        els = []
        for typ in shown_elements:
            e = list(self.getElements(typ))
            if e:
                els += [e[0]['name' if terse else 'longName']]

        if self.state == PeriodState.cancelled:
            return strike(' - '.join(els))
        else:
            return ' - '.join(els)

class Timegrid():
    Slot = collections.namedtuple('Slot', ['start', 'end'])
    Day  = collections.namedtuple('Day', ['label', 'first_slot', 'last_slot'])

    def __init__(self, data):
        """Initialize the timegrid from JSON data"""

        self.slots = {}
        self.days = []

        for slot_data in data['units']:
            slot_num = slot_data['number']
            slot = self.Slot(
                    start=datetime.strptime(str(slot_data['startTime']), '%H%M').time(),
                    end=  datetime.strptime(str(slot_data['endTime']),   '%H%M').time(),
                )

            if slot.end <= slot.start:
                raise ValueError('Slot times are wrong: starts at %(start)s, ends at %(end)s' % slot)

            if slot_num-1 in self.slots:
                prevslot = self.slots[slot_num-1]
                if prevslot.end > slot.start:
                    raise ValueError('Slot overlaps with previous (prev ends at %s, curr starts at %s)' % (prevslot.end, slot.start))

            self.slots[slot_num] = slot

        for day in data['days']:
            day = self.Day(
                    label=day['label'],
                    first_slot=day['firstLesson'],
                    last_slot=day['lastLesson'],
                )

            if day.first_slot == day.last_slot == 0:
                continue

            self.days.append(day)

    def slots_on(self, day_spec):
        """Return a list of time slots on a given day"""
        if isinstance(day_spec, self.Day):
            day = day_spec
        elif isinstance(day_spec, str):
            day = filter(lambda d: d.label == day_spec, self.days)
            if not day:
                raise ValueError('Day not found: %s' % day_spec)

            day = day[0]
        else:
            day = self_days[day_spec]

        return [self.slots[s] for s in range(day.first_slot, day.last_slot)]


class Timetable():
    def __init__(self, timegrid):
        self.days = collections.defaultdict(dict)
        self.timegrid = timegrid

    def periods(self):
        """Returns a timedate-sorted list of all periods in the timetable"""
        out = []
        for day in self.days.values():
            out += day

        return sorted(out, key=lambda p: p.start)

    def add_period(self, period):
        slot = period.slot()

        # check for alignment with Timegrid
        if slot not in self.timegrid.slots.values():
            raise ValueError('Period not in valid slot: %s' % (period.slot(),))

        day = self.days[period.start.date()]

        if slot not in day:
            day[slot] = []

        day[slot].append(period)

    def days_sorted(self):
        """Return a sorted list of (date, lessons) tuples"""
        return [(d, self.days[d]) for d in sorted(self.days)]

def strike(text):
    #return '\u0336'.join(text) + '\u0336'
    #return '\033[9m' + text + '\033[0m'
    return text

def fetch_timegrid(servername, schoolname):
    url = 'https://%s.webuntis.com/WebUntis/jsonrpc_web/jsonTimegridService' % servername

    r = requests.post(url, params={'school': schoolname}, data=json.dumps({
            'id': 0,
            'method': 'getTimegrid',
            'params': [3],
            'jsonrpc': '2.0',
        }))
    return r.json()['result']

def fetch_config(servername, schoolname, element_type, date):
    url = 'https://%s.webuntis.com/WebUntis/api/public/timetable/weekly/pageconfig' % servername

    r = requests.get(url, params={
            'school': schoolname,
            'type': element_type.value,
            'date': date.strftime('%Y-%m-%d'),
        })
    return r.json()['data']

def fetch_data(servername, schoolname, data_type, data_id, date):
    url = 'https://%s.webuntis.com/WebUntis/api/public/timetable/weekly/data' % servername

    r = requests.get(url, params={
            'school': schoolname,
            'elementType': data_type.value,
            'elementId': data_id,
            'date': date.strftime('%Y-%m-%d'),
        })
    return r.json()['data']['result']

def parse_args():
    parser = argparse.ArgumentParser(description='Extract timetable information from WebUntis')

    parser.add_argument('servername', help='name of the WebUntis server ([name].webuntis.com)')
    parser.add_argument('schoolname', help='name of the school')
    parser.add_argument('-q', '--query', dest='query_type', choices=ElementType.__members__,
            help='query for a given type')
    parser.add_argument('name', help='name of the item to query')
    parser.add_argument('-d', '--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(), default=datetime.now().date(),
            help='show timetable for specific date (YYYY-MM-DD) instead of today')

    return parser.parse_args()

def output_table(tt, shown_elements):
    indices = []
    rows = []

    for slot in sorted(tt.timegrid.slots.values()):
        indices.append('%s\n%s' % (
                slot.start.strftime('%H:%M'),
                slot.end.strftime('%H:%M'),
            ))
        row = {}
        for date, periods in tt.days_sorted():
            if slot in periods:
                row[date.strftime('%A')] = '\n'.join(
                        #list(p.getElements(ElementType.subject))[0]['name']
                        p.pretty(shown_elements)
                        for p in periods[slot]
                    )

        rows.append(row)

    print(tabulate(rows, headers='keys', showindex=indices, tablefmt='fancy_grid'))

def output_list(tt, shown_elements):
    for date, periods in tt.days.items():
        print(date)
        print({s: ', '.join([p.pretty(shown_elements) for p in ps_in_s]) for s, ps_in_s in periods.items()})

def main():
    args = parse_args()

    args.query_type = ElementType[args.query_type]

    mappings = fetch_config(args.servername, args.schoolname, args.query_type, args.date)['elements']
    target_id = list(filter(lambda e: e['name'] == args.name, mappings))

    if not target_id:
        raise ValueError('Specified target not found')

    target_id = target_id[0]['id']

    data = fetch_data(args.servername, args.schoolname, args.query_type, target_id, args.date)

    elements = ElementRegistry()
    for el in data['data']['elements']:
        elements.addElement(el)

    tg = Timegrid(fetch_timegrid(args.servername, args.schoolname))
    #print(tg.slots)

    tt = Timetable(tg)

    for period in data['data']['elementPeriods'][str(target_id)]:
        tt.add_period(Period(period, elements))

    output_table(tt, [ElementType.subject, ElementType.teacher, ElementType.room])
    #output_list(tt, [ElementType.subject, ElementType.teacher, ElementType.room])

if __name__ == '__main__':
    main()
