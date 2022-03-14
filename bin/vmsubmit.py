#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""Send a text file to a user via the VM reader or UTF protocol"""

import argparse
import getpass
from http import client
import http
from os import path
import os
import socket
import sys
import time

__version__ = '1.2.0'
__author__ = 'ahd@kew.com (Andrew H. Derbyshire)'
__copyright__ = ('Copyright 2018-2022 by Kendra Electronic Wonderworks.  '
                 'All commercial rights reserved.\n'
                 'Version ' + __version__)

TRANSLATE_TABLE = None

ASCII_READER_DEFAULT_PORT = int(os.getenv('HERCULES_ASCII_READER', default='14425'))
EBCDIC_READER_DEFAULT_PORT = int(os.getenv('HERCULES_EBCDIC_READER', default='254025'))
UFT_DEFAULT_PORT = 608

def _ParseCommandLine(command_line):
  """Parse program arguments"""

  def _PositiveInteger(value):
    """Convert passed value to a postive integer and verify it."""
    ivalue = int(value)
    if ivalue <= 0:
      raise argparse.ArgumentTypeError(
          '%s is an invalid positive int value' % value)
    return ivalue

  parser = argparse.ArgumentParser(
      description='Transmit a file to a user on VM either via '
      'a networked emulated system reader (the default) or '
      'via the Sender-Initiated/Unsolicited File Transfer (SIFT/UFT) '
      'protocol as (incompletely) defined in RFC 1440.',
      epilog=__copyright__
  )
  exclusive_port_flags = parser.add_mutually_exclusive_group()
  parser.add_argument(
      '-v',
      '--version',
      action='version',
      version='%(prog)s ' + __version__ )
  parser.add_argument(
      '-l',
      '--login',
      default=str.upper(getpass.getuser()),
      help='User login id to send file to '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-H',
      '--host',
      default='hercules',
      help='The TCP/IP hostname of the server to connect to; '
      'files are delivered to '
      'the specified login on this host unless the UFT or RCSCS options '
      'are specified '
      '(Default: %(default)s)',
      type=socket.gethostbyname,
  )
  parser.add_argument(
      '-t',
      '--filetype_default',
      metavar='FT',
      default='DATA',
      help='Filetype to add to the name on VM '
      'if the local file name has no usable extension '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-m',
      '--filemode',
      default='A1',
      metavar='FM',
      help='Filemode (class) to spool file as '
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-e',
      '--ebcdic',
      default=False,
      action='store_true',
      help='Transmit the file (which must already be in EBCDIC), '
      'using the EBCDIC reader port or UTF mode E as specified '
      '(generated header records are translated to EBCDIC as required) '
      '(Default: %(default)s, except for files of type VMARC or XMI, '
      'which are always in EBCDIC)',
  )
  parser.add_argument(
      '-u',
      '--uft',
      default=False,
      action='store_true',
      help='Connect to the specified UFT port on the TCP/IP server '
      'rather than to a reader port, '
      'and use the UFT protocol to send the file. '
      '(Default: %(default)s)'
  )
  parser.add_argument(
      '-r',
      '--remote_node',
      default=None,
      metavar='RSCS_NODE',
      help='Specify the RSCS node name that the file is to be sent to '
      'after receipt on the TCP/IP server host.'
      '(Default: %(default)s)',
      type=str.upper,
  )
  parser.add_argument(
      '-R',
      '--rscs_vm',
      default='RSCS',
      metavar='RSCS_VM',
      help='User id of the RSCS virtual machine to spool files via'
      'to transmit. '
      '(Default: %(default)s)',
      type=str.upper,
  )
  exclusive_port_flags.add_argument(
      '-A',
      '--port_ascii',
      default=ASCII_READER_DEFAULT_PORT,
      metavar='APORT',
      help='TCP port number of reader on host for ASCII files '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  exclusive_port_flags.add_argument(
      '-E',
      '--port_ebcdic',
      metavar='EPORT',
      default=EBCDIC_READER_DEFAULT_PORT,
      help='TCP port number of reader on host for EBCDIC files '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  exclusive_port_flags.add_argument(
      '-U',
      '--port_uft',
      metavar='UPORT',
      default=UFT_DEFAULT_PORT,
      help='TCP port number to send UTF/SIFT files via '
      '(Default: %(default)s)',
      type=_PositiveInteger,
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
      type=str,
  )
  return parser.parse_args(command_line)

def _Send(network_socket, buffer, translate=False):
  """Write buffer, translating if needed and making strings bytes."""
  if translate:
    buffer = buffer.translate(TRANSLATE_TABLE)

  if isinstance(buffer, str):
    # Don't trust Python locale to do the right thing; this brute force
    # handles conversion in ASCII -or- if we translated to EBCDIC above.
    buffer = bytes.fromhex(''.join('{:02x}'.format(ord(x)) for x in buffer))
    print('Sending {:d} string bytes'.format(len(buffer)))
  else:
    print('Sending {:d} data bytes'.format(len(buffer)))

  network_socket.sendall(buffer)


def _Expect(network_socket, prompt, expected):
  """Write single line to the UFT server and look for the expected response"""
  if prompt:
    _Send(network_socket, prompt)
    _Send(network_socket, b'\r\n')
    print('Sent:', prompt)

  if expected:
    expected = str(expected)  # Might be an integer
    actual = network_socket.recv(512).decode(encoding='utf-8')
    if not actual.startswith(expected):
      raise client.BadStatusLine(
          '\nSent: {:s},\nExpected: {:s},\nReceived: {:s}'.format(prompt,
                                                                  expected,
                                                                  actual))

def _UftPrologue(login,              # pylint: disable=R0913
                 hostname,
                 fname,
                 ftype,
                 length,
                 date,
                 is_ebcdic,
                 network_socket):
  """Generate header records for a UFT submission"""
  _Expect(network_socket, None, '2')
  _Expect(network_socket,
          'FILE {:d} {:s}'.format(length,
                                  str.upper(getpass.getuser())),
          http.HTTPStatus.CREATED)
  _Expect(network_socket,
          'USER {:s}@{:s}'.format(login, hostname),
          http.HTTPStatus.CREATED)

  if is_ebcdic:
    _Expect(network_socket, 'TYPE F 80', http.HTTPStatus.CREATED)
  else:
    _Expect(network_socket, 'TYPE A', http.HTTPStatus.CREATED)

  _Expect(network_socket,
          'NAME {:s}.{:s}'.format(fname, ftype),
          http.HTTPStatus.CREATED)
  _Expect(network_socket, 'DATE {:s}'.format(date), http.HTTPStatus.CREATED)
  _Expect(network_socket, 'DATA {:d}'.format(length), http.HTTPStatus.CREATED)


def _ReaderPrologue(remote_node,
                    login,
                    fname,
                    ftype,
                    fmode,
                    date,
                    is_ebcdic,
                    rscs_vm,
                    network_socket):
  """Generate Header records for a submission to the VM reader"""
  if remote_node:
    # Remote user via RSCS
    id_card = 'USERID {:8s} CLASS {:1s} NAME {:8s} {:2s}'.format(
        rscs_vm,
        fmode[0:1],
        fname[0:8],
        ftype[0:8])
    tag_card = '{:8s} {:8s}'.format(
        remote_node,
        login)
  else:
    # Local user
    id_card = 'USERID {:8s} CLASS {:1s} NAME {:8s} {:2s}'.format(
        login,
        fmode[0:1],
        fname[0:8],
        ftype[0:8])
    tag_card = None

  # :READ  PROFILE  EXEC     A1 AHD191 03/18/18 16:18:44
  read_card = ':READ {:8s} {:8s} {:2s} {:6s} {:17s}'.format(
      fname[0:8],
      ftype[0:8],
      fmode[0:2],
      socket.gethostname().upper().split('.')[0][0:6],
      date,
      )

  buffer = ''
  for card in (id_card, tag_card, read_card):
    if card:
      if is_ebcdic:
        card = '{:80}'.format(card).translate(TRANSLATE_TABLE)
      else:
        card = card + '\n'
      _Send(network_socket, card)


def _ProcessFile(file_path, keywords):   # pylint: disable=R0914
  """Send a single file to VM, prefixed by USERID and READ cards."""
  full_name = path.abspath(path.expanduser(file_path))
  length = path.getsize(full_name)
  date = time.strftime('%D %T', time.localtime(path.getmtime(full_name)))

  file_name = path.basename(full_name)
  vm_file_name = file_name.strip().strip('.').replace('_',
                                                      '$').upper().split('.')
  fname = vm_file_name[0]
  if len(vm_file_name) == 1:
    ftype = keywords['filetype_default']
  else:
    ftype = vm_file_name[1][0:8]
  fmode = keywords['filemode'][0:2]

  is_ebcdic = keywords['ebcdic']
  is_ebcdic = is_ebcdic or ftype in ('VMARC', 'XMI')
  is_ebcdic = is_ebcdic or keywords['port_ebcdic'] != EBCDIC_READER_DEFAULT_PORT

  is_uft = keywords['uft']
  is_uft = is_uft or keywords['port_uft'] != UFT_DEFAULT_PORT

  if is_ebcdic and length % 80:
    error = 'Length of file {:s} is not a multiple of 80, it is {:d}'.format(
        full_name, length)
    raise RuntimeError(error)

  if is_ebcdic:
    print('File', fname, ftype, 'is EBCDIC')
    port = keywords['port_ebcdic']
    file_handle = open(full_name, 'rb')
  else:
    print('File', fname, ftype, 'is ASCII')
    port = keywords['port_ascii']
    file_handle = open(full_name, 'rt', encoding='utf-8')

  data_buffer = file_handle.read()
  file_handle.close()

  # Insure the file ends with a new line, unless it was completely empty
  if (not is_ebcdic and data_buffer and data_buffer[-1] != '\n'):
    data_buffer += '\n'

  try:
    if is_uft:
      data_buffer = data_buffer.replace('\n', '\r\n')
      print('Opening UFT host {:s} port {:d} for user '
            '{:s} file {:s} {:s}'.format(
                keywords['host'],
                keywords['port_uft'],
                keywords['login'],
                fname,
                ftype))
      network_socket = socket.create_connection((keywords['host'],
                                                 keywords['port_uft']))
      _UftPrologue(keywords['login'],
                   keywords['remote_node'],
                   fname,
                   ftype,
                   len(data_buffer),
                   date,
                   is_ebcdic,
                   network_socket)
    else:
      print('Opening reader on host {:s} port {:d} for user '
            '{:s} file {:s} {:s} {:s}'.format(
                keywords['host'],
                port,
                keywords['login'],
                fname,
                ftype,
                fmode))
      network_socket = socket.create_connection(
          (keywords['host'], port))
      _ReaderPrologue(keywords['remote_node'],
                      keywords['login'],
                      fname,
                      ftype,
                      fmode,
                      date,
                      is_ebcdic,
                      keywords['rscs_vm'],
                      network_socket)

    _Send(network_socket, data_buffer)

    if is_uft:
      _Expect(network_socket, 'EOF', '213')
      _Expect(network_socket, 'QUIT', '250')
  finally:
    try:
      network_socket.shutdown(socket.SHUT_RDWR) # pylint: disable=E1101
    except (OSError, ConnectionResetError) as ex:
      print('Error during shutdown of socket:', ex)
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
      '¬':0x5F,                              # '¬' is Unicode
  }
  for key, value in translate_map.items():
    result[ord(key)] = chr(value)
  return ''.join(result)


def _Main():
  """Main program, requests arg processing and then sends each named file."""
  args = _ParseCommandLine(sys.argv[1:])
  global TRANSLATE_TABLE                # pylint: disable=W0603
  TRANSLATE_TABLE = _MakeTranslateTable()
  keywords = vars(args)
  first = True
  for current in args.file:
    if not first:
      # Allow Hercules side networking/IO to catch up, else it may get
      # rejected by hercules (which reports no error back to us!).
      time.sleep(keywords['sleep'])
    first = False

    _ProcessFile(current, keywords)

if __name__ == '__main__':
  sys.exit(_Main())
