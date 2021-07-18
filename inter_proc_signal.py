
"""Quick and dirty interprocess signaling that works on Windows and other OSs"""

import os

class win_ip_signal():
    def __init__(self, path):
        self.path = path

    def clear(self):
        """Remove the file name from the directory."""

        try:
            os.remove(self.path)
        except OSError:
            pass

    def set(self):
        open(self.path, 'w').close()

    def exists(self):
        return os.path.exists(self.path)

    def exit_if_exists(self):
        if self.exists():
            exit(1)

if __name__ == '__main__':
    p = '%%%.TESTING_win_ip_signal.%%%'
    y = win_ip_signal(p)
    y.clear()
    if y.exists():
        raise Exception("Exists after clear")
    y.set()
    if not y.exists():
        raise Exception("Doesn't exist after set")
    y.clear()
    if y.exists():
        raise Exception("Exists after clear")

