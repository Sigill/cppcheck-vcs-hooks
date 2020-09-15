#!/usr/bin/env python
import os
import sys
import tempfile
import shutil
import errno
import subprocess
from cppcheckvcsutils.cppcheckhgutils import MercurialCPPCheckRunner

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest


def run(*args):
    subprocess.check_call(args, env={'HGUSER': "John <smith@example.com>"})


class HGCPPCheck(unittest.TestCase):
    def test_something(self):
        try:
            tmp_dir = tempfile.mkdtemp()
            print(tmp_dir)
            os.chdir(tmp_dir)
            run('hg', 'init', tmp_dir)

            runner = MercurialCPPCheckRunner(tmp_dir, verbose=0)

            run('touch', 'f.cpp')
            run('hg', 'add', 'f.cpp')
            run('hg', 'commit', '-m', 'Commit 0')

            with open('f.cpp', 'w') as f:
                f.write("#include <string>\n"
                        "std::string f(const std::string s) {\n"
                        "  return s + s;\n"
                        "}\n")

            self.assertListEqual(runner.analyse(j=1),
                                 ["f.cpp:2:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                                  'std::string f(const std::string s) {\n'
                                  '                                ^'])

            with self.assertRaises(ValueError) as cm:
                # Skipped, p1(tip) does not exists
                runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip')

            self.assertEqual(str(cm.exception), "Revision tip has 0 parents, skipping")

            self.assertListEqual(runner.analyse(j=1, leftrev='p1(tip) or 0'),
                                 ["f.cpp:2:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                                  'std::string f(const std::string s) {\n'
                                  '                                ^'])

            run('hg', 'commit', '-m', 'Commit 1')

            self.assertEqual(runner.analyse(j=1), [])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip'),
                             ["f.cpp:2:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              'std::string f(const std::string s) {\n'
                              '                                ^'])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)'),
                             ["f.cpp:2:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              'std::string f(const std::string s) {\n'
                              '                                ^'])

            self.assertEqual(runner.analyse(j=1, change='tip'),
                             ["f.cpp:2:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              'std::string f(const std::string s) {\n'
                              '                                ^'])

            run('hg', 'mv', 'f.cpp', 'g.cpp')

            with open('g.cpp', 'w') as f:
                f.write("#include <string>\n"
                        "\n"
                        "std::string f(const std::string s) {\n"
                        "  try {\n"
                        "    return s + s;\n"
                        "  } catch (const std::exception ex) {\n"
                        "    throw std::runtime_error(ex.what());\n"
                        "  }\n"
                        "}\n")

            self.assertEqual(runner.analyse(j=1),
                             ["g.cpp:6:5: style: Exception should be caught by reference. [catchExceptionByValue]\n"
                              "  } catch (const std::exception ex) {\n"
                              "    ^",
                              "g.cpp:3:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              "std::string f(const std::string s) {\n"
                              "                                ^"])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)'),
                             ["g.cpp:6:5: style: Exception should be caught by reference. [catchExceptionByValue]\n"
                              "  } catch (const std::exception ex) {\n"
                              "    ^",
                              "g.cpp:3:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              "std::string f(const std::string s) {\n"
                              "                                ^"])

            run('hg', 'commit', '-m', 'Commit 2')

            self.assertEqual(runner.analyse(j=1), [])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip'),
                             ["g.cpp:6:5: style: Exception should be caught by reference. [catchExceptionByValue]\n"
                              "  } catch (const std::exception ex) {\n"
                              "    ^",
                              "g.cpp:3:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              "std::string f(const std::string s) {\n"
                              "                                ^"])

            with open('g.cpp', 'w') as f:
                f.write("#include <string>\n"
                        "\n"
                        "\n"
                        "std::string f(const std::string s) {\n"
                        "  try {\n"
                        "    return s + s;\n"
                        "  } catch (const std::exception& ex) {\n"
                        "    throw std::runtime_error(ex.what());\n"
                        "  }\n"
                        "}\n")

            self.assertEqual(runner.analyse(j=1),
                             ["g.cpp:4:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              "std::string f(const std::string s) {\n"
                              "                                ^"])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)'),
                             ["g.cpp:4:33: performance: Function parameter 's' should be passed by const reference. [passedByValue]\n"
                              "std::string f(const std::string s) {\n"
                              "                                ^"])

            run('hg', 'commit', '-m', 'Commit 3')

            self.assertEqual(runner.analyse(j=1), [])

            self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip'), [])

            run('hg', 'update', '--rev', '2')
            run('hg', 'branch', 'feature')

            with open('g.cpp', 'w') as f:
                f.write("#include <string>\n"
                        "\n"
                        "std::string f(const std::string s) {\n"
                        "  try {\n"
                        "    return s + s;\n"
                        "  } catch (const std::exception& ex) {\n"
                        "    throw std::runtime_error(ex.what());\n"
                        "  }\n"
                        "}\n"
                        "\n"
                        "std::vector<int> h(const std::vector<int> v) {\n"
                        "  return v;\n"
                        "}\n")

            run('hg', 'commit', '-m', 'Commit 2-2')

            run('hg', 'update', 'default')
            run('hg', 'merge', 'feature')
            run('hg', 'commit', '-m', 'Merge branch feature')

            self.assertEqual(runner.analyse(j=1), [])

            with self.assertRaises(ValueError) as cm:
                # Skipped, tip has more than 1 parent
                runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip')

            self.assertEqual(str(cm.exception), "Revision tip has 2 parents, skipping")

            # self.assertEqual(runner.analyse(j=1, leftrev='p1(tip)', rightrev='tip'),
            #                  ["g.cpp:12:43: performance: Function parameter 'v' should be passed by const reference. [passedByValue]\n"
            #                   'std::vector<int> h(const std::vector<int> v) {\n'
            #                   '                                          ^'])

        finally:
            try:
                shutil.rmtree(tmp_dir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise


if __name__ == '__main__':
    unittest.main()
