#!/usr/bin/env python3

# vim:  ts=2 sw=2 expandtab

"""Split HASP/JES2 spool output running in MVS under a Hercules emulated
machine into individual files based on their trailing JES2 banner.

Module written November, 2016.

To use, insert into the Hercules configuration:

    000E    1403    |${HOME}/bin/spool.py

where 000E is the address of a JES2 controlled printer with separator
pages enabled.

You may also want to tune JES2 parms in SYS1.JES2PARM(JES2PARM) to set
the number of separator page lines to 1:

    &PRIDCT=1
"""

__author__ = "ahd@kew.com (Drew Derbyshire)"
__version__ = "1.1.2"

import os
import re
import sys

# pylint: disable=C0301
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..
#       ****R  START  JOB    1  AHDLSCAT  A.H.DERBYSHIRE        ROOM TSO    3.52.41 PM 18 NOV 15  PRINTER1  SYS KEWS  JOB    1  START  R****
#       ****R   END   JOB 9991  AHDLSCAT  Derbyshire-123456789  ROOM TSOX  23.52.41 PM 18 NOV 15  PRINTER1  SYS KEWS  JOB 9991   END   R****
#       ****A   END   JOB    6  MVS0080   Build Netsol          ROOM        3.57.55 PM 26 NOV 15  PRINTER1  SYS KEWS  JOB    6   END   A****
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..

_JES2_PATTERN = (
    r'\*{4,4}'                              # ****
    r'(?P<class>[A-Z0-9])'                  # sysout class
    r'  (?P<edge>START| END )'              # START/END
    r'  (?P<type>JOB|STC|TSU)'              # JOB/TSU/STC
    r' (?P<number>[ \d]{4,4})'              # job number
    r'  (?P<name>[A-Z0-9@#$ ]{8,8})'        # job name
    r'  (.{20,20})'                         # programmer name
    r'  ROOM (?P<room>[\w ]{4,4})'          # room number
    r'  [ \d]\d(?:\.\d\d){2,2} (?:A|P)M'    # time: hh:mm:ss AM/PM
    r' \d\d [A-Z]{3,3} \d\d'                # date: dd mmm yy
    r'  ([\w ]{8,8})'                       # printer name
    r'  SYS (?P<system>[\w ]{4,4})'         # system name
    r'  (?P=type)'                          # JOB/TSU/STC
    r' (?P=number)'                         # job number
    r'  (?P=edge)'                          # START/END
    r'  (?P=class)'                         # sysout class
    r'\*{4,4}'                              # ****
)
_JES2_REGEX = re.compile(_JES2_PATTERN)

# pylint: disable=C0301
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..
#       HASP-II*A*PRINTER1....START JOB    3....11.03.49 AM  3 MAR 95....ROOM     ....AHD00128....DERBYSHIRE          ....PRINTER1*A*HASP-II
#       HASP-II*A*PRINTER1......END JOB    3....11.03.49 AM  3 MAR 95....ROOM     ....AHD00128....DERBYSHIRE          ....PRINTER1*A*HASP-II
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..

_HASP_PATTERN = (
    r'HASP-II\*'                            # Literal
    r'(?P<class>[A-Z0-9])'                  # sysout class
    r'\*'                                   # Literal
    r'(?P<printer>[\w ]{8,8})'              # printer name
    r'\.{4,4}'                            # Literal
    r'(?P<edge>START|\.\.END)'              # START/END
    r' (?P<type>JOB|STC|TSU)'               # JOB/TSU/STC
    r' (?P<number>[ \d]{4,4})'              # job number
    r'\.{4,4}'                              # Literal
    r'[.\d]\d(?:\.\d\d){2,2} (?:A|P)M'    # time: hh:mm:ss AM/PM
    r' [ \d]\d [A-Z]{3,3} \d\d'                # date: dd mmm yy
    r'\.{4,4}'                              # Literal
    r'ROOM (?P<room>[\w ]{4,4})'            # room number
    r'\.{4,4}'                              # Literal
    r'(?P<name>[A-Z0-9@#$ ]{8,8})'          # job name
    r'\.{4,4}'                              # Literal
    r'(?P<pgmr>.{20,20})'                 # programmer name
    r'\.{4,4}'                              # Literal
    r'([\w ]{8,8})'                         # printer name
    r'\*'                                   # Literal
    r'(?P=class)'                           # sysout class
    r'\*HASP-II'                            # ****
)
_HASP_REGEX = re.compile(_HASP_PATTERN)

def _GetLine():
  """Read one line of sysout from the input"""
  line = ''

  while True:
    try:
      c = sys.stdin.read(1)
    except (UnicodeDecodeError) as e:
      print("Failure reading character:", str(e))
      c = '?'

    if not c:
      return line
    if c == '\r':
      c = '\n'
    line += c
    if c in ('\n', '\f'):
      return line

def _Process():
  """Main processing loop.  Never exits until program shutdown."""
  buffer = []
  eof = False
  dictionary = {}

  while True:
    line = _GetLine()

    # Handle EOF when we have data buffered
    if not line:
      if buffer:
        type = 'XXX'
        if not os.path.exists(type):
          os.makedirs(type)

        for i in range(1, 1000):
          output_name = type + '/' + 'UNKNOWN' + '.' + str(i) + '.txt'
          if not os.path.exists(output_name):
            break
        with open(output_name, 'w') as f:
          f.write(''.join(buffer))
      return

    matches = re.match(_JES2_REGEX, line.strip())
    if not matches:
      matches = re.match(_HASP_REGEX, line.strip())

    if matches:
      buffer.append(line)
      dictionary = matches.groupdict()
      eof = 'END' in dictionary['edge']
    elif dictionary and eof and line.startswith('\f'):
      output_base = '-'.join((
          dictionary['name'],
          dictionary['number'].replace(' ', '0'),
          dictionary['class'])).replace(' ', '')
      output_base = output_base.replace('$', '_').replace('/', '-')
      output_name = output_base + '.txt'

      if not os.path.exists(dictionary['type']):
        os.makedirs(dictionary['type'])

      for i in range(1, 1000):
        output_name = dictionary['type'] + '/' + output_base + '.' + str(i) + '.txt'
        if not os.path.exists(output_name):
          break
      with open(output_name, 'w') as f:
        f.write(''.join(buffer))
      print(sys.argv[0], 'Wrote', output_name, 'with', len(buffer), 'lines')
      buffer = []
      dictionary = {}
    else:
      dictionary = {}
      buffer.append(line)


def Main():
  """Main program to invoke _Process."""
  print(sys.argv[0], 'Version', __version__, 'Started ...')
  if len(sys.argv) > 1:
    os.chdir(sys.argv[1])
  else:
    os.chdir('prt')
  print('Current directory now', os.getcwd())
  _Process()
  print(sys.argv[0], 'EOF!!!')

if __name__ == '__main__':
  sys.exit(Main())
