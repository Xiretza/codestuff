#!/usr/bin/env python

import argparse
import sys

parser = argparse.ArgumentParser(description='Run a brainfuck program')

parser.add_argument('infile', metavar='program', type=argparse.FileType('r'),
                    help='the brainfuck program to run')
parser.add_argument('--eof-behaviour', '-e', dest='eof', default='unchanged', choices=['0', '-1', 'unchanged'],
                    help='behaviour on EOF (set to 0 or -1 or leave unchanged)')

args = parser.parse_args()

p = 0
pc = 0
# counter to skip to the end of loops, increment on [, decrement on ] (done when 0)
seek_loop_end = 0
# program counter locations for loop beginnings
loops = []
memory = {}

with args.infile:
    program = args.infile.read()

while pc < len(program):
    # the current command
    c = program[pc]
    pc += 1

    # we need to search for a ], when seek_loop_count reaches 0 we're there
    if seek_loop_end > 0:
        if c == '[':
            seek_loop_end += 1
        elif c == ']':
            seek_loop_end -= 1

        continue

    if c == '<':
        p -= 1
    elif c == '>':
        p += 1
    elif c == '-':
        memory[p] = memory.get(p, 0) - 1
    elif c == '+':
        memory[p] = memory.get(p, 0) + 1
    elif c == '.':
        sys.stdout.write(chr(memory[p]))
    elif c == ',':
        in_c = sys.stdin.read(1)
        if in_c:
            in_c = ord(in_c)
        else:
            if args.eof == '0':
                in_c = 0
            elif args.eof == '-1':
                in_c = -1
            elif args.eof == 'unchanged':
                in_c = memory[p]

        memory[p] = in_c
    elif c == '[':
        # current cell is 0, skip the loop
        if memory.get(p, 0) == 0:
            seek_loop_end = 1
        else:
            # push the location of the [ to the loop stack for later backtracking
            loops.append(pc - 1)
    elif c == ']':
        pc = loops.pop()
