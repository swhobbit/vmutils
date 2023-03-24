#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# vim: ts=2 sw=2 expandtab

"""Send a text file to a user via the VM reader or UTF protocol"""

import argparse
import getpass
from http import client
from http import HTTPStatus
from os import path
import os
import socket
import sys
import time

__version__ = '1.2.7'
__author__ = 'ahd@kew.com (Drew Derbyshire)'
__copyright__ = ('Version ' + __version__ + '. '
                 'Copyright 2018-2022 by Kendra Electronic Wonderworks. '
                 'All commercial rights reserved.\n'
                )

TRANSLATE_TABLE = None

ASCII_DEFAULT_PORT = int(os.getenv('HERCULES_ASCII_READER',
                   default='14425'))
EBCDIC_DEFAULT_PORT = int(os.getenv('HERCULES_EBCDIC_READER',
                  default='25405'))
UFT_DEFAULT_PORT = 608

# We LIKE how we preface internal routines with underscores.
# pylint: disable=C0103

def _ParseCommandLine(command_line):
  """Parse program arguments"""

  def _PositiveInteger(value):
    """Convert passed value to a positive integer and verify it."""
    ivalue = int(value)
    if ivalue <= 0:
      raise argparse.ArgumentTypeError(
          f'{value} is not a positive int value')
    return ivalue

  def _StringToken(value):
    """Convert passed value to an upper case string and verify it."""
    ivalue = value.upper()
    if not value:
      raise argparse.ArgumentTypeError(
        'String argument is empty')
    if ' ' in value:
      raise argparse.ArgumentTypeError(
        f'"{value}" contains spaces')
    if len(value) > 8:
      raise argparse.ArgumentTypeError(
        f'"{value}" is longer than eight characters')
    return ivalue

  parser = argparse.ArgumentParser(
      description='Transmit a file to a user on VM '
      '(or connected via a VM system) either via '
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
      version='%(prog)s ' + __version__)
  parser.add_argument(
      '-d',
      '--debug',
      default=False,
      action='store_true',
      help='Report additional debugging information about the transfer '
      '(Default: %(default)s)')
  parser.add_argument(
      '-l',
      '--login',
      default=getpass.getuser().upper(),
      help='User login id to send file to '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-H',
      '--host',
      default='Hercules',
      help='The TCP/IP hostname of the server to connect to; '
      'files are delivered to '
      'the specified login on this host unless the UFT or RSCS options '
      'are specified '
      '(Default: %(default)s)',
      type=socket.gethostbyname,
  )
  parser.add_argument(
      '-t',
      '--filetype_default',
      metavar='FT',
      default='DATA',
      help='Filetype to add to the name '
      'if the local file name has no usable extension. '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-m',
      '--filemode',
      default='A1',
      metavar='FM',
      help='Filemode (class) to spool file as '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-e',
      '--ebcdic',
      '--binary',
      default=False,
      action='store_true',
      help='Transmit the file (which must already be in EBCDIC), '
      'via the EBCDIC reader port or UTF mode E '
      '(Default: %(default)s, except this option is automatically '
      'enabled for files of type VMARC and XMI, '
      'which are always in EBCDIC.)'
  )
  parser.add_argument(
      '-u',
      '--uft',
      dest='is_uft',
      default=False,
      action='store_true',
      help='Connect to the specified UFT port on the TCP/IP server '
      'rather than to a reader port, '
      'and use the UFT protocol to send the file. '
      '(Default: %(default)s)'
  )
  parser.add_argument(
      '-o',
      '--os',
      '--mvs',
      dest='is_os',
      default=False,
      action='store_true',
      help='The target system is running OS/360 (or a successor), '
      'not VM. '
      'To avoid mucking things up on such a system, '
      'no VM READ header card will preface the file. '
      '(Default: %(default)s, '
      'except that this option is automatically enabled for '
      'remote systems with MVS in their name '
      'and for files of type XMI, JCL, or JOB.)'
  )
  parser.add_argument(
      '-r',
      '--remote_node',
      default=None,
      metavar='REMOTE_NODE',
      help='The node name that the file is forwarded to via RSCS '
      'after receipt on the TCP/IP server host. '
      '(Default: %(default)s, that is deliver to the local host.)',
      type=_StringToken,
  )
  parser.add_argument(
      '-R',
      '--rscs_vm',
      default='RSCS',
      metavar='RSCS_VM',
      help='When forwarding to a remote node, '
      'the user id of the RSCS virtual machine to send files via. '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  exclusive_port_flags.add_argument(
      '-A',
      '--port_ascii',
      default=ASCII_DEFAULT_PORT,
      metavar='APORT',
      help='The TCP port number of the reader for ASCII '
      'files on the TCP/IP server host. '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  exclusive_port_flags.add_argument(
      '-E',
      '--port_ebcdic',
      metavar='EPORT',
      default=EBCDIC_DEFAULT_PORT,
      help='The TCP port number of the reader for EBCDIC'
      ' files on the TCP/IP server host. '
      '(Default: %(default)s)',
      type=_PositiveInteger,
  )
  exclusive_port_flags.add_argument(
      '-U',
      '--port_uft',
      metavar='UPORT',
      default=UFT_DEFAULT_PORT,
      help='The TCP port number to send UTF/SIFT files via. '
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

def _Send(network_socket, buffer, debug, translate=False):
  """Write buffer, translating if needed and making strings bytes."""
  if translate:
    buffer = buffer.translate(TRANSLATE_TABLE)

  if isinstance(buffer, str):
    # We don't trust Python locale to do the right thing; this brute force
    # handles conversion in ASCII -or- if we translated to EBCDIC above.
    if debug:
      if len(buffer) < 82 and not translate:
        print(f'Sending {len(buffer)} characters:', buffer.rstrip())
      else:
        print(f'Sending {len(buffer)} characters')
    buffer = bytes.fromhex(''.join([f'{ord(x):02x}' for x in buffer]))

  else:
    if debug:
      print(f'Sending {len(buffer)} data bytes')

  network_socket.sendall(buffer)


def _Expect(network_socket, prompt, expected, debug):
  """Write a line to the server & look for any of the expected response(s)"""
  if prompt:
    if debug:
      print(f'Sending:  {prompt},\twant: {expected}')
    _Send(network_socket, f'{prompt}\r\n', False)

  if not expected:
    return

  # Convert any atomic object to a tuple we can iterate over below
  if not isinstance(expected, (tuple, list)):
    expected = (expected,)

  actual = network_socket.recv(512).decode(encoding='utf-8')

  for entry in expected:
    if isinstance(entry, HTTPStatus):
      entry = str(entry.value)
    elif isinstance(entry, int):
      entry = str(entry)

    if actual.startswith(entry):
      return

  # Bad response from server, quit conversation, report it and die.
  _Send(network_socket, 'QUIT\r\n', debug)
  raise client.BadStatusLine(
     f'\nSent: {prompt},\nExpected: {expected},\nReceived: {actual}')


def _CharacterSet(is_ebcdic):
  """Report Character set in use as a string."""

  if is_ebcdic:
    return "EBCDIC"

  return "ASCII"


def _UftPrologue(keywords,
         file_info,
         network_socket):
  """Generate header records for a UFT submission"""
  _Expect(network_socket,
      None,
      ('2', HTTPStatus.CONTINUE),
      keywords['debug'])
  _Expect(network_socket,
      f'FILE {file_info["length"]} {getpass.getuser().upper()}',
      (HTTPStatus.CREATED, HTTPStatus.OK),
      keywords['debug'])
  _Expect(network_socket,
      f'USER {keywords["login"]}',
      HTTPStatus.OK,
      keywords['debug'])

  if file_info['is_ebcdic']:
    _Expect(network_socket,
        'TYPE I', (HTTPStatus.CREATED, HTTPStatus.OK),
        keywords['debug'])
    _Expect(network_socket,
        'LRECL 80', (HTTPStatus.CREATED, HTTPStatus.OK),
        keywords['debug'])
  else:
    _Expect(network_socket,
        'TYPE A', (HTTPStatus.CREATED, HTTPStatus.OK),
        keywords['debug'])

  _Expect(network_socket,
      f'NAME {file_info["fname"]}.{file_info["ftype"]}',
      (HTTPStatus.CREATED, HTTPStatus.OK),
      keywords['debug'])

  if keywords["remote_node"]:
    _Expect(network_socket,
        f'DEST {keywords["remote_node"]}',
        (HTTPStatus.CREATED, HTTPStatus.OK),
        keywords['debug'])

  _Expect(network_socket,
      f'DATE {file_info["date"]}',
      (HTTPStatus.CREATED, HTTPStatus.OK),
      keywords['debug'])
  _Expect(network_socket,
      f'DATA {file_info["length"]}',
       (123, HTTPStatus.CREATED),
       keywords['debug'])


def _UftSend(keywords,
       file_info,
       data_buffer):
  """Send a file via a remote UFT server"""

  if not file_info['is_ebcdic']:
    # Internet protocol is \r\n for new lines.
    data_buffer = data_buffer.replace('\n', '\r\n')
    file_info['length'] = len(data_buffer)

  if keywords['debug']:
    print(f'Opening UFT host {keywords["host"]} '
        f'port {keywords["port_uft"]} '
        f'for {_CharacterSet(file_info["is_ebcdic"])} '
        f'file {file_info["fname"]}.{file_info["ftype"]} '
        f'with {file_info["length"]} bytes '
        f'for user {keywords["login"]})')

  network_socket = socket.create_connection((keywords['host'],
                         keywords['port_uft']))

  try:
    _UftPrologue(keywords,
           file_info,
           network_socket)
    _Send(network_socket,
        data_buffer,
        keywords['debug'])
    _Expect(network_socket,
        'EOF', ('213', HTTPStatus.OK),
        keywords['debug'])
    _Expect(network_socket,
        'QUIT', ('250', HTTPStatus.OK),
        keywords['debug'])
  finally:
    try:
      network_socket.shutdown(socket.SHUT_RDWR) # pylint: disable=E1101
    except (OSError, ConnectionResetError) as ex:
      print('Error during shutdown of socket:', ex)
    network_socket.close()
    print('File '
          f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
          'sent via UFT')


def _ReaderPrologue(keywords,
          file_info,
          network_socket):
  """Generate Header records for a submission to the VM reader"""

  is_os = keywords['is_os']

  for os_name in ('OS', 'MVS','MVT', 'MFT', 'DOS'):
    if (os_name in keywords['host'] or
      keywords['remote_node'] and os_name in keywords['remote_node']):
      is_os = True

  if file_info["ftype"] in ('JCL', 'JOB', 'XMI'):
    is_os = True

  if is_os:
    print(f'Processing '
        f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
        'in OS mode.')

  if keywords['remote_node']:
    # Remote user via RSCS
    id_card = (f'USERID {keywords["rscs_vm"]:8s} '
           f'CLASS {file_info["fmode"]:1s} '
           f'NAME {file_info["fname"]:8s} {file_info["ftype"]:8s}')
    tag_card = f'{keywords["remote_node"]:8s} {keywords["login"]:8s}'
  else:
    # Local user
    id_card = (f'USERID {keywords["login"]:8s} '
           f'CLASS {file_info["fmode"]:1s} '
           f'NAME {file_info["fname"]:8s} {file_info["ftype"]:8s}')
    tag_card = None

  if is_os:
    read_card = None
  else:
    # :READ  PROFILE  EXEC     A1 AHD191 03/18/18 16:18:44
    read_card = (':READ  '
           f'{file_info["fname"]:8s} '
           f'{file_info["ftype"]:8s} '
           f'{file_info["fmode"]:2s} '
           f'{socket.gethostname().upper().split(".")[0]:6s} '
           f'{file_info["date"]:17s}'
          )

  for card in (id_card, tag_card, read_card):
    if card:
      if file_info['is_ebcdic']:
        card = f'{card:80}'.translate(TRANSLATE_TABLE)
      else:
        card = card + '\n'
      _Send(network_socket, card, keywords['debug'])


def _ReaderSend(keywords,
        file_info,
        data_buffer):
  """Send a file to a remote VM virtual (network) reader"""

  if file_info['is_ebcdic']:
    port = keywords['port_ebcdic']
  else:
    port = keywords['port_ascii']

  if keywords['debug']:
    print(f'Opening VM reader on host {keywords["host"]} '
        f'port {port} '
        f'for {_CharacterSet(file_info["is_ebcdic"])} file '
        f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
        f'for user {keywords["login"]}')

  network_socket = socket.create_connection((keywords['host'],
                         port))
  try:
    _ReaderPrologue(keywords,
            file_info,
            network_socket)

    _Send(network_socket, data_buffer, keywords['debug'])
  finally:
    try:
      network_socket.shutdown(socket.SHUT_RDWR) # pylint: disable=E1101
    except (OSError, ConnectionResetError) as ex:
      print('Error during shutdown of socket:', ex)
    network_socket.close()
    print('File '
          f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
          'sent via reader')


def _ProcessFile(file_path, keywords):   # pylint: disable=R0914
  """Send a single file to VM, prefixed by USERID and READ cards."""
  file_path = path.abspath(path.expanduser(file_path))
  length = path.getsize(file_path)
  date = time.strftime('%D %T', time.localtime(path.getmtime(file_path)))

  base_name = path.basename(file_path).replace('_', '$').upper()
  base_name = base_name.strip().strip('.').split('.')
  fname = base_name[0]

  if len(base_name) == 1:
    ftype = keywords['filetype_default']
  else:
    ftype = base_name[1][:8]
  fmode = keywords['filemode'][:2]

  is_ebcdic = keywords['ebcdic'] or ftype in ('VMARC', 'XMI')
  is_ebcdic = is_ebcdic or keywords['port_ebcdic'] != EBCDIC_DEFAULT_PORT

  is_uft = keywords['is_uft'] or keywords['port_uft'] != UFT_DEFAULT_PORT

  if is_ebcdic and length % 80:
    raise RuntimeError(f'Length of file {file_path} '
               f'is not a multiple of 80, it is {length}')

  # Ignore possible use of "with", we have two opens for the same handle
  # pylint: disable=R1732
  if is_ebcdic:
    with open(file_path, 'rb') as file_handle:
      data_buffer = file_handle.read()
  else:
    with open(file_path, 'rt', encoding='utf-8') as file_handle:
      data_buffer = file_handle.read()

  # Insure any ASCII file ends with a new line, unless it was completely
  # empty
  if (not is_ebcdic and data_buffer and data_buffer[-1] != '\n'):
    data_buffer += '\n'

  file_info = {
    'fname':fname,
    'ftype':ftype,
    'fmode':fmode,
    'date':date,
    'length':length,
    'is_ebcdic':is_ebcdic,
  }

  if is_uft:
    _UftSend(keywords,
         file_info,
         data_buffer)
  else:
    _ReaderSend(keywords,
          file_info,
          data_buffer)


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
      chr(170):0x5F,          # really, logical not
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
      '¬':0x5F,                # '¬' is Unicode
  }
  for key, value in translate_map.items():
    result[ord(key)] = chr(value)
  return ''.join(result)


def _Main():
  """Main program, does arg processing and then sends each named file."""
  args = _ParseCommandLine(sys.argv[1:])
  global TRANSLATE_TABLE          # pylint: disable=W0603
  TRANSLATE_TABLE = _MakeTranslateTable()
  keywords = vars(args)
  first = True

  for current in args.file:
    if not first:
      # Allow Hercules side networking/IO to catch up, else the file may
      # get rejected by Hercules (which reports no error back to us!).
      time.sleep(keywords['sleep'])
      first = False

    _ProcessFile(current, keywords)

# Invoke the main program (above)
if __name__ == '__main__':
  sys.exit(_Main())
