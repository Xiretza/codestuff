#!/usr/bin/env python
import math
import numpy as np
import statistics

use_braille = True

columns = 160
rows = 40

omega = 0.1
offset = 0

#vals = [1 - math.exp(omega * -i) for i in range(columns)]
vals = [math.cos(omega * i) for i in range(columns)]
#vals = [(i%2) for i in range(math.floor(columns/10))]
#vals = [math.sqrt((1 - (omega * i)**2)) for i in range(columns)]

maxval = max(vals)
minval = min(vals)

# returns numbers from start to end, inclusive
def fromto(start, end):
    if start < end:
        return range(start, end+1)
    else:
        return range(start, end-1, -1)

# takes array of 4 rows with 2 truthy/falsy columns each
def matrix_to_braille(matrix):
    codepoint = 0x2800
    for x, row in enumerate(matrix):
        for y, enabled in enumerate(row): 
            codepoint += ((0x1, 0x8), (0x2, 0x10), (0x4, 0x20), (0x40, 0x80))[x][y] if enabled else 0

    return chr(codepoint)

class Coord:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return "(%d, %d)" % (self.x, self.y)

    def get_cart(self):
        return (self.x, self.y)

    def get_polar(self):
        mag = math.sqrt(sum(self.get_cart() ** 2))
        phi = math.atan(self.y / self.x)
        return (mag, phi)

class Matrix:
    def __init__(self, w, h, fill):
        self.w = w
        self.h = h
        self._data = np.zeros((h, w))
    
    def set_coord(self, x, y, val):
        #print("set %s to %d" % (Coord(x, y), val))
        self._data[y, x] = val

    def get_coord(self, x, y):
        return self._data[y, x]

    def get_row(self, y):
        return self._data[y]
    
    # [row] generator
    def rows(self):
        return self._data

    # (Coord, point) generator
    def points(self):
        return self._data.flat
    
    def extract(self, _start, _end):
        start = Coord(min(_start.x, _end.x), min(_start.y, _end.y))
        end = Coord(max(_start.x, _end.x), max(_start.y, _end.y))
        
        #print("extract from %s to %s" % (start, end))

        #diffx = end.x-start.x
        #diffy = end.y-start.y

        #new_matrix = Matrix(diffx+1, diffy+1, 0)

        return self._data[start.y:end.y+1, start.x:end.x+1]

    def draw_line(self, start, end):
        diffx = end.x-start.x
        diffy = end.y-start.y

        if diffx != 0:
            for x in fromto(start.x, end.x):
                self.set_coord(x, math.floor(start.y + (x-start.x) * diffy/diffx + 0.5), 255)
 
        if diffy != 0:
            for y in fromto(start.y, end.y):
                self.set_coord(math.floor(start.x + (y-start.y) * diffx/diffy + 0.5), y, 255)

    def render(self, ren):
        ren.draw(self)

    def scale(self, new_w, new_h):
        new_matrix = Matrix(new_w, new_h, 0)

        factor_w = self.w/new_w
        factor_h = self.h/new_h

        for y in range(new_h):
            for x in range(new_w):
                extracted = self.extract(
                    Coord(
                        math.floor(factor_w * x + 0.5),
                        math.floor(factor_h * y + 0.5)
                    ),
                    Coord(
                        math.floor(factor_w * (x+1) - 0.5),
                        math.floor(factor_h * (y+1) - 0.5)
                    )
                )

                avg = extracted.mean()

                #if avg > 0: print("avg: %d" % avg)

                new_matrix.set_coord(x, y, avg)

        return new_matrix

class MatrixRender:
    def __init__():
        self.matrix = matrix

    def draw(self, matrix):
        print("dummy matrix draw")

class RenderConsole(MatrixRender):
    def __init__(self, w, h):
        self.w = w
        self.h = h

    def draw(self, matrix):
        self.matrix = matrix.scale(self.w, self.h)
        for row in reversed(self.matrix.rows()):
            print("".join([
                [" ", "-", "o", "x"][max(min(math.floor(p/40), 3), 0)]
                #"x" if p else " "
                for p in row
            ]))

pattern_one = matrix_to_braille(((1,0), (0,1), (1,0), (0,1)))
pattern_two = matrix_to_braille(((0,1), (1,0), (0,1), (1,0)))

#for i in range(5):
#    print(pattern_one * 10)
#    print(pattern_two * 10)

# convert to pixel coordinates
vals = [
        math.floor((n - minval) * (rows - 1) / (maxval-minval) + 0.5)
        for n in vals
    ]

matrix = Matrix(300, 100, 0)

for col, val in enumerate(vals):
    # get previous column's value
    prevval = vals[col - 1] if col != 0 else val

    matrix.draw_line(Coord(col-1, prevval), Coord(col, val))

c1 = Coord(50, 30)
c2 = Coord(100, 35)

matrix.draw_line(c1, c2)

render = RenderConsole(columns, rows)

matrix.render(render)

#for row in reversed(matrix.rows()):
#    print("".join(row))
