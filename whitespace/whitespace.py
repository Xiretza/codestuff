#!/usr/bin/env python

import argparse
import sys
from enum import Enum
import re

"""
for https://www.codewars.com/kata/whitespace-interpreter
characters are represented as:
's' = ' ' (0x20)
't' = '\t' (0x09)
'n' = '\n' (0x0A)
"""

class Command:
    def __init__(self, name, imp, ins, takes_num=False, takes_label=False):
        if takes_num and takes_label:
            raise ValueError("instruction can't take both number and label")

        self.takes_num = takes_num
        self.takes_label = takes_label

        self.name = name
        self.imp = imp
        self.ins = ins
        self.full = imp.value + ins

    def __str__(self):
        return '{%s.%s (%s %s)}' % (self.imp.name, self.name, self.imp.value, self.ins)

    def __repr__(self):
        return 'Command(%r, %r, %r, %r, %r)' % (self.name, self.imp, self.ins, self.takes_num, self.takes_label)

class IMP(Enum):
    stack = ('s', {
            'push': 's_n',
            'dup_n': 'ts_n',
            'discard_n': 'tn_n',
            'dup': 'ns',
            'swap': 'nt',
            'discard': 'nn',
        })

    arithmetic = ('ts', {
            'add': 'ss',
            'sub': 'st',
            'mul': 'sn',
            'div': 'ts',
            'mod': 'tt',
        })

    heap = ('tt', {
            'store': 's',
            'get': 't',
        })

    io = ('tn', {
            'out_c': 'ss',
            'out_n': 'st',
            'in_c': 'ts',
            'in_n': 'tt',
        })

    flow = ('n', {
            'mark': 'ss_l',
            'call': 'st_l',
            'jump': 'sn_l',
            'jz': 'ts_l',
            'jlz': 'tt_l',
            'ret': 'tn',
            'exit': 'nn',
        })

    def __new__(cls, prefix, instructions):
        obj = object.__new__(cls)
        obj._value_ = prefix
        for name, code in instructions.items():
            parts = code.split('_')
            ins = parts[0]
            cmd = Command(name, obj, ins, 'n' in parts[1:], 'l' in parts[1:])
            setattr(obj, name, cmd)

        return obj

print('t' in IMP)
print(IMP.stack)
print(IMP.stack.value)
print(IMP.stack.dup)

def clean(program):
    """
    strips everything but space/tab/newline, replaces them with s/t/n
    """

    return re.sub(r'[^ \t\n]', '', program).translate(str.maketrans(' \t\n', 'stn'))

def consume_any(code, choices):
    """
    seek in code until a match in choices is found
    return (match, position after match)
    raise ValueError if no match found
    
    >>> consume_any('abcde', ['b', 'abc', 'ab'])
    ('ab', 2)
    >>> consume_any('dfghi', ['b', 'abc', 'ab'])
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "whitespace.py", line 120, in consume_any
        raise ValueError('no match found in %r for %r' % (code, choices))
    ValueError: no match found in 'dfghi' for ['b', 'abc', 'ab']
    """
    
    if not code:
        raise ValueError('tried to consume from empty string')

    max_len = max(len(x) for x in choices)

    pos = 1
    for pos in range(max_len):
        if code[:pos] in choices:
            return (code[:pos], pos)

    raise ValueError('no match found in %r for %r' % (code, choices))

def parse(program):
    """
    returns list of Command()
    """
    
    last_end = 0
    pos = 1
    current_imp = None
    while pos < len(program):
        imp, loc = consume_any(program, [imp.value for imp in IMP])
        print(imp)
        cmd, loc = consume_any(program[loc:], [ins.ins for ins in IMP(imp)])
        print(cmd)

        return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a whitespace program')

    #parser.add_argument('infile', metavar='program', type=argparse.FileType('r'),
    #                    help='the brainfuck program to run')

    args = parser.parse_args()

    program = "   \t\n\t\n \t\n\n\n"

    program = clean(program)
    print(program)
    program = parse(program)
    print(program)

    #with args.infile:
    #    program = args.infile.read()
