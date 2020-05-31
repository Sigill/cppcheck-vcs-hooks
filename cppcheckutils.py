import sys
import re
import editdistance
#import Levenshtein

def get_findings(iter):
  entries = []

  start_re = re.compile('^[^:]*:[0-9]+:')

  for line in iter:
    if start_re.match(line):
      entries.append(line)
    else:
      entries[-1] += '\n'
      entries[-1] += line

  return [ e.rstrip() for e in entries ]

def is_new_finding(new_finding, known_findings):
  closest_dst = 8 # Do not authorize more tha 8 editions.
  closest = None
  for known_finding in known_findings:
    dst = editdistance.distance(new_finding, known_finding)
    #dst = Levenshtein.distance(new_finding, known_finding)
    if dst < closest_dst:
      closest_dst = dst
      closest = known_finding

  return closest is None

def filter_new_findings(known_findings, new_findings):
  return [finding for finding in new_findings if is_new_finding(finding, known_findings)]

