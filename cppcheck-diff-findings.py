#!/usr/bin/env python

"""
Script to filter already known cppcheck findings.

This script compares two set of cppcheck findings, performing fuzzy
comparisons in order to distinguish already existing and new findings.
"""

import sys
import re
import editdist

def get_findings(filename):
  entries = []

  start_re = re.compile('^[^:]*:[0-9]+:')

  with open(filename, 'r') as file:
    for line in file:
      if start_re.match(line):
        entries.append(line)
      else:
        entries[-1] += line

  return [ e.rstrip() for e in entries ]

if __name__ == '__main__':
  if len(sys.argv) != 3:
    print("Usage: {0} old_findings new_findings".format(sys.argv[0]))
    sys.exit(-1)

  original_entries = get_findings(sys.argv[1])
  newest_entries = get_findings(sys.argv[2])

  for newest_entry in newest_entries:
    closest_dst = 8 # Do not authorize more tha 8 editions.
    closest = None
    for original_entry in original_entries:
      dst = editdist.distance(newest_entry, original_entry)
      #dst = Levenshtein.distance(newest_entry, original_entry)
      if dst < closest_dst:
        closest_dst = dst
        closest = original_entry

    if closest is None:
      print(newest_entry)
