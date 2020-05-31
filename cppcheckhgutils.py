import os, sys, re, shlex, shutil
import subprocess
from termcolor import colored
import tempfile
import multiprocessing

sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
import cppcheckutils

class MercurialCPPCheckRunner(object):
  @staticmethod
  def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

  @staticmethod
  def colorcat(color, filename):
    with open(filename, 'r') as f:
      eprint(colored(f.read(), color))

  def __print_cmd(self, *args):
    if self.verbose > 1:
      MercurialCPPCheckRunner.eprint(colored(shlex.join(args), 'blue'))

  def __execute(self, *args, out=subprocess.DEVNULL, err = subprocess.DEVNULL):
    self.__print_cmd(*args)
    return subprocess.run(args, stdout=out, stderr=err)

  def __capture(self, *args):
    return self.__execute(*args, out=subprocess.PIPE , err=subprocess.PIPE)

  def __init__(self, hg_root=os.getcwd(), **kwargs):
    self.verbose = kwargs['verbose'] if 'verbose' in kwargs else 0

    result = self.__capture('hg', '--cwd', hg_root, 'root')
    if result.returncode == 0:
      self.hg_root = result.stdout.strip().decode('utf-8')
    else:
      raise ValueError('No mercurial repository found at %s' % hg_root)

    self.cppcheckoptions = ["--enable=warning,style,performance,portability", "--language=c++", "--inconclusive"]
    self.ignore_patterns = []

  def set_ignore_patterns(self, *patterns):
    self.ignore_patterns = patterns

  def load_ignore_patterns(self, filename):
    with open(args.ignore, 'r') as f:
      self.ignore_patterns = [re.compile(line.rstrip('\n')) for line in f]

  def set_cppcheck_options(self, *args):
    self.cppcheckoptions = args

  def is_relevant(self, finding):
    return all(not p.match(finding) for p in self.ignore_patterns)

  def count_parents(self, rev):
    result = self.__capture('hg', 'log', '-R', self.hg_root, '--rev', 'parents(%s)' % rev, '--template', '{rev}\n')
    if result.returncode != 0:
      raise ValueError('Unable to find revision %s' % rev)

    lines = result.stdout.strip().decode('utf-8').split('\n')

    if len(lines) > 0 and len(lines[-1]) == 0:
      del lines[-1]

    return len(lines)

  def list_altered_files(self, range_args, untracked, files):
    result = self.__capture('hg', 'status', '-R', self.hg_root, *range_args, '-m', '-a', *(['-u'] if untracked else []), *files)
    if result.returncode != 0:
      raise ValueError('Unable to get status for %s' % range_args)

    status_re = re.compile('^([MA?])\\s*(.*\\.(?:cpp|cxx|h|hxx))$')

    altered_files = []
    for line in result.stdout.decode('utf-8').split('\n'):
      m = status_re.search(line)
      if m:
        altered_files.append((m.group(2), m.group(1)))

    return altered_files

  def run_cppcheck(self, d, f):
    cmd = ['cppcheck', '-q', *self.cppcheckoptions, '--relative-paths=%s' % d, os.path.join(d, f)]
    result = self.__capture(*cmd)

    if len(result.stderr) == 0:
      return []

    findings = cppcheckutils.get_findings(result.stderr.decode('utf-8').split('\n'))

    if len(self.ignore_patterns) == 0:
      return findings

    return [finding for finding in findings if is_relevant(finding)]

  def analyse_file(self, i, f, s, tmpdir, leftrev, rightrev, leftrev_args, rightrev_args, range_args):
    src = os.path.join(self.hg_root, f)
    if rightrev is None and not os.path.exists(src):
      eprint('%s does not exist, skipping' % src)
      return []

    fwd = os.path.join(tmpdir, str(i))
    leftd = os.path.join(fwd, 'L')
    leftf = os.path.join(leftd, f)
    rightd = os.path.join(fwd, 'R')
    rightf = os.path.join(rightd, f)

    analyse_left = leftrev is not None and s == 'M'

    if analyse_left:
      os.makedirs(os.path.dirname(leftf))
      self.__capture('hg', 'cat', '-R', self.hg_root, *leftrev_args, src, '-o', leftf)

    os.makedirs(os.path.dirname(rightf))

    if rightrev is None:
      self.__print_cmd('cp', src, rightf)
      shutil.copyfile(src, rightf)
    elif analyse_left:
      self.__print_cmd('cp', leftf, rightf)
      shutil.copyfile(leftf, rightf)
      patchfile = os.path.join(fwd, 'patchfile')
      with open(patchfile, 'w') as out:
        self.__execute('hg', 'diff', '-R', self.hg_root, '-a', *range_args, src, out=out, err=subprocess.PIPE)
      self.__capture('patch', '-us', '-p1', '--posix', '--batch', '-d', rightd, '-i', patchfile)
    else:
      self.__capture('hg', 'cat', '-R', self.hg_root, *rightrev_args, src, '-o', rightf)

    leftfindings = self.run_cppcheck(leftd, f) if os.path.exists(leftf) else []
    rightfindings = self.run_cppcheck(rightd, f) if os.path.exists(rightf) else []

    if self.verbose > 2:
      if analyse_left:
        MercurialCPPCheckRunner.colorcat(leftf, 'red')
        MercurialCPPCheckRunner.eprint(colored('\n'.join(leftfindings), 'red', attrs=['concealed']))

      MercurialCPPCheckRunner.colorcat(rightf, 'green')
      MercurialCPPCheckRunner.eprint(colored('\n'.join(rightfindings), 'green', attrs=['concealed']))

    if len(leftfindings) > 0 and len(rightfindings) > 0:
      return cppcheckutils.filter_new_findings(leftfindings, rightfindings) 
    else:
      return rightfindings

  class Worker(object):
    def __init__(self, ctx, tmpdir, leftrev, rightrev, leftrev_args, rightrev_args, range_args):
      self.ctx = ctx
      self.tmpdir = tmpdir
      self.leftrev = leftrev
      self.rightrev = rightrev
      self.leftrev_args = leftrev_args
      self.rightrev_args = rightrev_args
      self.range_args = range_args

    def __call__(self, ifs):
      i, (f, s) = ifs
      return self.ctx.analyse_file(i, f, s, self.tmpdir, self.leftrev, self.rightrev, self.leftrev_args, self.rightrev_args, self.range_args)

  def analyse(self, change=None, leftrev=None, rightrev=None, untracked=False, files=[], j=os.cpu_count(), keep=False):
    if change:
      leftrev = 'p1(%s)' % change
      rightrev = change
    else:
      leftrev = leftrev
      rightrev = rightrev

    nparents = self.count_parents(rightrev)
    if nparents != 1:
      raise ValueError('Revision %s has %d parents, skipping' % (rightrev, nparents))

    leftrev_args  = ['--rev', leftrev]  if leftrev  else []
    rightrev_args = ['--rev', rightrev] if rightrev else []

    range_args = ['--change', change] if change else leftrev_args + rightrev_args

    altered_files = self.list_altered_files(range_args, untracked, files)

    tmpdir = tempfile.mkdtemp(None, 'cppcheck.hg.')

    worker = self.Worker(self, tmpdir, leftrev, rightrev, leftrev_args, rightrev_args, range_args)

    findings = []

    if j > 1:
      pool = multiprocessing.Pool()
      findingss = pool.map(worker, enumerate(altered_files, start=1))

      findings = [finding for findings in findingss for finding in findings]
    else:
      for ifs in enumerate(altered_files, start=1):
        i, (f, s) = ifs
        if self.verbose > 0:
          MercurialCPPCheckRunner.eprint(colored("%d Running cppcheck on:  %s" % (i, f), 'blue'))

        findings.extend(worker(ifs))

    if not keep:
      shutil.rmtree(tmpdir)

    return findings

