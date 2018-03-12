import wochenplan
from datetime import date

import json

class CustomEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        if isinstance(o, date):
            return o.isoformat()
        elif isinstance(o, wochenplan.Plan):
            return {'__kind': 'Plan',
                    'start_date': o.start_date,
                    'end_date': o.end_date,
                    'menus': o.menus}
        elif isinstance(o, wochenplan.Menu):
            return {'__kind': 'Menu',
                    'name': o.name,
                    'price': o.price,
                    'days': o.days}
        elif isinstance(o, wochenplan.Meal):
            return {'__kind': 'Meal',
                    'name': o.name,
                    'allergens': o.allergens}

        return super().default(o)


def output_table(plan):
    """Generator to return a table view of a Plan"""
    
    yield 'Plan vom %s bis %s\n\n' % (plan.start_date, plan.end_date)

    for day in wochenplan.DAYS:
        soup = plan.menus[0].get_day(day)[0]

        yield '%s\nSuppe: %s\n' % (day, soup)

        for menu in plan.menus:
            meal = menu.get_day(day)[1]
            yield 'Menü %s (%.2f€): %s\n' % (menu.name, menu.price / 100, meal)

        yield '\n'

    # list of allergens
    yield ', '.join([': '.join(ag) for ag in wochenplan.ALLERGENS.items()])
    yield '\n'


def output_json(plan):
    """Generator to return a JSON representation of a Plan"""

    yield json.dumps(plan, cls=CustomEncoder, indent=2)


def output_csv(plan):
    pass
