#!/usr/bin/env python

"""
Script to filter already known cppcheck findings.

This script compares two set of cppcheck findings, performing fuzzy
comparisons in order to identify new findings from known findings.
"""

import sys
import cppcheckvcsutils.cppcheckutils


def read_findings(filename):
    with open(filename, 'r') as file:
        return cppcheckvcsutils.cppcheckutils.get_findings([line.rstrip('\n') for line in file])


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: %s known_findings new_findings" % sys.argv[0])
        sys.exit(-1)

    known_findings = read_findings(sys.argv[1])
    new_findings = read_findings(sys.argv[2])

    for finding in cppcheckvcsutils.cppcheckutils.filter_new_findings(known_findings, new_findings):
        print(finding)
