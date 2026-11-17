import curses

from dustsweeper.tui import _map_key


def test_left_arrow_goes_to_parent():
    assert _map_key(curses.KEY_LEFT) == "backspace"
