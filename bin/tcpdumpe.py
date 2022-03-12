#!/usr/bin/env python3

# vim: expandtab sw=2 ts=2

"""tcpdumpe.py -- dump tcpdump with cheat block in EBCDIC"""

import re
import subprocess
import sys

__author__ = 'ahd@kew.com (Drew Derbyshire)'

__version__ = '1.0.2'

def _Dump(table):
  """Execute tcpdump and process the output."""
  argv = list(sys.argv)
  argv[0] = 'tcpdump'
  print(' '.join(argv))
  # <tab>       0x0000:  3333 0000 0001 dca6 3202 5864 86dd 600a
  regex = re.compile(
      r'\s+0x[0123456789abcdef]+:\s+(([0123456789abcdef]+( |$))+)')

  proc = subprocess.Popen(argv,
                          bufsize=1,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          universal_newlines=True)
  for data in proc.stdout:
    match = regex.match(data)
    if match:
      print("{:67}".format(data.rstrip()), end='')
      digits = match.group(1).replace(' ', '')
      print('\t', end='', sep='')
      for i in range(0, len(digits), 2):
        byte = digits[i:i+2]
        byte = table[int(byte, 16)]
        print(byte, sep='', end='')
      print()
    else:
      print(data)

def _MakeTranslateTable():
  """Build an ASCII to EBCDIC translation table."""
  result = 256 * ['.']
  translate_map = {
      'a':0x81,
      'b':0x82,
      'c':0x83,
      'd':0x84,
      'e':0x85,
      'f':0x86,
      'g':0x87,
      'h':0x88,
      'i':0x89,
      'j':0x91,
      'k':0x92,
      'l':0x93,
      'm':0x94,
      'n':0x95,
      'o':0x96,
      'p':0x97,
      'q':0x98,
      'r':0x99,
      's':0xA2,
      't':0xA3,
      'u':0xA4,
      'v':0xA5,
      'w':0xA6,
      'x':0xA7,
      'y':0xA8,
      'z':0xA9,
      'A':0xC1,
      'B':0xC2,
      'C':0xC3,
      'D':0xC4,
      'E':0xC5,
      'F':0xC6,
      'G':0xC7,
      'H':0xC8,
      'I':0xC9,
      'J':0xD1,
      'K':0xD2,
      'L':0xD3,
      'M':0xD4,
      'N':0xD5,
      'O':0xD6,
      'P':0xD7,
      'Q':0xD8,
      'R':0xD9,
      'S':0xE2,
      'T':0xE3,
      'U':0xE4,
      'V':0xE5,
      'W':0xE6,
      'X':0xE7,
      'Y':0xE8,
      'Z':0xE9,
      '0':0xF0,
      '1':0xF1,
      '2':0xF2,
      '3':0xF3,
      '4':0xF4,
      '5':0xF5,
      '6':0xF6,
      '7':0xF7,
      '8':0xF8,
      '9':0xF9,
      '`':0x79,
      '-':0x60,
      '=':0x7E,
      '~':0xA1,
      '!':0x5A,
      '@':0x7C,
      '#':0x7B,
      '$':0x5B,
      '%':0x6C,
      chr(170):0x5F,                  # really, logical not
      '&':0x50,
      '*':0x5C,
      '(':0x4D,
      ')':0x5D,
      '_':0x6D,
      '+':0x4E,
      '[':0xAD,
      ']':0xBD,
      '\\':0xE0,
      '{':0xC0,
      '}':0xD0,
      '|':0x4F,
      ';':0x5E,
      "'":0x7D,
      ':':0x7A,
      '"':0x7F,
      ',':0x6B,
      '.':0x4B,
      '/':0x61,
      '<':0x4C,
      '>':0x6E,
      '?':0x6F,
      ' ':0x40,
      u'¬':0x5F,                              # '¬' is Unicode
  }
  for key, value in translate_map.items():
    # result[ord(key)] = chr(value)
    result[value] = key
  return ''.join(result)

def _Main():
  """Main program."""
  _Dump(_MakeTranslateTable())
  sys.exit(0)

if __name__ == '__main__':
  _Main()
