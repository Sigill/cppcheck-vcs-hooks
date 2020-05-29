#!/usr/bin/ruby
require 'pp'
require 'rubygems'
#require 'levenshtein'
require 'levenshtein-ffi'

def get_findings(file)
  entries = []

  path = nil
  File.readlines(file).each do |line|
    if m = /^([^:]*):([0-9]+):/.match(line)
      entries << line
    else
      entries.last << line
    end
  end

  return entries
end

# https://rosettacode.org/wiki/Levenshtein_distance
#module Levenshtein
#  def self.distance(a, b)
#    a, b = a.downcase, b.downcase
#    costs = Array(0..b.length) # i == 0
#    (1..a.length).each do |i|
#      costs[0], nw = i, i - 1  # j == 0; nw is lev(i-1, j)
#      (1..b.length).each do |j|
#        costs[j], nw = [costs[j] + 1, costs[j-1] + 1, a[i-1] == b[j-1] ? nw : nw + 1].min, costs[j]
#      end
#    end
#    costs[b.length]
#  end
#end

original_entries = get_findings(ARGV[0])
newest_entries = get_findings(ARGV[1])

newest_entries.each { |newest_entry|
  closest_dst = 8
  closest = nil
  original_entries.each { |original_entry|
    dst = Levenshtein.distance(newest_entry, original_entry)

    if !dst.nil? && dst < closest_dst
      closest_dst = dst
      closest = original_entry
    end
  }

  if closest.nil?
    puts newest_entry
  end
}
