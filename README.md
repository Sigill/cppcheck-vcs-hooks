# cppcheck-vcs-utils

Utilities to write VCS hooks for [cppcheck](http://cppcheck.net/).

It started with the [mercurialhook](https://sourceforge.net/p/cppcheck/wiki/mercurialhook/), but quickly evolved to something new.

## cppcheck-mercurial.sh

Script to run cppcheck on a Mercurial repository.

## cppcheck-diff-findings

The `cppcheck-diff-findings` scripts allow to perform fuzzy analysis between two sets of cppcheck findings in order to identify new findings.

### Python version

The Python version requires `editdist` module:

```
pip install editdist
or
yum install python-editdist
```

The `Levenshtein` module can also be used instead (you'll have to modify the script for that).

### Ruby version

The Ruby version requires the `levenshtein-ffi` module:

```
gem install levenshtein-ffi
```

The `levenshtein` module can also be used instead (you'll have to modify the script for that).
Be aware that it is quite slower.

## License

These tools are released under the terms of the MIT License. See the LICENSE.txt file for more details.
