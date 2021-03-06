#!/usr/bin/env python3

import requests
import json
import argparse
import collections
import functools
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
    substitution = 'SUBSTITUTION'
    room_substitution = 'ROOMSUBSTITUTION'
    office_hour = 'OFFICEHOUR'

class NotAuthenticatedError(Exception):
    def __init__(self, message):
        self.message = message

class NotAlignedError(Exception):
    def __init__(self, period):
        super().__init__('period is not aligned: %s from %s to %s' % (
                period.start.date(),
                period.start.time(),
                period.end.time()
            ))

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


@functools.total_ordering
class Period():
    def __init__(self, data, extraEls):
        """
        Instantiate a Period from JSON data.

        extraEls: ElementRegistry
        """

        day = datetime.strptime(str(data['date']), '%Y%m%d').date()
        self.start = datetime.combine(
                day,
                datetime.strptime(str(data['startTime']).zfill(4), '%H%M').time()
            )
        self.end = datetime.combine(
                day,
                datetime.strptime(str(data['endTime']).zfill(0), '%H%M').time()
            )

        if self.end - self.start <= timedelta(0):
            raise ValueError('bad period time: is %s (from %s to %s)' % (
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

    def __lt__(self, other):
        return self.start < other.start

    def __eq__(self, other):
        return self.start == other.start

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
    def __init__(self):
        self.days = collections.defaultdict(list)

    def periods(self):
        """Returns a timedate-sorted list of all periods in the timetable"""
        out = []
        for day in self.days.values():
            out += day

        return sorted(out, key=lambda p: p.start)

    def add_period(self, period):
        day = self.days[period.start.date()]

        day.append(period)

    def days_sorted(self):
        """Return a sorted list of (date, lessons) tuples"""
        return [(d, self.days[d]) for d in sorted(self.days)]

    def grid_aligned(self, timegrid):
        """Return dict of {date:{slot:[periods]}}, with each slot contained in the timegrid, raises NotAlignedError if impossible"""
        out = collections.defaultdict(dict)
        for date, periods in self.days.items():
            day = out[date]
            for p in periods:
                slot = p.slot()

                # check for alignment with Timegrid
                if slot not in timegrid.slots.values():
                    raise NotAlignedError(p)

                if slot not in day:
                    day[slot] = []

                day[slot].append(p)

        return out

class ConnectionInfo():
    def __init__(self, servername, schoolname):
        self.servername = servername
        self.schoolname = schoolname
        self.s = requests.Session()
        self.base_url = 'https://%s.webuntis.com/WebUntis/' % self.servername

    def get(self, url, base_url=None, **kwargs):
        """Gets data from url relative to base_url and returns its JSON decoded form"""

        if not base_url:
            base_url = self.base_url

        r = self.s.get(base_url + url, **kwargs)

        j = r.json()
        if 'isSessionTimeout' in j:
            raise NotAuthenticatedError('missing required authentication')

        return j

    def post(self, url, base_url=None, **kwargs):
        """Gets data from url relative to base_url and returns its JSON decoded form"""

        if not base_url:
            base_url = self.base_url

        r = self.s.post(base_url + url, **kwargs)

        j = r.json()
        if 'isSessionTimeout' in j:
            raise NotAuthenticatedError('missing required authentication')

        return j

def strike(text):
    #return '\u0336'.join(text) + '\u0336'
    #return '\033[9m' + text + '\033[0m'
    return text

def fetch_timegrid(conn_info):
    url = 'jsonrpc_web/jsonTimegridService'

    r = conn_info.post(url, params={'school': conn_info.schoolname}, data=json.dumps({
            'id': 0,
            'method': 'getTimegrid',
            'params': [3],
            'jsonrpc': '2.0',
        }))

    return r['result']

def fetch_config(conn_info, element_type, date):
    url = 'api/public/timetable/weekly/pageconfig'

    r = conn_info.get(url, params={
            'school': conn_info.schoolname,
            'type': element_type.value,
            'date': date.strftime('%Y-%m-%d'),
        })

    return r['data']

def fetch_data(conn_info, data_type, data_id, date):
    url = 'api/public/timetable/weekly/data'

    r = conn_info.get(url, params={
            'school': conn_info.schoolname,
            'elementType': data_type.value,
            'elementId': data_id,
            'date': date.strftime('%Y-%m-%d'),
        })

    return r['data']['result']

def authenticate(conn_info, user, password):
    url = 'j_spring_security_check'

    r = conn_info.post(url, headers={'Accept': 'application/json'}, data={
            'school': conn_info.schoolname,
            'j_username': user,
            'j_password': password,
        })

    if r.get('state') == 'SUCCESS':
        return True
    else:
        raise NotAuthenticatedError('authentication failed: %s' % r)


def parse_args():
    parser = argparse.ArgumentParser(description='Extract timetable information from WebUntis')

    parser.add_argument('servername', help='name of the WebUntis server ([name].webuntis.com)')
    parser.add_argument('schoolname', help='name of the school')
    parser.add_argument('type', choices=ElementType.__members__,
            help='the type of element to look for')
    parser.add_argument('-d', '--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(), default=datetime.now().date(),
            help='show timetable for specific date (YYYY-MM-DD) instead of today')
    parser.add_argument('-u', '--user',
            help='the username to use for authentication')
    parser.add_argument('-p', '--password',
            help='the password to use for authentication')

    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('-l', '--list', action='store_true',
            help='list targets for the given type')
    actions.add_argument('-q', '--query', dest='query_target',
            help='query for a given target')

    return parser.parse_args()

def output_tt_table(tt, timegrid, shown_elements):
    indices = []
    rows = []

    days = tt.grid_aligned(timegrid)

    for slot in sorted(timegrid.slots.values()):
        indices.append('%s\n%s' % (
                slot.start.strftime('%H:%M'),
                slot.end.strftime('%H:%M'),
            ))
        row = {}
        for date, periods in sorted(days.items()):
            if slot in periods:
                row[date.strftime('%A')] = '\n'.join(
                        p.pretty(shown_elements)
                        for p in periods[slot]
                    )

        rows.append(row)

    print(tabulate(rows, headers='keys', showindex=indices, tablefmt='fancy_grid'))

def output_tt_list(tt, shown_elements):
    for date, periods in sorted(tt.days.items()):
        print(date)
        print({p.slot(): p.pretty(shown_elements) for p in sorted(periods)})

def output_target_list(config):
    print('\n'.join(sorted(e['name'] for e in config)))

def main():
    args = parse_args()

    args.type = ElementType[args.type]

    ci = ConnectionInfo(args.servername, args.schoolname)

    if args.user:
        authenticate(ci, args.user, args.password)

    # fetch id listings for the requested type
    mappings = fetch_config(ci, args.type, args.date)['elements']

    if args.query_target:
        # find the target's id from the mapping
        target_id = list(filter(lambda e: e['name'] == args.query_target, mappings))

        if not target_id:
            raise ValueError('Specified target not found')

        target_id = target_id[0]['id']

        # get all timetable data for the type/id pair
        data = fetch_data(ci, args.type, target_id, args.date)

        # populate element registry
        elements = ElementRegistry()

        for el in data['data']['elements']:
            elements.addElement(el)

        # populate timetable
        tt = Timetable()

        for period in data['data']['elementPeriods'][str(target_id)]:
            tt.add_period(Period(period, elements))

        shown_elements = [ElementType.subject, ElementType.teacher, ElementType.room if args.type == ElementType.grade else ElementType.grade]

        tg = Timegrid(fetch_timegrid(ci))
        try:
            output_tt_table(tt, tg, shown_elements)
        except NotAlignedError as e:
            print('Lessons are not aligned to grid, printing as list instead (%s)' % e)
            print('Slots:')
            print(tg.slots)
            output_tt_list(tt, shown_elements)
    elif args.list:
        # just list the possible targets
        output_target_list(mappings)
    else:
        print('Action not supported!')

if __name__ == '__main__':
    main()
