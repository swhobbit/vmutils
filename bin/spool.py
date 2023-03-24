#!/usr/bin/env python3

#         vim:  ts=2 sw=2 expandtab

"""Split HASP/JES2 spool output running in MVS or MVT w/HASP under a
Hercules emulated machine into individual files based on their trailing
JES2 banner.

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
__version__ = "1.1.6"

from datetime import datetime
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
    r'  (?P<queue>JOB|STC|TSU)'             # JOB/TSU/STC
    r' (?P<number>[ \d]{4,4})'              # job number
    r'  (?P<jobname>[A-Z0-9@#$ ]{8,8})'     # job name
    r'  (.{20,20})'                         # programmer name
    r'  ROOM (?P<room>[\w ]{4,4})'          # room number
    r'  [ \d]\d(?:\.\d\d){2,2} (?:A|P)M'    # time: hh:mm:ss AM/PM
    r' \d\d [A-Z]{3,3} \d\d'                # date: dd mmm yy
    r'  ([\w ]{8,8})'                       # printer name
    r'  SYS (?P<node>[\w ]{4,4})'           # system SMF name
    r'  (?P=queue)'                         # JOB/TSU/STC
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
    r'\.{4,4}'                              # Literal
    r'(?P<edge>START|\.\.END)'              # START/END
    r' (?P<queue>JOB|STC|TSU)'              # JOB/TSU/STC
    r' (?P<number>[ \d]{4,4})'              # job number
    r'\.{4,4}'                              # Literal
    r'[.\d]\d(?:\.\d\d){2,2} (?:A|P)M'      # time: hh:mm:ss AM/PM
    r' [ \d]\d [A-Z]{3,3} \d\d'             # date: dd mmm yy
    r'\.{4,4}'                              # Literal
    r'ROOM (?P<room>[\w ]{4,4})'            # room number
    r'\.{4,4}'                              # Literal
    r'(?P<jobname>[A-Z0-9@#$ ]{8,8})'       # job name
    r'\.{4,4}'                              # Literal
    r'(?P<pgmr>.{20,20})'                   # programmer name
    r'\.{4,4}'                              # Literal
    r'([\w ]{8,8})'                         # printer name
    r'\*'                                   # Literal
    r'(?P=class)'                           # sysout class
    r'\*HASP-II'                            # ****
)
_HASP_REGEX = re.compile(_HASP_PATTERN)

# pylint: disable=C0301
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..
#       ***********A  START   G02VSCPY   SYS SYSA   WTR 00E   07:38:43 PM  28 AUG 1978   WTR 00E   SYS SYSA   G02VSCPY   START  A***********
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..

_WTR_PATTERN = (
    r'\*{11,11}'                            # Literal
    r'(?P<class>[A-Z0-9])'                  # sysout class
    r'  '                                   # Literal
    r'(?P<edge>START|\.\.END)'              # START/END
    r'   '                                  # Literal
    r'(?P<jobname>[A-Z0-9@#$ ]{8,8})'       # job name
    r'   SYS '                              # Literal
    r'(?P<node>[ \w]{4,4})'                 # system SMF id
    r'   '                                  # Literal
    r'(?P<queue>WTR|JOB|STC|TSU)'           # WTR JOB/TSU/STC
    r' (?P<printer>[\w ]{3,3})'             # printer address (name)
    r'   '                                  # Literal
    r'[ \d]\d(:\d\d){2,2} (?:A|P)M'         # time: hh:mm:ss AM/PM
    r'  '                                   # Literal
    r'[ \d]\d [A-Z]{3,3} \d{4,4}'           # date: dd mmm yyyy
    r'   '                                  # Literal
    r'(?P=queue)'                           # WTR
    r' (?P=printer)'                        # printer address (name)
    r'   SYS '                              # Literal
    r'(?P=node)'                            # system SMF id
    r'   '                                  # Literal
    r'(?P=jobname)'                         # job name
    r'   '                                  # Literal
    r'(?P=edge)'                            # START/END
    r'  '                                   # Literal
    r'(?P=class)'                           # sysout class
    r'\*{11,11}'                            # Literal
)
_WTR_REGEX = re.compile(_WTR_PATTERN)

# pylint: disable=C0301
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..#
#       //INIT     JOB MSGLEVEL=1
#       ....+....1....+....2....+....3....+....4....+....5....+....6....+....7....+....8....+....9....+....*....+....1....+....2....+....3..

_NOBANNER_PATTERN = (
    r'(//|IEF452I )(?P<jobname>[A-Z0-9@#$]+)' # jobname or failure of some job
    r' +JOB '                                # it's a JOB statement
#   r'.*(MSGCLASS=(?P<class>[A-Z0-9]))?'     # which MAYBE has a class
    r'.*'                                    # Unparsed trailing
)
_NOBANNER_REGEX = re.compile(_NOBANNER_PATTERN)

def _GetLine():
  """Read one line of sysout from the input"""
  line = ''

  while True:
    try:
      c = sys.stdin.read(1)
    except (KeyboardInterrupt) as e:
      print("Interrupt:", str(e), file=sys.stderr)
      sys.stderr.flush()
      # Try again recursively.
      return _GetLine()
    except (UnicodeDecodeError) as e:
      print("Failure reading character:", str(e), file=sys.stderr)
      sys.stderr.flush()
      c = '?'

    if not c:
      return line
    if c == '\r':
      c = '\n'
    line += c
    if c in ('\n', '\f'):
      return line

def _OpenFile(dictionary, sequence, lines_in):
  """Open a new spool based on provided job information."""
  if not dictionary:
    # Fake job information since none provided
    current = datetime.now()
    dictionary['jobname'] = 'X' + current.strftime('%j%H%M')

  for (key, values) in (('node', (os.getenv('HERCULES_NAME'), 'nonet')),
                        ('class', ('Y',)),
                        ('queue', ('noqueue',)),
                        ('number', (str(sequence),))):
    for value in values:
      if value and not key in dictionary:
        dictionary[key] = value

  if not os.path.exists(dictionary['queue']):
    os.makedirs(dictionary['queue'])

  output_base = ''.join((
      dictionary['jobname'].replace('$', '_').replace('/', '-'),
      '.',
      'listing',
      '-',
      dictionary['node'],
      '-',
      dictionary['number'].replace(' ', '0'),
      '-',
      dictionary['class'])).replace(' ', '')

  output_base = '/'.join((dictionary['queue'], output_base))

  output_name = output_base
  for i in range(1, 1000):
    if not os.path.exists(output_name):
      break
    output_name = output_base + '-' + str(i)

  print('Opening output file', output_name,
        'after', lines_in or 'no', 'lines read',
         file=sys.stderr)
  sys.stderr.flush()
  return open(output_name, 'w')

def _CloseFile(file_handle, lines_out, lines_in):
  """Close a file handle if needed."""
  if file_handle:
    print('Closing output file with',
          lines_out or "no", 'lines written (input had',
          lines_in or "no", "total lines in)",
          file=sys.stderr)
    sys.stderr.flush()
    file_handle.close()

def _ScanForBanner(line, new_page, last_regex):
  """Scan current line for a banner text."""
  if not line.strip():
    return (None, last_regex)

  regex_list = [_JES2_REGEX, _HASP_REGEX, _WTR_REGEX]

  # Only search for the raw JCL starting a job if starting a page AND
  # we not yet seen a real banner page.
  if new_page and last_regex is _NOBANNER_REGEX:
    regex_list.append(last_regex)

  for regex in regex_list:
    matches = re.match(regex, line.strip())
    if matches:
      dictionary = matches.groupdict()
      return (dictionary, regex)

  return (None, last_regex)


def _Process():
  """Main processing loop.  Never exits until program shutdown."""
  page_buffer = []
  banner_page = False
  new_page = False
  form_feed = False
  file_handle = None
  lines_out = 0
  lines_in = 0
  line = True

  last_regex = _NOBANNER_REGEX
  sequence = 10000

  while line:
    line = _GetLine()
    new_page = form_feed
    form_feed = '\f' in line

    # At EOF, write any current page (unless a banner page) and exit
    if not line:
      if page_buffer and not banner_page:
        if not file_handle:
          file_handle = _OpenFile({}, sequence + 1, lines_in)
        file_handle.write(''.join(page_buffer))
        _CloseFile(file_handle, lines_out, lines_in)
        lines_out = 0
      return

    lines_in += 1
    lines_out += 1

    #  print/flush any previous page when we see top of form
    if '\f' in line and (page_buffer and page_buffer != ['\n']):
      if banner_page:
        # We flush (not print) banner pages
        banner_page = False
      else:
        if not file_handle:
          # If input did not start with a banner page, we need to
          # open an anonymous file now that we have the first page
          print('New file for:\n', '->'.join(page_buffer), file=sys.stderr)
          sys.stderr.flush()
          sequence = sequence + 1
          file_handle = _OpenFile({}, sequence, lines_in)

        file_handle.write(''.join(page_buffer))
        file_handle.flush()

      # Having printed/discarded the previous page, start a new one
      page_buffer = []

    page_buffer.append(line)

    # Look for a banner which starts end a new file.
    if not banner_page:
      (dictionary, last_regex) = _ScanForBanner(line, new_page, last_regex)

      if dictionary:
        # If a match, we have a banner page which may need a new file
        banner_page = 'edge' in dictionary
        _CloseFile(file_handle, lines_out, lines_in)
        lines_out = 0
        file_handle = None

        # We only open files for START banner pages; at the end of jobs,
        # we ignore it, having already closed the file.
        if not banner_page or 'END' not in dictionary['edge']:
          sequence += 1
          file_handle = _OpenFile(dictionary, sequence, lines_in)
          dictionary = None

def Main():
  """Main program to invoke _Process."""
  print(sys.argv[0], 'Version', __version__, 'Started ...', file=sys.stderr)
  sys.stderr.flush()
  if len(sys.argv) > 1:
    os.chdir(sys.argv[1])
  else:
    os.chdir('prt')
  print('Current directory now', os.getcwd(), file=sys.stderr)
  sys.stderr.flush()
  _Process()
  print(sys.argv[0], '\nEOF!\n', file=sys.stderr)
  sys.stderr.flush()

if __name__ == '__main__':
  sys.exit(Main())
