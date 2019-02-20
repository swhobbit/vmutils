#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""Send file(s) to a VM user via the VM read or via UFT/SIFT"""

import argparse
import getpass
import httplib
from os import path
import socket
import sys
import time

__author__ = 'ahd@kew.com (Andrew H. Derbyshire)'
__copyright__ = ('Copyright 2018-2019 by Kendra Electronic Wonderworks.  '
                 'All commerical rights reserved.')
__version__ = '1.1.0'

TRANSLATE_TABLE = None

def _ParseCommandLine(command_line):
  """Parse program arguments"""

  def _PositiveInteger(value):
    """Convert passed value to an integer and verify it is a positive value."""
    ivalue = int(value)
    if ivalue <= 0:
      raise argparse.ArgumentTypeError(
          '%s is an invalid positive int value' % value)
    return ivalue

  parser = argparse.ArgumentParser(
      description='Transmit one or more files to a user on VM either via '
      'a networked emulated system reader (the default) or '
      'via the Sender-Initiated/Unsolicited File Transfer (SIFT/UFT) '
      'protocol as (incompletely) defined in RFC 1440.',
      version=__version__,
      epilog=__copyright__
  )
  parser.add_argument(
      '-l',
      '--login',
      default=str.upper(getpass.getuser()),
      help='VM user login id to send file(s) to '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-H',
      '--host',
      default='hercules',
      help='The hostname of the server to submit file(s) to '
      '(Default: %(default)s)',
      type=socket.gethostbyname,
  )
  parser.add_argument(
      '-u',
      '--uft_host',
      default=argparse.SUPPRESS,
      metavar='VM_HOST',
      help='Request the file(s) be sent using the UFT protocol, '
      'specifying hostname of the UTF server '
      'to send the file(s) via',
      type=str.upper,
  )
  parser.add_argument(
      '-e',
      '--ebcdic',
      default=False,
      action='store_true',
      help='Transmit the file(s) which are already in EBCDIC, '
      'using the EBCDIC port or UTF mode E as requested '
      '(generated header records are translated to EBCDIC as required) '
      '(Default: %(default)s, except for files of type VMARC, '
      'which are always in EBCDIC)',
  )
  parser.add_argument(
      '-p',
      '--port_ascii',
      default=3505,
      metavar='APORT',
      help='Port number of reader on host for ASCII files '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  parser.add_argument(
      '-P',
      '--port_ebcdic',
      metavar='EPORT',
      default=2540,
      help='Port number of reader on host for EBCDIC files '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  parser.add_argument(
      '-U',
      '--port_uft',
      metavar='UPORT',
      default=608,
      help='Port number to send UTF/SIFT files via '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )

  parser.add_argument(
      '-t',
      '--filetype_default',
      metavar='FT',
      default='DATA',
      help='Filetype to add to the name on VM '
      'if the local file(s) name have no usable extension '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-m',
      '--filemode',
      default='A1',
      metavar='FM',
      help='Filemode (class) to spool file(s) as '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-s',
      '--sleep',
      metavar='SECONDS',
      default=1,
      help='Interval in seconds to sleep between file submissions. '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  parser.add_argument(
      'file',
      nargs='+',
      help='File(s) to send to VM',
      type=argparse.FileType('r'),
  )
  return parser.parse_args(command_line)


def _Expect(network_socket, prompt, expected):
  """Write single line to the UFT server and look for the expected response"""
  if prompt:
    network_socket.sendall(prompt + "\r\n")
    print "Sent:", prompt

  if expected:
    expected = str(expected)
    actual = network_socket.recv(512)
    if expected and not actual.startswith(expected):
      raise httplib.BadStatusLine(
          '\nSent: {:s},\nExpected: {:s},\nReceived: {:s}'.format(prompt,
                                                                  expected,
                                                                  actual))
  return

def _UftPrologue(login,              # pylint: disable=R0913
                 hostname,
                 fname,
                 ftype,
                 fmode,
                 length,
                 date,
                 is_ebcdic,
                 network_socket):
  """Generate commands which prefix a single UFT submission"""
  _Expect(network_socket, None, "220")
  _Expect(network_socket,
          "FILE {:d} {:s}".format(length,
                                  str.upper(getpass.getuser())),
          httplib.CREATED)
  _Expect(network_socket,
          "USER {:s}@{:s}".format(login, hostname),
          httplib.CREATED)

  if is_ebcdic:
    _Expect(network_socket, 'TYPE F 80', httplib.CREATED)
  else:
    _Expect(network_socket, 'TYPE A', httplib.CREATED)

  _Expect(network_socket,
          'NAME {:s}.{:s}'.format(fname, ftype),
          httplib.CREATED)
  _Expect(network_socket, 'DATE {:s}'.format(date), httplib.CREATED)
  _Expect(network_socket, 'DATA {:d}'.format(length), httplib.CREATED)
  return


def _ReaderPrologue(login,
                    fname,
                    ftype,
                    fmode,
                    date,
                    is_ebcdic,
                    network_socket):
  """Generate Header records for a submission to the VM reader"""
  id_card = 'USERID {:8s} CLASS {:1s} NAME {:8s} {:2s}'.format(
      login,
      fmode[0:1],
      fname[0:8],
      ftype[0:8])
  # :READ  PROFILE  EXEC     A1 AHD191 03/18/18 16:18:44
  read_card = ':READ {:8s} {:8s} {:2s} {:6s} {:17s}'.format(
      fname[0:8],
      ftype[0:8],
      'filemode'[0:2],
      socket.gethostname().upper().split('.')[0][0:6],
      date,
      )
  print id_card

  if is_ebcdic:
    id_card = "{:80}".format(id_card).translate(TRANSLATE_TABLE)
    read_card = "{:80}".format(read_card).translate(TRANSLATE_TABLE)
  else:
    id_card += '\n'
    read_card += '\n'

  network_socket.sendall(id_card)
  network_socket.sendall(read_card)
  return


def _ProcessFile(file_handle, keyword_arguments):   # pylint: disable=R0914
  """Send a single file to VM."""
  full_name = path.abspath(path.expanduser(file_handle.name))
  file_name = path.basename(full_name)
  date = time.strftime('%D %T', time.localtime(path.getmtime(full_name)))
  length = path.getsize(full_name)

  vm_file_name = file_name.strip().strip('.').replace('_',
                                                      '$').upper().split('.')
  fname = vm_file_name[0]
  if len(vm_file_name) == 1:
    ftype = keyword_arguments['filetype_default']
  else:
    ftype = vm_file_name[1][0:8]
  fmode = keyword_arguments['filemode'][0:2]

  is_ebcdic = keyword_arguments['ebcdic'] or ftype == 'VMARC'
  is_uft = 'uft_host' in keyword_arguments

  if is_ebcdic and length % 80:
    error = 'Length of file {:s} is not a multiple of 80, it is {:d}'.format(
        full_name, length)
    raise RuntimeError(error)

  if is_ebcdic:
    port = keyword_arguments['port_ebcdic']
  else:
    port = keyword_arguments['port_ascii']

  data_buffer = file_handle.read()
  file_handle.close()

  # Insure the file ends with a new line, unless it was completely empty
  if (not is_ebcdic and data_buffer and data_buffer[-1] != '\n'):
    data_buffer += '\n'

  if is_uft:
    data_buffer = data_buffer.replace('\n', '\r\n')
    print 'Opening UFT host {:s} port {:d}'.format(
        keyword_arguments['host'],
        keyword_arguments['port_uft'])
    network_socket = socket.create_connection((keyword_arguments['host'],
                                               keyword_arguments['port_uft']))
    _UftPrologue(keyword_arguments['login'],
                 keyword_arguments['uft_host'],
                 fname,
                 ftype,
                 fmode,
                 len(data_buffer),
                 date,
                 is_ebcdic,
                 network_socket)
  else:
    print 'Opening reader on host {:s} port {:d}'.format(
        keyword_arguments['host'],
        port)
    network_socket = socket.create_connection((keyword_arguments['host'], port))
    _ReaderPrologue(keyword_arguments['login'],
                    fname,
                    ftype,
                    fmode,
                    date,
                    is_ebcdic,
                    network_socket)

  network_socket.sendall(data_buffer)       # pylint: disable=E1101

  if is_uft:
    _Expect(network_socket, "EOF", "213")
    _Expect(network_socket, "QUIT", "250")

  network_socket.shutdown(socket.SHUT_RDWR) # pylint: disable=E1101
  network_socket.close()


def _MakeTranslateTable():
  """Build an ASCII to EBCDIC translation table."""
  result = 256 * [chr(0xff)]
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
      u'¬':0x5F,                              # "¬" is Unicode
  }
  for key, value in translate_map.items():
    result[ord(key)] = chr(value)
  return ''.join(result)


def _Main():
  """Main program, requests arg processing and then sends each named files."""
  args = _ParseCommandLine(sys.argv[1:])
  global TRANSLATE_TABLE                # pylint: disable=W0603
  TRANSLATE_TABLE = _MakeTranslateTable()
  keyword_arguments = vars(args)
  first = True
  for current in args.file:
    if first:
      first = False
    else:
      # Allow Hercules side networking/IO to catch up, else the next file(s)
      # may get rejected by Hercules (which reports no error back to us!).
      time.sleep(keyword_arguments['sleep'])

    _ProcessFile(current, keyword_arguments)

if __name__ == "__main__":
  sys.exit(_Main())
