#!/usr/bin/env python

import argparse
import sys
from enum import Enum
import re
from io import StringIO

"""
for https://www.codewars.com/kata/whitespace-interpreter
characters are represented as:
's' = ' ' (0x20)
't' = '\t' (0x09)
'n' = '\n' (0x0A)
"""

class Command:
    def __init__(self, ins, number=None, label=None):
        """
        ins: the Instruction()
        """

        self.ins = ins
        self.imp = ins.imp

        if self.ins.takes_number != (number is not None) or self.ins.takes_label != (label is not None):
            raise ValueError("payload mismatch: %r, number=%r, label=%r" % (self.ins, number, label))

        self.number = number
        self.label = label

    def __str__(self):
        return '{%s.%s(%s) (number=%r, label=%s)}' % (self.imp.name, self.ins.name, self.ins.value, self.number, self.label)

    def beautiful(self):
        return self.ins.name + (' ' + str(self.number) if self.number is not None else '') + (' %r' % str(self.label) if self.label is not None else '')

    def __repr__(self):
        return 'Command(%r, %r, %r)' % (self.ins, self.number, self.label)

class Program:
    """class that saves commands and regulates flow"""

    commands = []
    labels = {}
    pc = 0
    call_stack = []

    def jump(self, label):
        """
        jump execution to a given label
        """
        if label not in self.labels:
            raise ValueError('tried to jump to nonexistent label: %r' % (label,))

        self.pc = self.labels[label]

    def advance(self):
        """
        advance the pc by 1
        """
        self.pc += 1

    def add_command(self, cmd):
        if cmd.ins == Instruction.mark:
            if cmd.label in self.labels:
                raise ValueError('tried to redefine label')
            self.labels[cmd.label] = len(self.commands)
        else:
            self.commands.append(cmd)

    def get_command(self):
        """
        return the command at the current pc
        """

        if self.pc >= len(self.commands):
            raise ValueError('unexpected end of program')
        return self.commands[self.pc]

    def call(self, label):
        """jump to label and store the return address"""
        self.call_stack.append(self.pc)
        self.jump(label)

    def ret(self):
        """return execution to the address stored by the last call()"""

        self.pc = self.call_stack.pop()

    def __str__(self):
        out = ['\t' + cmd.beautiful() for cmd in self.commands]
        for label, pos in self.labels.items():
            out.insert(pos, label + ':')

        return '\n'.join(out)

class IMP(Enum):
    stack = 's'
    arithmetic = 'ts'
    heap = 'tt'
    io = 'tn'
    flow = 'n'

class Instruction(Enum):
    push = (IMP.stack, 's_n')
    dup_n = (IMP.stack, 'ts_n')
    discard_n = (IMP.stack, 'tn_n')
    dup = (IMP.stack, 'ns')
    swap = (IMP.stack, 'nt')
    discard = (IMP.stack, 'nn')

    add = (IMP.arithmetic, 'ss')
    sub = (IMP.arithmetic, 'st')
    mul = (IMP.arithmetic, 'sn')
    div = (IMP.arithmetic, 'ts')
    mod = (IMP.arithmetic, 'tt')

    store = (IMP.heap, 's')
    get = (IMP.heap, 't')

    out_c = (IMP.io, 'ss')
    out_n = (IMP.io, 'st')
    in_c = (IMP.io, 'ts')
    in_n = (IMP.io, 'tt')

    mark = (IMP.flow, 'ss_l')
    call = (IMP.flow, 'st_l')
    jump = (IMP.flow, 'sn_l')
    jz = (IMP.flow, 'ts_l')
    jlz = (IMP.flow, 'tt_l')
    ret = (IMP.flow, 'tn')
    exit = (IMP.flow, 'nn')

    def __new__(cls, imp, ins_str):
        ins_parts = ins_str.split('_')
        obj = object.__new__(cls)

        obj.imp = imp
        obj.code = ins_parts[0]
        obj._value_ = imp.value + obj.code

        obj.takes_number = 'n' in ins_parts[1:]
        obj.takes_label = 'l' in ins_parts[1:]
        if obj.takes_number and obj.takes_label:
            raise ValueError("instruction can't take both number and label")

        return obj

def clean(program):
    """
    strips everything but space/tab/newline, replaces them with s/t/n
    """

    return re.sub(r'[^ \t\n]', '', program).translate(str.maketrans(' \t\n', 'stn'))

def consume_any(code, choices, offset=0):
    """
    seek in code until a match in choices is found
    return (match, position after match)
    """

    if len(code) <= offset:
        raise ValueError('tried to consume from empty string')

    max_len = max(len(x) for x in choices)

    code_part = code[offset:]

    for pos in range(max_len+1):
        if code_part[:pos] in choices:
            return (code_part[:pos], offset+pos)

    raise ValueError('no match found in %r for %r' % (code_part, choices))

