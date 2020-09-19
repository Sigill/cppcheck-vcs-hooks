# cppcheck-vcs-utils

Utilities to write VCS hooks for [cppcheck](http://cppcheck.net/).

It started with [mercurialhook](https://sourceforge.net/p/cppcheck/wiki/mercurialhook/), but quickly evolved to something new.

Required python packages (`pip install -r requirements.txt`):

- argparse
- termcolor
- [gcc-warnings](https://github.com/Sigill/gcc-warnings)

These scripts should work with most versions of Python (tested with 2.6, 2.7 and 3.x).

## cppcheck-mercurial.py

Script to run cppcheck on (commits of) a Mercurial repository.

## cppcheck-diff-findings.py

The `cppcheck-diff-findings` scripts allow to perform fuzzy analysis between two sets of cppcheck findings in order to identify new findings.

## Build & packaging

```
virtualenv venv
source venv/bin/activate

# Editable install, for development purpose
pip install -e .

# Standard install
python setup.py bdist_wheel --universal # might require pip install wheel
pip install dist/cppcheckvcsutils*.whl
```

## License

These tools are released under the terms of the MIT License. See the LICENSE.txt file for more details.
