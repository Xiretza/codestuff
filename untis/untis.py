import requests
import base64
import json
import argparse
from tabulate import tabulate
from collections import defaultdict
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
        self.student_group = data['studentGroup']

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

    def __str__(self):
        return '%s %s-%s: %s with %s in %s' % (
                self.start.strftime('%d.%m.'), self.start.strftime('%H:%M'), self.end.strftime('%H:%M'),
                ', '.join([e['name'] for e in self.getElements(ElementType.subject)]),
                ', '.join([e['name'] for e in self.getElements(ElementType.teacher)]),
                ', '.join([e['name'] for e in self.getElements(ElementType.room)]),
            )

class Timetable():
    def __init__(self):
        self._days = defaultdict(list)

    def periods(self):
        """Returns a timedate-sorted list of all periods in the timetable"""
        out = []
        for day in self._days.values():
            out += day

        return sorted(out, key=lambda p: p.start)

    def add_period(self, period):
        # check for overlap with existing periods
        for other_p in self.periods():
            if period.end <= other_p.start or other_p.end <= period.start:
                # out of range or barely touching one side, both ok
                continue

            if (period.start == other_p.start) and (period.end == other_p.end):
                # exactly the same, also ok
                continue

            raise ValueError('Periods overlap weirdly: %s and %s' % (other_p, period))

        day = self._days[period.start.date()]

        day.append(period)
        day.sort(key=lambda p: p.start)

    def days(self):
        """Return a sorted list of days"""
        return [self._days[d] for d in sorted(self._days)]

def fetch_config(schoolname, element_type, date):
    url = 'https://neilo.webuntis.com/WebUntis/api/public/timetable/weekly/pageconfig?type=%d&date=%s' % (element_type.value, date.strftime('%Y-%m-%d'))

    r = requests.get(url, cookies={'schoolname': '_' + base64.b64encode(schoolname.encode()).decode()})
    return r.json()['data']

def fetch_periods(schoolname, grade_id, date):
    url = 'https://neilo.webuntis.com/WebUntis/api/public/timetable/weekly/data?elementType=%d&elementId=%d&date=%s' % (ElementType.grade.value, grade_id, date.strftime('%Y-%m-%d'))

    r = requests.get(url, cookies={'schoolname': '_' + base64.b64encode(schoolname.encode()).decode()})
    return r.json()['data']['result']

def parse_args():
    parser = argparse.ArgumentParser(description='Extract timetable information from WebUntis')

    parser.add_argument('schoolname', help='name of the school')
    parser.add_argument('grade', help='name of the grade/class')
    parser.add_argument('-d', '--date', type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(), default=datetime.now().date(),
            help='show timetable for specific date (YYYY-MM-DD) instead of today')

    return parser.parse_args()

def main():
    args = parse_args()

    grades = fetch_config(args.schoolname, ElementType.grade, args.date)['elements']
    grade_id = list(filter(lambda e: e['name'] == args.grade, grades))

    if not grade_id:
        raise ValueError('Specified grade not found')

    grade_id = grade_id[0]['id']

    data = fetch_periods(args.schoolname, grade_id, args.date)

    elements = ElementRegistry()
    for el in data['data']['elements']:
        elements.addElement(el)

    tt = Timetable()

    for period in data['data']['elementPeriods'][str(grade_id)]:
        tt.add_period(Period(period, elements))

    # dict of rows, first index is start time, second index is date, third index is irrelevant (for multiple periods per time slot)
    rows = {}
    for day in tt.days():
        for p in day:
            if p.start.time() not in rows:
                rows[p.start.time()] = {}

            row = rows[p.start.time()]

            if p.start.date() not in row:
                row[p.start.date()] = []

            row[p.start.date()].append(p)

    indices = []
    rows_mangled = []
    for time in sorted(rows):
        indices.append(time.strftime('%H:%M'))
        rows_mangled.append({day.strftime('%A'): '\n'.join([list(p.getElements(ElementType.subject))[0]['name'] for p in periods]) for day, periods in rows[time].items()})

    print(tabulate(rows_mangled, headers='keys', showindex=indices, tablefmt='grid'))

if __name__ == '__main__':
    main()
