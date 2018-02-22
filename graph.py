#!/usr/bin/env python
import math

columns = 160
rows = 40

omega = 1

vals = [math.cos(0.06 * i) for i in range(columns)]
#vals = [math.cos(omega * i) for i in range(columns)]

maxval = max(vals)
minval = min(vals)

def matrix_to_braille(matrix):
    codepoint = 0x2800
    for x, row in enumerate(matrix):
        for y, enabled in enumerate(row): 
            codepoint += ((0x1, 0x8), (0x2, 0x10), (0x4, 0x20), (0x40, 0x80))[x][y] if enabled else 0

    return chr(codepoint)

pattern_one = matrix_to_braille(((1,0), (0,1), (1,0), (0,1)))
pattern_two = matrix_to_braille(((0,1), (1,0), (0,1), (1,0)))

for i in range(5):
    print(pattern_one * 10)
    print(pattern_two * 10)

# convert to pixel coordinates
vals = [
        math.floor((n - minval) * (rows - 1) / (maxval-minval) + 0.5)
        for n in vals
    ]

matrix = [[" "] * columns for x in range(rows)]

for col, val in enumerate(vals):
    matrix[val][col] = "x"

    # get previous and next columns' values
    prevval = vals[col - 1] if col != 0 else val
    nextval = vals[col + 1] if col != len(vals)-1 else val

    # switch them around so that prev isn't larger than next (for range() and rounding)
    if prevval > nextval:
        prevval, nextval = nextval, prevval

    # calculate the average value between current and prev/next column's value
    prevavg = math.floor((val+prevval)/2 + 0.5)
    nextavg = math.floor((val+nextval)/2 + 0.5)

    # fill in the lines
    for n in range(prevavg, nextavg):
        matrix[n][col] = "x"

for row in reversed(matrix):
    print("".join(row))
