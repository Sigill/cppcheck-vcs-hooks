#!/usr/bin/env python3

import os, sys, re, shlex
import argparse
import subprocess
from argparse import RawTextHelpFormatter
import tempfile
import shutil
from termcolor import colored
import multiprocessing

sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
import cppcheckutils

verbose=0
hg_root=None
cppcheckoptions = ["--enable=warning,style,performance,portability", "--language=c++", "--inconclusive"]

def eprint(*args, **kwargs):
  print(*args, file=sys.stderr, **kwargs)

def colorcat(color, filename):
  with open(filename, 'r') as f:
    eprint(colored(f.read(), color))

def print_cmd(*args):
  global verbose
  if verbose > 1:
    eprint(colored(shlex.join(args), 'blue'))

def execute(*args, out=subprocess.DEVNULL, err = subprocess.DEVNULL):
  print_cmd(*args)
  return subprocess.run(args, stdout=out, stderr=err)

def capture(*args):
  return execute(*args, out=subprocess.PIPE , err=subprocess.PIPE)

def match_any(s, patterns):
  return any(p.match(finding) for p in ignore_patterns)

def run_cppcheck(d, f, ignore_patterns):
  global cppcheckoptions
  cmd = ['cppcheck', '-q', *cppcheckoptions, '--relative-paths=%s' % d, os.path.join(d, f)]
  result = capture(*cmd)

  if len(result.stderr) == 0:
    return []

  findings = cppcheckutils.get_findings(result.stderr.decode('utf-8').split('\n'))

  if len(ignore_patterns) == 0:
    return findings

  return [finding for finding in findings if not match_any(finding, ignore_patterns)]


def process_file(i, f, s, tmpdir, args):
  src = os.path.join(args.hg_root, f)
  fwd = os.path.join(tmpdir, str(i))
  leftd = os.path.join(fwd, 'L')
  leftf = os.path.join(leftd, f)
  rightd = os.path.join(fwd, 'R')
  rightf = os.path.join(rightd, f)

  if args.to_rev is None and not os.path.exists(src):
    eprint('%s does not exist, skipping' % src)
    return []

  process_left = True
  if args.from_rev is None or s != 'M':
    process_left = False

  if process_left:
    os.makedirs(os.path.dirname(leftf))
    capture('hg', 'cat', '-R', args.hg_root, *args.rev1_args, src, '-o', leftf)

  os.makedirs(os.path.dirname(rightf))

  if args.to_rev is None:
    print_cmd('cp', src, rightf)
    shutil.copyfile(src, rightf)
  elif process_left:
    print_cmd('cp', leftf, rightf)
    shutil.copyfile(leftf, rightf)
    patchfile = os.path.join(fwd, 'patchfile')
    with open(patchfile, 'w') as out:
      execute('hg', 'diff', '-R', args.hg_root, '-a', *args.range_args, src, out=out, err=subprocess.PIPE)
    capture('patch', '-us', '-p1', '--posix', '--batch', '-d', rightd, '-i', patchfile)
  else:
    capture('hg', 'cat', '-R', hg_root, *args.rev2_args, src, '-o', rightf)

  leftfindings = run_cppcheck(leftd, f, args.ignore_patterns) if os.path.exists(leftf) else []
  rightfindings = run_cppcheck(rightd, f, args.ignore_patterns) if os.path.exists(rightf) else []

  if args.verbose > 2:
    if process_left:
      colorcat(leftf, 'red')
      eprint(colored('\n'.join(leftfindings), 'red', attrs=['concealed']))

    colorcat(rightf, 'green')
    eprint(colored('\n'.join(rightfindings), 'green', attrs=['concealed']))

  return cppcheckutils.filter_new_findings(leftfindings, rightfindings) if len(leftfindings) > 0 and len(rightfindings) > 0 else rightfindings


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
parser.add_argument('-k', '--keep', dest='keep',
                    help='Keep working directory')
parser.add_argument('-v', '--verbose', dest='verbose', action='count', default=0,
                    help='Verbose mode')

(args, unknown) = parser.parse_known_args()
verbose = args.verbose

if len(unknown) > 0:
  cppcheckoptions = unknown

if args.hg_root:
  result = capture('hg', '--cwd', args.hg_root, 'root')
  if (result.returncode == 0):
    hg_root = result.stdout.strip().decode('utf-8')
  else:
    eprint('No mercurial repository found at %s' % hg_root)
    sys.exit(-1)

if args.change:
  args.from_rev = 'p1(%s)' % args.change
  args.to_rev = args.change

if args.to_rev:
  result = capture('hg', 'log', '-R', hg_root, '--rev', 'parents(%s)' % args.to_rev, '--template', '{rev}\n')
  result.check_returncode()
  lines = result.stdout.strip().decode('utf-8').split('\n')
  if len(lines) > 0 and len(lines[-1]) == 0:
    del lines[-1]
  if len(lines) != 1:
    eprint('Revision %s is a merge, skipping' % args.to_rev)
    sys.exit(0)

args.rev1_args = ['--rev', args.from_rev] if args.from_rev else []
args.rev2_args = ['--rev', args.to_rev]   if args.to_rev   else []

if args.change:
  args.range_args = ['--change', args.change]
else:
  args.range_args = args.rev1_args + args.rev2_args

args.ignore_patterns = []
if args.ignore:
  with open(args.ignore, 'r') as f:
    for line in f:
      args.ignore_patterns.append(re.compile(line.rstrip('\n')))

result = capture('hg', 'status', '-R', hg_root, *args.range_args, '-m', '-a', *(['-u'] if args.untracked else []), *args.files)
result.check_returncode()
status_re = re.compile('^([MA?])\\s*(.*\\.(?:cpp|cxx|h|hxx))$')
altered_files = []
for line in result.stdout.decode('utf-8').split('\n'):
    m = status_re.search(line)
    if m:
      altered_files.append((m.group(1), m.group(2)))

tmpdir = tempfile.mkdtemp(None, 'cppcheck.hg.')

def worker(job):
  i, (s, f) = job
  return process_file(i, f, s, tmpdir, args)

pool = multiprocessing.Pool()
findingss = pool.map(worker, enumerate(altered_files, start=1))

for findings in findingss:
  for finding in findings:
    print(finding)

#findings = []
#for i, (s, file) in enumerate(altered_files, start=1):
#  if verbose > 0:
#    eprint(colored("{} Running cppcheck on:  {}".format(i, file), 'blue'))
#
#  findings.extend(process_file(i, file, s, tmpdir, args))
#
#for finding in findings:
#  print(finding)

if not args.keep:
  shutil.rmtree(tmpdir)
  pass

