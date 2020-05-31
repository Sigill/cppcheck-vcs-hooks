#!/usr/bin/env python3

import os, sys
import argparse
from argparse import RawTextHelpFormatter

sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
from cppcheckhgutils import MercurialCPPCheckRunner

parser = argparse.ArgumentParser(description='Run cppcheck on the files modified between two Mercurial revisions.', formatter_class=RawTextHelpFormatter)
parser.add_argument('--from', dest='from_rev', metavar='REV',
                    help='Revision to start from (NOT inclusive, only changes\n'
                         'introduced AFTER this revision will be considered.\n'
                         'Use p1(REV) to start from the first parent.\n'
                         'See \'hg help revset\' for more details.')
parser.add_argument('--to', dest='to_rev', metavar='REV',
                    help='Last revision to consider (inclusive).')
parser.add_argument('-c', '--change', dest='change', metavar='REV',
                    help='Consider changes introduced by this revision.\n'
                         'Equivalent to --from \'p1(REV)\' --to REV.')
parser.add_argument('-f', '--file', dest='files', metavar='FILE', action='append', default=[],
                    help='File to analyse.\n'
                         'If not specified, the list of files is automatically obtained using hg status.')
parser.add_argument('-u', '--untracked', dest='untracked', action='store_true',
                    help='Include untracked files.')
parser.add_argument('--ignore', dest='ignore', metavar='FILE',
                    help='Ignore patterns.\n'
                         'The first line of each finding will be run through\n'
                         'grep -f FILE. In case of match, the finding is ignored.')
parser.add_argument('--hg', dest='hg_root', metavar='DIR', default=os.getcwd(),
                    help='Location of the mercurial repository.')
parser.add_argument('--exitcode', type=int, dest='exitcode', metavar='VALUE=0', default=0,
                    help='Exit code if findings are found.')
parser.add_argument('-k', '--keep', dest='keep', default=False,
                    help='Keep working directory')
parser.add_argument('-j', dest='j', type=int, default=os.cpu_count(),
                    help='Number of threads to use.')
parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                    help='Verbose mode')

(args, unknown) = parser.parse_known_args()
verbose = args.verbose

runner = MercurialCPPCheckRunner(args.hg_root, verbose=args.verbose)

if len(unknown) > 0:
  runner.set_cppcheck_options(*unknown)

if args.ignore:
  runner.load_ignore_patterns(args.ignore)

findings = runner.analyse(args.change, args.from_rev, args.to_rev, args.untracked, args.files, args.j, args.keep)

for finding in findings:
  print(finding)

