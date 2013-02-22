"""Scott Hansen <firecat four one five three at gmail dot com>

Copyright (c) 2013, Scott Hansen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

import curses
import curses.ascii
import locale
from textwrap import wrap


class Editor(object):
    """ Basic python curses text editor class.

    Can be used for multi-line editing.

    Text will be wrapped to the width of the editing window, so there will be
    no scrolling in the horizontal direction. For now, there's no line
    wrapping, so lines will have to be wrapped manually.

    Args:
        stdscr:         the curses window object
        title:          title text
        inittext:       inital text content string
        win_location:   tuple (y,x) for location of upper left corner
        win_size:       tuple (rows,cols) size of the editor window
        box:            True/False whether to outline editor with a box
        max_text_size:  maximum rows allowed size for text.
                            Default=0 (unlimited)
                            If initext is longer than max_text_size, then
                            max_text_size will increase to that size so no data
                            is lost.
        pw_mode:        True/False. Whether or not to show text entry
                            (e.g. for passwords)

    Returns:
        text:   text string  or -1 on a KeyboardInterrupt

    Usage:
        from keepassc.editor import Editor
        Editor(box=False, inittext="Hi", win_location=(5, 5))()

    TODO: fix bottom of box disappears when backspacing
    TODO: fix pageup/pagedown for single line text entry
    TODO: x-scrolling. Enable long lines to be pasted without cutting them off.
          - Scroll the entire screen left/right.
          - If going up or down to a new line, jump to the end of that line and
            scroll sideways to put the cursor at the right edge of the box if
            the line is longer than the box.
          - Or should I just wrap lines to stay within the visible box, but
            don't add '\n' unless a newline is desired? This will mess with my
            line counts for the visible box....

    """

    def __init__(self, scr, title="", inittext=" ", win_location=(0, 0),
                 win_size=(20, 80), box=True, max_text_size=0, pw_mode=False):
        self.space_counter = 0
        self.scr = scr
        self.title = title
        self.box = box
        self.max_text_size = max_text_size
        self.pw_mode = pw_mode
        if self.pw_mode is True:
            try:
                curses.curs_set(0)
            except:
                print('Invisible cursor not supported.')
        else:
            try:
                curses.curs_set(1)
            except:
                pass
            curses.echo()
        locale.setlocale(locale.LC_ALL, '')
        encoding = locale.getpreferredencoding()
        curses.use_default_colors()
        self.resize_flag = False
        self.win_location_x, self.win_location_y = win_location
        self.win_size_orig_y, self.win_size_orig_x = win_size
        self.win_size_y = self.win_size_orig_y
        self.win_size_x = self.win_size_orig_x
        if self.win_size_y < 2 and self.max_text_size == 1:
            # For single line windows limited to max_text_size=1, allow
            # scrolling text in the x direction. < 2 because I can't get the
            # extra line at the bottom of the text window to be usable.
            self.x_scroll = True
        else:
            self.x_scroll = False
        self.win_init()
        self.box_init()
        self.text_init(inittext or " ")  # Make sure empty string isn't passed
        self.text_orig = self.text[:]
        self.keys_init()
        self.display()

    def __call__(self):
        return self.run()

    def box_init(self):
        """Clear the main screen and redraw the box and/or title

        """
        # Touchwin seems to save the underlying screen and refreshes it (for
        # example when the help popup is drawn and cleared again)
        self.scr.touchwin()
        self.scr.refresh()
        self.stdscr.clear()
        self.stdscr.refresh()
        quick_help = "   (F2 or Enter: Save, F5: Cancel)"
        if self.box is True:
            self.boxscr.clear()
            self.boxscr.box()
            if self.title:
                self.boxscr.addstr(1, 1, self.title, curses.A_BOLD)
                self.boxscr.addstr(quick_help, curses.A_STANDOUT)
                self.boxscr.addstr
            self.boxscr.refresh()
        elif self.title:
            self.boxscr.clear()
            self.boxscr.addstr(0, 0, self.title, curses.A_BOLD)
            self.boxscr.addstr(quick_help, curses.A_STANDOUT)
            self.boxscr.refresh()

    def text_init(self, text):
        """Transform text string into a list of lists of strings, wrapped to
        fit the window size. [['line 1','line 2'], ['line3','line4']] where
        each sublist is a continuous line separated by \n.  Also sets the
        dimensions of the text buffer.

        """
        t = str(text).splitlines(True)
        if self.x_scroll is False:
            # Wrap text if we're not enabling x scrolling
            self.text = [wrap(i, self.win_size_x - 1) or [" "] for i in t]
        else:
            self.text = [t]
        self.buffer_set()
        if 0 < self.max_text_size < self.num_rows:
            # Increases max_text_size if if max_text_size < num_rows
            self.max_text_size = self.num_rows

    def buffer_set(self):
        """Set variables for the text buffer.

        """
        self.max_cols = max([len(j) for i in self.text for j in i]
                            or [self.win_size_x])
        self.num_rows = sum([len(i) for i in self.text])
        self.buffer_idx_y = self.cur_pos_y + self.y_offset
        # Create an indexable list where each row of text has an index of
        # (line, row) within self.text, and the list is indexed from
        # self.buffer_idx_y. Like: [(idx_line,idx_row, row), (....)]
        self.buffer_list = []
        idx_line = 0
        for line in self.text:
            idx_row = 0
            for row in line:
                self.buffer_list.append((idx_line, idx_row, row))
                idx_row += 1
            idx_line += 1
        if not self.buffer_list:
            self.buffer_list.append((0, 0, ""))
        # buf_length = length of current line
        self.buf_length = len(self.buffer_list[self.buffer_idx_y][2])
        self.buffer_idx_x = self.cur_pos_x + self.x_offset

    def keys_init(self):
        """Define methods for each key.

        """
        self.keys = {
            curses.KEY_BACKSPACE:                self.backspace,
            curses.KEY_DOWN:                     self.down,
            curses.KEY_END:                      self.end,
            curses.KEY_ENTER:                    self.insert_line_or_quit,
            curses.KEY_HOME:                     self.home,
            curses.KEY_DC:                       self.del_char,
            curses.KEY_LEFT:                     self.left,
            curses.KEY_NPAGE:                    self.page_down,
            curses.KEY_PPAGE:                    self.page_up,
            curses.KEY_RIGHT:                    self.right,
            curses.KEY_UP:                       self.up,
            curses.KEY_F1:                       self.help,
            curses.KEY_F2:                       self.quit,
            curses.KEY_F5:                       self.quit_nosave,
            curses.KEY_RESIZE:                   self.resize,
            chr(curses.ascii.ctrl(ord('x'))):    self.quit,
            chr(curses.ascii.ctrl(ord('u'))):    self.del_to_bol,
            chr(curses.ascii.ctrl(ord('k'))):    self.del_to_eol,
            chr(curses.ascii.ctrl(ord('d'))):    self.close,
            chr(curses.ascii.DEL):               self.backspace,
            chr(curses.ascii.NL):                self.insert_line_or_quit,
            chr(curses.ascii.LF):                self.insert_line_or_quit,
            chr(curses.ascii.BS):                self.backspace,
            chr(curses.ascii.ESC):               self.quit_nosave,
            chr(curses.ascii.ETX):               self.close,
            "\n":                                self.insert_line_or_quit,
            "\t":                                self.insert_tab,
            -1:                                  self.resize,
        }

    def win_init(self):
        """Set initial editor window size parameters, and reset them if window
        is resized.

        """
        # self.cur_pos is the current y,x position of the cursor
        self.cur_pos_y = 0
        self.cur_pos_x = 0
        # y_offset controls the up-down scrolling feature, x_offset left-right
        self.y_offset = 0
        self.x_offset = 0
        # buffer_idx_y is the location of the current line within all of
        # self.text. row_idx is the position within the current line
        # line_idx is the position of the current line within self.text. So an
        # actual line of text would be self.text[line_idx][row_idx]
        self.buffer_idx_y = 0
        self.buffer_idx_x = 0
        self.line_idx = 0
        self.row_idx = 0
        # Adjust win_size if resizing
        if self.resize_flag is True:
            self.win_size_x += 1
            self.win_size_y += 1
            self.resize_flag = False
        # Make sure requested window size is < available window size
        self.max_win_size_y, self.max_win_size_x = self.scr.getmaxyx()
        # Adjust max_win_size for maximum possible offsets
        # (e.g. if there is a title and a box)
        self.max_win_size_y = max(0, self.max_win_size_y - 4)
        self.max_win_size_x = max(0, self.max_win_size_x - 3)
        # Keep the input box inside the physical window
        if (self.win_size_y > self.max_win_size_y or
                self.win_size_y < self.win_size_orig_y):
            self.win_size_y = self.max_win_size_y
        if (self.win_size_x > self.max_win_size_x or
                self.win_size_x < self.win_size_orig_x):
            self.win_size_x = self.max_win_size_x
        # Reduce win_size by 1 to account for position starting at 0 instead of
        # 1. E.g. if size=80, then the max size should be 79 (0-79).
        self.win_size_y -= 1
        self.win_size_x -= 1
        # Validate win_location settings
        if self.win_size_x + self.win_location_x >= self.max_win_size_x:
            self.win_location_x = max(0, self.max_win_size_x -
                                      self.win_size_x)
        if self.win_size_y + self.win_location_y >= self.max_win_size_y:
            self.win_location_y = max(0, self.max_win_size_y -
                                      self.win_size_y)
        # Create an extra window for the box outline and/or title, if required
        x_off = y_off = loc_off_y = loc_off_x = 0
        if self.box:
            y_off += 3
            x_off += 2
            loc_off_y += 1
            loc_off_x += 1
        if self.title:
            y_off += 1
            loc_off_y += 1
        if self.box is True or self.title:
            # Make box/title screen bigger than actual text area (stdscr)
            self.boxscr = self.scr.subwin(self.win_size_y + y_off,
                                          self.win_size_x + x_off,
                                          self.win_location_y,
                                          self.win_location_x)
            self.stdscr = self.boxscr.subwin(self.win_size_y,
                                             self.win_size_x,
                                             self.win_location_y + loc_off_y,
                                             self.win_location_x + loc_off_x)
        else:
            self.stdscr = self.scr.subwin(self.win_size_y,
                                          self.win_size_x,
                                          self.win_location_y,
                                          self.win_location_x)
        self.stdscr.keypad(1)

    def left(self):
        if self.cur_pos_x > 0:
            self.cur_pos_x = self.cur_pos_x - 1
        elif self.cur_pos_y > 0:
            self.up()
            self.cur_pos_x = self.max_cols
            self.end_of_line_check()

    def right(self):
        if self.cur_pos_x < self.buf_length:
            self.cur_pos_x = self.cur_pos_x + 1
        elif self.buffer_idx_y < self.num_rows - 1:
            self.cur_pos_x = 0
            self.down()

    def up(self):
        if self.cur_pos_y > 0:
            self.cur_pos_y -= 1
        else:
            self.y_offset = max(0, self.y_offset - 1)
        self.end_of_line_check()

    def down(self):
        if (self.cur_pos_y < self.win_size_y - 1 and
                self.buffer_idx_y < self.num_rows - 1):
            self.cur_pos_y += 1
        elif self.buffer_idx_y == self.num_rows - 1:
            return
        else:
            self.y_offset = min(self.num_rows - self.win_size_y,
                                self.y_offset + 1)
        self.end_of_line_check()

    def end(self):
        self.cur_pos_x = self.buf_length

    def home(self):
        self.cur_pos_x = 0

    def page_up(self):
        self.y_offset = max(0, self.y_offset - self.win_size_y)
        self.end_of_line_check()

    def page_down(self):
        self.y_offset = min(self.num_rows - self.win_size_y - 1,
                            self.y_offset + self.win_size_y)
        # Corrects negative offsets
        self.y_offset = max(0, self.y_offset)
        self.end_of_line_check()

    def end_of_line_check(self):
        self.buffer_set()
        if self.cur_pos_x > self.buf_length:
            self.cur_pos_x = self.buf_length

    def get_cur_word(self, text, forward=True):
        """Given a string and the direction the cursor is moving, get the
        current word to the left of the cursor using self.buffer_idx_x

        Args:
            text: string
            forward: True or False

        Returns: cur_word

        """
        text = text or ""
        if forward is True:
            idx = -1
        else:
            idx = 0
        return text[:self.buffer_idx_x].split(' ')[idx]

    def insert_char(self, c):
        """Given a curses wide character, insert that character in the current
        line. Stop when the maximum line length is reached.

        """
        # Skip non-handled special characters (get_wch returns int value for
        # certain special characters)
        if isinstance(c, int):
            return
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line) or [""]
        line.insert(self.buffer_idx_x, c)
        self.text[ln][r] = "".join(line)
        self.space_counter = len(self.text[ln][r]) - \
                             len(self.text[ln][r].rstrip()) + 1
        cur_word = self.get_cur_word(self.text[ln][r])
        self.text[ln] = wrap(" ".join(self.text[ln]), self.win_size_x - 1) or [""]
        cur_word_wrapd = self.get_cur_word(self.text[ln][r])
        if self.space_counter:
            ln, r, line = self.buffer_list[self.buffer_idx_y]
            self.text[ln][r] += " " * self.space_counter
        self.buffer_set()
        self.right()
        self.word_wrap_jump(cur_word, cur_word_wrapd)

    def word_wrap_jump(self, cur_word, cur_word_wrapd):
        # If current word is wrapped to previous or next line, move cursor.
        if cur_word != cur_word_wrapd and cur_word:
            if (self.buffer_list[self.buffer_idx_y - 1][2].endswith(cur_word) or
                    self.buffer_list[self.buffer_idx_y - 1][2].endswith(cur_word[:-1])):
                # If word is wrapped up to previous line
                self.up()
                self.end()
            elif (self.buffer_list[self.buffer_idx_y][2].startswith(cur_word) or
                    self.buffer_list[self.buffer_idx_y][2].startswith(cur_word[:-1])):
                # If word is wrapped down to next line
                self.cur_pos_x = len(cur_word) + 1

    def insert_tab(self):
        """Insert 4 spaces for a tab.

        """
        tab_size = 4
        for i in range(0, tab_size):
            self.insert_char(" ")

    def insert_line_or_quit(self):
        """Insert a new line at the cursor. Wrap text from the cursor to the
        end of the line to the next line. If the line is a single line, saves
        and exits.

        """
        if self.max_text_size == 1:
            # Save and quit for single-line entries
            return False
        if self.num_rows == self.max_text_size:
            return
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line)
        newline = line[self.cur_pos_x:]
        line = line[:self.cur_pos_x]
        oldline1 = self.text[ln][:r]
        oldline1.append("".join(line))
        oldline2 = self.text[ln][r + 1:]
        oldline2.insert(0, "".join(newline))
        del self.text[ln]
        self.text.insert(ln, oldline2)
        self.text.insert(ln, oldline1)
        self.buffer_set()
        self.cur_pos_x = 0
        self.down()

    def backspace(self):
        """Delete character under cursor and move one space left.

        """
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line)
        if self.cur_pos_x > 0:
            try:
                del line[self.buffer_idx_x - 1]
            except IndexError:
                # Catches missing whitespace due to word wrapping
                line.extend(list(" " * (self.space_counter or 1)))
                del line[self.buffer_idx_x - 1]
                self.space_counter = max(0, self.space_counter - 1)
                line = line or [" "]
            self.text[ln][r] = "".join(line)
            self.left()
        elif self.cur_pos_x == 0 and self.buffer_idx_y > 0:
            # If at BOL, move cursor to end of previous line and join the two
            # lines (unless already at top of file)
            # If current or previous line is empty, delete it
            self.left()
            self.cur_pos_x = max(0, self.cur_pos_x - 1)
            ln0, r0, line0 = self.buffer_list[self.buffer_idx_y]
            line0 = list(line0)
            if line0:
                del line0[-1]
                self.text[ln0][r0] = "".join(line0)
                if ln0 < ln:
                    self.text[ln0].extend(self.text[ln])
                    del self.text[ln]
            else:
                del self.text[ln0]
            ln = ln0
        elif self.cur_pos_x == 0 and self.buffer_idx_y == 0 and not line:
            # If at the top and the line is empty, delete it
            del self.text[ln]
            return
        cur_word = self.get_cur_word(self.text[ln][r], False)
        self.text[ln] = wrap(" ".join(self.text[ln]), self.win_size_x -1) or [""]
        try:
            cur_word_wrapd = self.get_cur_word(self.text[ln][r], False)
        except IndexError:
            cur_word_wrapd = ""
        self.buffer_set()
        self.word_wrap_jump(cur_word, cur_word_wrapd)

    def del_char(self):
        """Delete character under the cursor.

        """
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line)
        if line and self.cur_pos_x < len(line):
            del line[self.buffer_idx_x]
        self.text[ln][r] = "".join(line)
        self.text[ln] = wrap(" ".join(self.text[ln]), self.win_size_x - 1) or [""]

    def del_to_eol(self):
        """Delete from cursor to end of current line. (C-k)

        """
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line)
        line = line[:self.cur_pos_x]
        self.text[ln][r] = "".join(line)

    def del_to_bol(self):
        """Delete from cursor to beginning of current line. (C-u)

        """
        ln, r, line = self.buffer_list[self.buffer_idx_y]
        line = list(line)
        line = line[self.cur_pos_x:]
        self.text[ln][r] = "".join(line)
        self.cur_pos_x = 0

    def quit(self):
        return False

    def quit_nosave(self):
        self.text = False
        return False

    def help(self):
        """Display help text popup window.

        """
        help_txt = """
        Save and exit                               : F2 or Ctrl-x
                                       (Enter if single-line entry)
        Exit without saving                         : F5 or ESC
        Cursor movement                             : Arrow keys
        Move to beginning of line                   : Home
        Move to end of line                         : End
        Page Up/Page Down                           : PgUp/PgDn
        Backspace/Delete one char left of cursor    : Backspace
        Delete 1 char under cursor                  : Del
        Insert line at cursor                       : Enter
        Delete to end of line                       : Ctrl-k
        Delete to beginning of line                 : Ctrl-u
        Help                                        : F1
        """
        try:
            curses.curs_set(0)
        except:
            pass
        txt = help_txt.split('\n')
        lines = min(self.max_win_size_y, len(txt) + 2)
        cols = min(self.max_win_size_x, max([len(i) for i in txt]) + 2)
        # Only print help text if the window is big enough
        try:
            popup = curses.newwin(lines, cols, 0, 0)
            popup.addstr(1, 1, help_txt)
            popup.box()
        except:
            pass
        else:
            while not popup.getch():
                pass
        finally:
            # Turn back on the cursor
            if self.pw_mode is False:
                curses.curs_set(1)
            # flushinp Needed to prevent spurious F1 characters being written to line
            curses.flushinp()
            self.box_init()

    def resize(self):
        self.resize_flag = True
        self.win_init()
        self.box_init()
        self.text_init("\n".join([" ".join(i) for i in self.text]))

    def run(self):
        """Main program loop.

        """
        try:
            while True:
                self.stdscr.move(self.cur_pos_y, self.cur_pos_x)
                loop = self.get_key()
                if loop is False or loop == -1:
                    break
                self.buffer_set()
                self.display()
        except KeyboardInterrupt:
            self.close()
        return self.exit()

    def display(self):
        """Display the editor window and the current contents.

        """
        s = self.buffer_list[self.y_offset:(self.y_offset + self.win_size_y) or 1]
        for y, line in enumerate(s):
            try:
                self.stdscr.move(y, 0)
                self.stdscr.clrtoeol()
                if not self.pw_mode:
                    self.stdscr.addstr(y, 0, line[2])
                self.boxscr.addstr(0,0,"{},{},{},{}".format(self.space_counter,self.cur_pos_x, self.buffer_idx_x, self.buf_length))
                self.boxscr.clrtoeol()
            except:
                self.close()
        self.stdscr.refresh()
        if self.box:
            self.boxscr.refresh()
        self.scr.refresh()

    def exit(self):
        """Normal exit procedure.

        """
        curses.flushinp()
        try:
            curses.curs_set(0)
        except:  # If invisible cursor not supported
            pass
        curses.noecho()
        if self.text == -1:
            return -1
        elif self.text is False:
            return False
        else:
            return "\n".join([" ".join(i) for i in self.text])

    def close(self):
        """Exiting on keyboard interrupt or other curses display errors.

        """
        curses.endwin()
        self.text = -1
        return self.exit()

    def get_key(self):
        try:
            c = self.stdscr.get_wch()
        except KeyboardInterrupt:
            self.close()
        try:
            loop = self.keys[c]()
        except KeyError:
            self.insert_char(c)
            loop = True
        return loop


def main(stdscr, **kwargs):
    return Editor(stdscr, **kwargs)()


def editor(**kwargs):
    return curses.wrapper(main, **kwargs)
