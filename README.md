# cppcheck-vcs-utils

Utilities to write VCS hooks for [cppcheck](http://cppcheck.net/).

It started with the [mercurialhook](https://sourceforge.net/p/cppcheck/wiki/mercurialhook/), but quickly evolved to something new.

Required python packages:

- termcolor
- editdistance

## cppcheck-mercurial.py

Script to run cppcheck on a Mercurial repository.

## cppcheck-diff-findings.py

The `cppcheck-diff-findings` scripts allow to perform fuzzy analysis between two sets of cppcheck findings in order to identify new findings.

## License

These tools are released under the terms of the MIT License. See the LICENSE.txt file for more details.
