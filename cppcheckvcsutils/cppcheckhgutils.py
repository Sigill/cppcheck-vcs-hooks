from __future__ import print_function
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
from termcolor import colored
import cppcheckvcsutils.cppcheckutils

if sys.version_info >= (3, 8):
    import shlex

    def join_args(args):
        return shlex.join(args)
else:
    import pipes

    def join_args(args):
        return " ".join(pipes.quote(a) for a in args)


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
        return self.ctx.analyse_file(i, f, s, self.tmpdir, self.leftrev, self.rightrev, self.leftrev_args,
                                     self.rightrev_args, self.range_args)


class MercurialCPPCheckRunner(object):
    @staticmethod
    def eprint(*args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    @staticmethod
    def colorcat(color, filename):
        with open(filename, 'r') as f:
            MercurialCPPCheckRunner.eprint(colored(f.read(), color))

    def __print_cmd(self, args):
        if self.verbose > 1:
            MercurialCPPCheckRunner.eprint(colored(join_args(args), 'blue'))

    def __execute(self, args, stdout=None, stderr=None):
        self.__print_cmd(args)
        p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
        (out, err) = p.communicate()
        return p.returncode, out, err

    def __capture(self, args):
        return self.__execute(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def __init__(self, hg_root=os.getcwd(), **kwargs):
        self.verbose = kwargs['verbose'] if 'verbose' in kwargs else 0

        result = self.__capture(['hg', '--cwd', hg_root, 'root'])
        if result[0] == 0:
            self.hg_root = result[1].strip().decode('utf-8')
        else:
            raise ValueError('No mercurial repository found at %s' % hg_root)

        self.cppcheckoptions = ["--enable=warning,style,performance,portability", "--language=c++", "--inconclusive"]
        self.ignore_patterns = []

    def set_ignore_patterns(self, *patterns):
        self.ignore_patterns = patterns

    def load_ignore_patterns(self, filename):
        with open(filename, 'r') as f:
            self.ignore_patterns = [re.compile(line.rstrip('\n')) for line in f]

    def set_cppcheck_options(self, *args):
        self.cppcheckoptions = args

    def is_relevant(self, finding):
        return not any(p.search(finding) for p in self.ignore_patterns)

    def count_parents(self, rev):
        result = self.__capture(
            ['hg', 'log', '-R', self.hg_root, '--rev', 'parents(%s)' % rev, '--template', '{rev}\n'])
        if result[0] != 0:
            raise ValueError('Unable to find revision %s' % rev)

        lines = result[1].strip().decode('utf-8').split('\n')

        if len(lines) > 0 and len(lines[-1]) == 0:
            del lines[-1]

        return len(lines)

    def list_altered_files(self, range_args, untracked, files):
        cmd = ['hg', 'status', '-R', self.hg_root, '-m', '-a']
        if untracked:
            cmd.append('-u')
        cmd.extend(range_args)
        cmd.extend(files)

        result = self.__capture(cmd)
        if result[0] != 0:
            raise ValueError('Unable to get status for %s' % range_args)

        status_re = re.compile('^([MA?])\\s*(.*\\.(?:cpp|cxx|h|hxx))$')

        altered_files = []
        for line in result[1].decode('utf-8').split('\n'):
            m = status_re.search(line)
            if m:
                altered_files.append((m.group(2), m.group(1)))

        return altered_files

    def run_cppcheck(self, d, f):
        cmd = ['cppcheck', '-q', '--relative-paths=%s' % d]
        cmd.extend(self.cppcheckoptions)
        cmd.append(os.path.join(d, f))

        result = self.__capture(cmd)

        if len(result[2]) == 0:
            return []

        findings = cppcheckvcsutils.cppcheckutils.get_findings(result[2].decode('utf-8').split('\n'))

        if len(self.ignore_patterns) == 0:
            return findings

        return [finding for finding in findings if self.is_relevant(finding)]

    def analyse_file(self, i, f, s, tmpdir, leftrev, rightrev, leftrev_args, rightrev_args, range_args):
        src = os.path.join(self.hg_root, f)
        if rightrev is None and not os.path.exists(src):
            MercurialCPPCheckRunner.eprint('%s does not exist, skipping' % src)
            return []

        fwd = os.path.join(tmpdir, str(i))
        leftd = os.path.join(fwd, 'L')
        leftf = os.path.join(leftd, f)
        rightd = os.path.join(fwd, 'R')
        rightf = os.path.join(rightd, f)

        analyse_left = leftrev is not None and s == 'M'

        if analyse_left:
            os.makedirs(os.path.dirname(leftf))
            cmd = ['hg', 'cat', '-R', self.hg_root]
            cmd.extend(leftrev_args)
            cmd.extend([src, '-o', leftf])
            self.__capture(cmd)

        os.makedirs(os.path.dirname(rightf))

        if rightrev is None:
            self.__print_cmd(['cp', src, rightf])
            shutil.copyfile(src, rightf)
        elif analyse_left:
            self.__print_cmd(['cp', leftf, rightf])
            shutil.copyfile(leftf, rightf)
            patchfile = os.path.join(fwd, 'patchfile')
            with open(patchfile, 'w') as out:
                cmd = ['hg', 'diff', '-R', self.hg_root, '-a']
                cmd.extend(range_args)
                cmd.append(src)

                self.__execute(cmd, stdout=out, stderr=subprocess.PIPE)
            self.__capture(['patch', '-us', '-p1', '--posix', '--batch', '-d', rightd, '-i', patchfile])
        else:
            cmd = ['hg', 'cat', '-R', self.hg_root]
            cmd.extend(rightrev_args)
            cmd.extend([src, '-o', rightf])

            self.__capture(cmd)

        leftfindings = self.run_cppcheck(leftd, f) if os.path.exists(leftf) else []
        rightfindings = self.run_cppcheck(rightd, f) if os.path.exists(rightf) else []

        if self.verbose > 2:
            if analyse_left:
                MercurialCPPCheckRunner.colorcat(leftf, 'red')
                MercurialCPPCheckRunner.eprint(colored('\n'.join(leftfindings), 'red', attrs=['concealed']))

            MercurialCPPCheckRunner.colorcat(rightf, 'green')
            MercurialCPPCheckRunner.eprint(colored('\n'.join(rightfindings), 'green', attrs=['concealed']))

        if len(leftfindings) > 0 and len(rightfindings) > 0:
            return cppcheckvcsutils.cppcheckutils.filter_new_findings(leftfindings, rightfindings)
        else:
            return rightfindings

    def analyse(self, change=None, leftrev=None, rightrev=None, untracked=False, files=[],
                j=multiprocessing.cpu_count(), keep=False):
        if change:
            leftrev = 'p1(%s)' % change
            rightrev = change
        else:
            leftrev = leftrev
            rightrev = rightrev

        if rightrev:
            nparents = self.count_parents(rightrev)
            if nparents != 1:
                raise ValueError('Revision %s has %d parents, skipping' % (rightrev, nparents))

        leftrev_args = ['--rev', leftrev] if leftrev else []
        rightrev_args = ['--rev', rightrev] if rightrev else []

        range_args = ['--change', change] if change else leftrev_args + rightrev_args

        altered_files = self.list_altered_files(range_args, untracked, files)

        tmpdir = tempfile.mkdtemp('', 'cppcheck.hg.')

        worker = Worker(self, tmpdir, leftrev, rightrev, leftrev_args, rightrev_args, range_args)

        findings = []

        if j > 1:
            pool = multiprocessing.Pool()
            files_findings = pool.map(worker, enumerate(altered_files, start=1))

            findings = [finding for file_findings in files_findings for finding in file_findings]
        else:
            for ifs in enumerate(altered_files, start=1):
                i, (f, s) = ifs
                if self.verbose > 0:
                    MercurialCPPCheckRunner.eprint(colored("%d Running cppcheck on:  %s" % (i, f), 'blue'))

                findings.extend(worker(ifs))

        if not keep:
            shutil.rmtree(tmpdir)

        return findings
