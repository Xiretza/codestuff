#!/usr/bin/env python

import argparse
import output
import sys
import wochenplan
import xml.etree.ElementTree as ET

def setup_parser():
    parser = argparse.ArgumentParser(description='Mensa-Wochenplan parsen')

    parser.add_argument('infile', type=argparse.FileType('r'),
                        help='the HTML file to be parsed (specify - for stdin)')
    parser.add_argument('-o', '--outfile', type=argparse.FileType('w'), default=sys.stdout,
                        help='output to file (instead of stdout)')
    #parser.add_argument('--extract', dest='to_extract', metavar='extract_targets', type=argument_list(config['extract_types']), default=config['extract_types'])

    outopts = parser.add_mutually_exclusive_group(required=True)
    outopts.add_argument('--validate', action='store_const', dest='outfunction',
                         const=wochenplan.validate,
                         help='no output, only validate')
    outopts.add_argument('--start-date', action='store_const', dest='outfunction',
                         const=lambda p: ['%s\n' % p.start_date],
                         help='output start date in ISO format')
    outopts.add_argument('--end-date', action='store_const', dest='outfunction',
                         const=lambda p: ['%s\n' % p.end_date],
                         help='output end date in ISO format')
    outopts.add_argument('-t', '--table', action='store_const', dest='outfunction',
                         const=output.output_table,
                         help='output plan as a nice table')
    outopts.add_argument('-j', '--json', action='store_const', dest='outfunction',
                         const=output.output_json,
                         help='output plan as JSON')
    outopts.add_argument('-c', '--csv', action='store_const', dest='outfunction',
                         const=output.output_csv,
                         help='output plan as CSV')

    return parser

def main():
    parser = setup_parser()
    args = parser.parse_args()
    with args.infile:
        tree = ET.parse(args.infile)

    plan = wochenplan.Plan()

    plan.set_timespan(wochenplan.extract_timespan(tree))

    tab = tree.find('.//table')
    for rownum, row in enumerate(tab.iter('tr')):
        rowtype = rownum % 3

        for colnum, col in enumerate(row.iter('td')):
            # get all text inside field
            text = ''.join(col.itertext())
            text = text.translate(str.maketrans('\n', ' ', '\t')).strip()

            # menu header
            if rowtype == 0:
                current_menu = wochenplan.parse_menu_header(text)
                if int(current_menu.name) != rownum / 3 + 1:
                    raise ParseError('menu/row desync, menu = %d, rownum = %d'
                                     % (int(current_menu.name), rownum))

                plan.menus.append(current_menu)
            # day
            elif rowtype == 1:
                if not text == wochenplan.DAYS[colnum]:
                    raise ParseError('wrong day: is %r, should be %r' % (text, DAYS[colnum]))
            # courses for one day
            elif rowtype == 2:
                meals = wochenplan.parse_day_menu(text)

                current_menu.add_day(wochenplan.DAYS[colnum], meals)

    wochenplan.validate(plan)

    output = args.outfunction(plan)

    if output:
        with args.outfile:
            for chunk in output:
                args.outfile.write(chunk)

if __name__ == '__main__':
    main()
