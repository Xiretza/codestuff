#!/usr/bin/env python

import argparse
import sys
from enum import Enum
from io import TextIOBase, StringIO
from collections import defaultdict

"""
for https://www.codewars.com/kata/whitespace-interpreter
characters are represented as:
's' = ' ' (0x20)
't' = '\t' (0x09)
'n' = '\n' (0x0A)
"""

class Command:
    """an 'instance' of an Instruction, with payload"""

    def __init__(self, ins, number=None, label=None):
        """
        ins: the Instruction()
        number: the number argument (necessary depending on ins)
        label: the label argument (necessary depending on ins)
        """

        self.ins = ins
        self.imp = ins.imp

        if self.ins.takes_number != (number is not None) or self.ins.takes_label != (label is not None):
            raise ValueError("payload mismatch: %r, number=%r, label=%r" % (self.ins, number, label))

        self.number = number
        self.label = label

    def __str__(self):
        return self.ins.name + (' ' + str(self.number) if self.number is not None else '') + (' %r' % str(self.label) if self.label is not None else '')

    def __repr__(self):
        return 'Command(%r, %r, %r)' % (self.ins, self.number, self.label)

class Program:
    """class that saves commands and regulates program flow"""

    def __init__(self):
        self.commands = []
        self.labels = {}
        self.pc = 0
        self.call_stack = []

    def jump(self, label):
        """jump execution to a given label"""

        if label not in self.labels:
            raise ValueError('tried to jump to nonexistent label: %r' % (label,))

        self.pc = self.labels[label]

    def advance(self):
        """advance the program counter by 1"""

        self.pc += 1

    def add_command(self, cmd):
        """adds a command to the program. Handles label markers"""

        if cmd.ins == Instruction.mark:
            if cmd.label in self.labels:
                raise ValueError('tried to redefine label')
            self.labels[cmd.label] = len(self.commands)
        else:
            self.commands.append(cmd)

    def get_command(self):
        """return the command at the current pc"""

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
        out = ['\t' + str(cmd) for cmd in self.commands]
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
    """
    All individual instructions.
    initialization:
        code of the instruction, with optional '_n'/'_l' suffix if number/label argument is required
    items of each:
        name: the name of the instruction
        imp: the associated IMP
        code: the code of the instruction itself (without IMP)
        value: the code of the instruction including IMP code
        takes_number: true if the instruction requires a number argument
        takes_label: true if the instruction requires a label argument
    """

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
    """strips everything but space/tab/newline, replaces them with s/t/n"""

    return program.translate(defaultdict(str,
            str.maketrans(zip(' \t\n', 'stn'))
        ))

def consume_any(code, choices, offset=0):
    """
    seek from position 'offset' of code until a match in choices is found
    return (matched choice, position after match)

    >>> whitespace.consume_any('abcdef', ['bcd', 'ab', 'a'], 0)
    ('a', 1)
    >>> whitespace.consume_any('abcdef', ['bcd', 'ab', 'a'], 1)
    ('bcd', 4)
    >>> whitespace.consume_any('abcdef', ['bcd', 'ab', 'a'], 4)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "whitespace.py", line 185, in consume_any
        raise ValueError('no match found in %r for %r' % (code_part, choices))
    ValueError: no match found in 'ef' for ['bcd', 'ab', 'a']
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
    """
    seek from position 'offset' of code until a complete whitespace number is formed
    returns: (found number, position after terminal character)
    """

    terminal = code.find('n', offset)
    if terminal == offset:
        raise ValueError('empty number (only terminal, no sign)')
    if terminal == offset+1:
        return 0, terminal+1

    sign = {'t': -1, 's': 1}[code[offset]]
    bits = code[offset+1:terminal].translate(str.maketrans('st', '01'))

    return sign * int(bits, 2), terminal+1

def consume_label(code, offset=0):
    """
    seek from position 'offset' of code until a complete whitespace label is formed
    returns: (found label, position after terminal character)
    """
    terminal = code.find('n', offset)

    return code[offset:terminal], terminal+1

def parse(code):
    """
    takes string of s/t/n
    returns Program
    """

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
    """takes Program, input and output TextIO"""

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
                raise ValueError('unknown arithmetic operation')
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

def execute(code, inp=None, is_cleaned=False):
    """
    execute whitespace code, with optional input

    inp: TextIO or string to act as input for the program
    is_cleaned: input consists of s/t/n characters already

    returns: the produced output string
    """

    if is_cleaned:
        # make sure we still filter out any trailing newlines etc
        code = code.translate(defaultdict(str, str.maketrans({c: c for c in 'stn'})))
    else:
        code = clean(code)

    if isinstance(inp, str):
        inp = StringIO(inp)
    elif not isinstance(inp, TextIOBase):
        raise ValueError('unable to convert input %r to TextIO' % (inp,))

    output = StringIO()

    run(parse(code), inp, output)

    return output.getvalue()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a whitespace program')

    parser.add_argument('infile', metavar='program', type=argparse.FileType('r'),
                        help='the brainfuck program to run')
    parser.add_argument('-n', '--no-clean', action='store_true',
                        help='use this if the given file already contains cleaned code (only s/t/n characters)')
    parser.add_argument('-o', '--output', metavar='outfile', nargs=1, type=argparse.FileType('w'), default=sys.stdout,
                        help='file to write the output to')

    args = parser.parse_args()

    with args.infile as f:
        code = f.read()

    output = execute(code, sys.stdin, args.no_clean)

    args.output.write(output)

    if args.output.isatty():
        args.output.write('\n')
