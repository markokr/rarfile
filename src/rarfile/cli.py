"""Minimal command-line interface for rarfile module.
"""

import argparse

from . import RarFile

__all__ = ('main',)

def main(args):
    p = argparse.ArgumentParser(description=__doc__,
                                prog='python3 -m rarfile')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("-l", "--list", metavar="<rarfile>",
                   help="Show archive listing")
    g.add_argument("-e", "--extract", nargs=2,
                   metavar=("<rarfile>", "<output_dir>"),
                   help="Extract archive into target dir")
    g.add_argument("-t", "--test", metavar="<rarfile>",
                   help="Test if a archive is valid")
    cmd = p.parse_args(args)

    if cmd.list:
        with RarFile(cmd.list) as rf:
            rf.printdir()
    elif cmd.test:
        with RarFile(cmd.test) as rf:
            rf.testrar()
    elif cmd.extract:
        with RarFile(cmd.extract[0]) as rf:
            rf.extractall(cmd.extract[1])