def consume_number(code, offset=0):
    terminal = code.find('n', offset)
    if terminal == offset:
        raise ValueError('empty number (only terminal, no sign)')
    if terminal == offset+1:
        return 0, terminal+1

    sign = {'t': -1, 's': 1}[code[offset]]

    return sign * int(code[offset+1:terminal].translate(str.maketrans('st', '01')), 2), terminal+1

def consume_label(code, offset=0):
    terminal = code.find('n', offset)

    return code[offset+1:terminal], terminal+1

def parse(code):
    """
    takes string of s/t/n
    returns Program()
    """

    imp_ins_map = {imp: [] for imp in IMP}

    for ins in Instruction:
        imp_ins_map[ins.imp].append(ins)

    prog = Program()

    last_end = 0
    pos = 0

    while pos < len(code):
        ins, pos = consume_any(code, [ins.value for ins in Instruction], pos)
        ins = Instruction(ins)

        if ins.takes_number:
            num, pos = consume_number(code, pos)
            cmd = Command(ins, number=num)
        elif ins.takes_label:
            label, pos = consume_label(code, pos)
            cmd = Command(ins, label=label)
        else:
            cmd = Command(ins)

        prog.add_command(cmd)
        last_end = pos

    return prog

def run(program, inp, output):
    """
    takes Program(), input and output TextIO
    """

    stack = []
    call_stack = []
    heap = {}
    pc = 0

    while True:
        cmd = program.get_command()
        ins = cmd.ins

        program.advance()

        if ins == Instruction.push:
            stack.append(cmd.number)
        elif ins == Instruction.dup_n:
            if cmd.number >= len(stack):
                raise ValueError('tried to duplicate too far down the stack')
            stack.append(stack[len(stack)-cmd.number-1])
        elif ins == Instruction.discard_n:
            n = cmd.number if cmd.number > 0 else len(stack)
            del stack[-n-1:-1]
        elif ins == Instruction.dup:
            if not stack:
                raise ValueError('tried to dup empty stack')
            stack.append(stack[-1])
        elif ins == Instruction.swap:
            if len(stack) < 2:
                raise ValueError('tried to swap less than 2 elements')
            stack[-2:] = stack[-1:-3:-1]
        elif ins == Instruction.discard:
            if not stack:
                raise ValueError('tried to discard from empty stack')
            stack.pop()
        elif cmd.imp == IMP.arithmetic:
            a = stack.pop()
            b = stack.pop()

            if ins == Instruction.add:
                stack.append(b+a)
            elif ins == Instruction.sub:
                stack.append(b-a)
            elif ins == Instruction.mul:
                stack.append(b*a)
            elif ins == Instruction.div:
                stack.append(b//a)
            elif ins == Instruction.mod:
                stack.append(b%a)
            else:
                raise ValueError('Unknown arithmetic operation')
        elif ins == Instruction.store:
            a = stack.pop()
            b = stack.pop()
            heap[b] = a
        elif ins == Instruction.get:
            a = stack.pop()
            if a not in heap:
                raise ValueError('bad heap address: %s' % (a,))
            stack.append(heap[a])
        elif ins == Instruction.out_c:
            output.write(chr(stack.pop()))
        elif ins == Instruction.out_n:
            output.write(str(stack.pop()))
        elif ins == Instruction.in_c:
            a = inp.read(1)
            if not a:
                raise ValueError('unexpected EOF on input')
            b = stack.pop()

            heap[b] = ord(a)
        elif ins == Instruction.in_n:
            a = inp.readline()
            if not a:
                raise ValueError('unexpected EOF on input')
            b = stack.pop()

            heap[b] = int(a)
        elif ins == Instruction.mark:
            raise ValueError('leftover mark')
        elif ins == Instruction.call:
            program.call(cmd.label)
        elif ins == Instruction.ret:
            program.ret()
        elif ins == Instruction.jump:
            program.jump(cmd.label)
        elif ins == Instruction.jz:
            if stack.pop() == 0:
                program.jump(cmd.label)
        elif ins == Instruction.jlz:
            if stack.pop() < 0:
                program.jump(cmd.label)
        elif ins == Instruction.exit:
            return
        else:
            raise ValueError('unknown instruction')

    raise ValueError('execution loop exited, something went terribly wrong')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a whitespace program')

    parser.add_argument('infile', metavar='program', type=argparse.FileType('r'),
                        help='the brainfuck program to run')
    parser.add_argument('-n', '--no-clean', action='store_true',
                        help='indicates that the given file already contains cleaned code (only s/t/n characters)')
    parser.add_argument('-o', '--output', metavar='outfile', nargs=1, type=argparse.FileType('w'), default=sys.stdout,
                        help='file to write the output to')

    args = parser.parse_args()

    with args.infile as f:
        code = f.read()

    if not args.no_clean:
        code = clean(code)

    print('after clean:', code)
    program = parse(code)
    print('after parse:', program)
    run(program, sys.stdin, args.output)
    if args.output.isatty():
        args.output.write('\n')

