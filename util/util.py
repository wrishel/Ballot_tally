"""Common definitions and functions around compressed3"""
import GLB_globs
GLB = GLB_globs.GLB_globs()


def oxford_series(strings):
    """Punctuate the list of strings as a series with the Oxford comma."""

    l = len(strings)
    if l == 0:
        return ''
    elif l == 1:
        return strings[0]
    elif l == 2:
        return ' and '.join(strings)
    else:
        r = ', '.join(strings[0:-1])
        r += ', and ' + strings[-1]
    return r


def divz(n: float, d: float) -> float:
    return 0 if d == 0 else n / d

def path_to_image(root_dir, imgnum):
    return "%s/%03d/%06d.jpg" % (root_dir, imgnum / 1000, imgnum)

class Kwarg_handler():
    """Create an object with attributes that represent kwargs values."""

    def __init__(self, argnames, kwargs, required_args=None):
        error_list = [kw for kw in kwargs.keys() if kw not in argnames]
        if len(error_list) > 0:
            raise ValueError('Invalid keywords: ' + error_list.join(', '))

        if required_args is not None:
            error_list = [kw for kw in required_args if kw not in kwargs]
            if len(error_list) > 0:
                raise ValueError('Missing keywords: ' + error_list.join(', '))

        for arg in kwargs.keys():
            setattr(self, arg, kwargs[arg])


def concise_pairs(items):
    """Reorganize the sorted list of integers into a concise format."""

    def format_range(bottom, top):
        if bottom == top: return (bottom,)
        else: return bottom, top

    l = list()
    bottom = items[0]
    last_seen = bottom
    for i in range(1, len(items)):
        if items[i] == last_seen + 1:
            last_seen = items[i]
            continue
        else:
            l.append(format_range(bottom, last_seen))
            bottom = last_seen = items[i]
    l.append(format_range(bottom, last_seen))
    return l

def report(title, items):
    """Report a list from concise_pairs"""

    if len(items) > 0:
        print (title)
        for item in items:
            if len(item) == 1:
                print ("%06d" % item[0])
            else:
                print ("%06d - %06d" % item)

def report_quantities(title, items):
    """Report a list from concise_pairs"""

    s = ''
    if len(items) > 0:
        s = f"{title}\n"
        for item in items:
            if len(item) == 1:
                s += "%06d           %6d\n" % (item[0], 1)
            else:
                s += "%06d - %06d  %6d\n" % (item[0], item[1], item[1] - item[0] + 1)

    return s


def open_scratch(name, mode='r'):
    return open(GLB.path_to_scratches / name, mode)


if __name__ == '__main__':
    x = [1, 2, 3, 5, 6, 7, 9, 11, 12, 15]
    assert concise_pairs(x) == [(1, 3), (5, 7), (9,), (11, 12), (15,)]

    s =    '\n'.join(["rq",
        "000001 - 000003       3",
        "000005 - 000007       3",
        "000009                1",
        "000011 - 000012       2",
        "000015                1"])
    s += '\n'
    assert report_quantities("rq", concise_pairs(x)) == s

    with open(open_scratch('scratch.txt')):
        pass

