from PyQt5.QtCore import Qt, QBasicTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QFrame, QDesktopWidget, QApplication
from PyQt5.QtGui import QPainter, QColor
from enum import Enum
import numpy as np
import random
import sys, random

"""
inspired by http://zetcode.com/gui/pyqt5/tetris/
adapted for numpy + coding style

Positions: (row, column)
row: 0 at top
column: 0 left
"""

class Tetris(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.board = Board(self)
        self.setCentralWidget(self.board)

        self.status_bar = self.statusBar()
        self.board.print_status[str].connect(self.status_bar.showMessage)

        self.board.start()

        self.resize(180, 380)
        self.center()
        self.setWindowTitle('Tetris')
        self.show()

    def center(self):
        """Center the window on the screen"""

        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move(
                (screen.width()-size.width())/2,
                (screen.height()-size.height())/2
            )

class Shape:
    def __init__(self, color, block_mask):
        """
        Create a Shape with specific color and fields

        color: QColor
        fieldmap: 2-dimensional array of rows, value truthiness determines if block is part of the shape
        """
        self.color = color

        self.block_mask = np.array(block_mask)

    def blocks(self):
        """
        Return array of (row, col) pairs of all blocks in the shape
        """

        # get positions of blocks that are set
        blocks = np.array(self.block_mask.nonzero())

        # transpose for correct x/y alignment
        return blocks.T

    def rotate_left(self):
        """Return a Shape rotated to the left"""
        return Shape(self.color, np.rot90(self.block_mask))

    def rotate_right(self):
        """Return a Shape rotated to the right"""
        return Shape(self.color, np.rot90(self.block_mask, -1))


class Tetromino(Enum):
    S = Shape(QColor(0xCC6666), [
            [1,0],
            [1,1],
            [0,1]
        ])
    Z = Shape(QColor(0x66CC66), [
            [0,1],
            [1,1],
            [1,0]
        ])
    Line = Shape(QColor(0x6666CC), [
            [1],
            [1],
            [1],
            [1]
        ])
    T = Shape(QColor(0xCCCC66), [
            [1,1,1],
            [0,1,0]
        ])
    Square = Shape(QColor(0xCC66CC), [
            [1,1],
            [1,1]
        ])
    L = Shape(QColor(0x6CCCC), [
            [1,0],
            [1,0],
            [1,1]
        ])
    MirroredL = Shape(QColor(0xDAAA00), [
            [0,1],
            [0,1],
            [1,1]
        ])

class Board(QFrame):
    print_status = pyqtSignal(str)

    WIDTH = 10
    HEIGHT = 22
    SPEED = 300

    def __init__(self, parent):
        super().__init__(parent)

        self.init_board()

    def init_board(self):
        self.timer = QBasicTimer()
        self.rows_removed = 0
        # array of colors
        self.board = np.zeros((self.HEIGHT, self.WIDTH))

        self.setFocusPolicy(Qt.StrongFocus)
        self.is_started = False
        self.is_paused = False
        self.need_new_piece = False

    def square_width(self):
        return self.contentsRect().width() // self.WIDTH

    def square_height(self):
        return self.contentsRect().height() // self.HEIGHT

    def start(self):
        """starts the game"""

        if self.is_started:
            raise RuntimeError('Tried to start board twice')

        self.is_started = True
        self.new_piece()
        self.timer.start(self.SPEED, self)

    def pause(self):
        if not self.is_started:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.timer.stop()
            self.print_status.emit('paused')
        else:
            self.timer.start(self.SPEED, self)
            self.print_status.emit(str(self.rows_removed))

        self.update()

    def keyPressEvent(self, e):
        if not (self.is_started and self.cur_type):
            super(Board, self).keyPressEvent(e)
            return

        key = e.key()

        if key == Qt.Key_P:
            self.pause()

        if self.is_paused:
            return
        elif key == Qt.Key_Left:
            self.try_move(self.cur_shape, self.cur_pos - [0, 1])
        elif key == Qt.Key_Right:
            self.try_move(self.cur_shape, self.cur_pos + [0, 1])
        elif key == Qt.Key_Up:
            self.try_move(self.cur_shape.rotate_left(), self.cur_pos)
        elif key == Qt.Key_Down:
            self.try_move(self.cur_shape.rotate_right(), self.cur_pos)
        elif key == Qt.Key_Space:
            self.drop_piece()

    def paintEvent(self, e):
        painter = QPainter(self)
        rect = self.contentsRect()

        board_top = rect.bottom() - self.HEIGHT * self.square_height()

        for row in range(self.HEIGHT):
            for col in range(self.WIDTH):
                color = self.board[row, col]

                if color:
                    self.draw_square(painter, (
                            board_top + row * self.square_height(),
                            rect.left() + col * self.square_width(),
                        ), QColor(color))

        if self.cur_type:
            for pos in self.cur_shape.blocks():
                vpos, hpos = self.cur_pos + pos
                self.draw_square(painter, (
                        board_top + vpos * self.square_height(),
                        rect.left() + hpos * self.square_width(),
                    ), self.cur_shape.color)


    def timerEvent(self, e):
        if e.timerId() == self.timer.timerId():
            if self.need_new_piece:
                self.new_piece()
            else:
                self.move_piece_down()
        else:
            super(Board, self).timerEvent(event)

    def move_piece_down(self):
        """Try to move a piece down, release and return false if unable"""

        if not self.try_move(self.cur_shape, self.cur_pos + [1, 0]):
            self.release_piece()
            return False

        return True

    def drop_piece(self):
        """Drop a piece all the way down"""
        while self.move_piece_down():
            pass

    def release_piece(self):
        """Fix the current piece to the board"""

        for pos in self.cur_shape.blocks():
            vpos, hpos = self.cur_pos + pos
            self.board[vpos, hpos] = self.cur_shape.color.rgba()

        self.remove_full_rows()
        self.need_new_piece = True

    def remove_full_rows(self):
        to_remove = []
        for i, row in enumerate(self.board):
            if row.all():
                to_remove.append(i)

        for rownum in to_remove:
            self.board[0:rownum+1] = np.vstack((
                    np.zeros_like(self.board[0]),
                    self.board[0:rownum]
                ))

        self.rows_removed += len(to_remove)

        self.print_status.emit(str(self.rows_removed))
        self.update()


    def new_piece(self):
        self.need_new_piece = False
        self.cur_type = random.choice(list(Tetromino))
        self.cur_shape = self.cur_type.value

        self.cur_pos = np.array([0, self.WIDTH // 2 + 1])

        if not self.try_move(self.cur_shape, self.cur_pos):
            self.timer.stop()
            self.cur_type = None
            self.cur_shape = None
            self.is_started = False
            self.print_status.emit('Game over')

    def try_move(self, piece, pos):
        """Try to move a Shape to a given position"""

        offset_blocks = piece.blocks() + pos

        # out of bounds
        if (offset_blocks < [0,0]).any() or (offset_blocks >= [self.HEIGHT, self.WIDTH]).any():
            return False

        # overlaps with existing shape
        if self.board[tuple(offset_blocks.T)].any():
            return False

        self.cur_pos = pos
        self.cur_shape = piece
        self.update()
        return True

    def draw_square(self, painter, pos, color):
        """
        Draw a square at a given pixel position with the given color

        pos: (vertical from top, horizontal from left)
        color: QColor
        """

        vpos, hpos = pos
        painter.fillRect(hpos+1, vpos+1, self.square_width()-2, self.square_height()-2, color)

        painter.setPen(color.lighter())
        painter.drawLine(hpos, vpos, hpos, vpos + self.square_height() - 1)
        painter.drawLine(hpos, vpos, hpos + self.square_width() - 1, vpos)

        painter.setPen(color.darker())
        painter.drawLine(hpos + 1, vpos + self.square_height() - 1,
                hpos + self.square_width() - 1, vpos + self.square_height() - 1)
        painter.drawLine(hpos + self.square_width() - 1, vpos + self.square_height() - 1,
                hpos + self.square_width() - 1, vpos + 1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    tetris = Tetris()
    sys.exit(app.exec_())
