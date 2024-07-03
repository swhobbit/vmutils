#!/usr/bin/env python3

# -*- coding: UTF-8 -*-
# vim: ts=2 sw=2 expandtab

"""Send a text file to a user via the VM reader or UTF protocol"""

import argparse
import enum
import ftplib
from ftplib import FTP
import getpass
from http import client
from http import HTTPStatus
import io
from os import path
import os
import socket
import sys
import time

__version__ = '1.3.1'
__author__ = 'ahd@kew.com (Drew Derbyshire)'
__copyright__ = ('Version ' + __version__ + '. '
                 'Copyright 2018-2024 by Kendra Electronic Wonderworks. '
                 'All commercial rights reserved.\n'
                )

TRANSLATE_TABLE = None

ASCII_DEFAULT_PORT = int(os.getenv('HERCULES_ASCII_READER', default='1442'))
EBCDIC_DEFAULT_PORT = int(os.getenv('HERCULES_EBCDIC_READER', default='2540'))
UFT_DEFAULT_PORT = int(os.getenv('HERCULES_SIFT_PORT', default='608')) 
FTP_DEFAULT_PORT = socket.getservbyname('ftp')

class Transport(enum.StrEnum):
  """Choices for our transport protocol"""
  FTP = 'FTP'
  RDR = 'RDR'
  UFT = 'UFT'

# We LIKE how we preface internal routines with underscores.
# pylint: disable=C0103

def _ParseCommandLine(command_line):
  """Parse program arguments"""

  def _TransportUpper(member):
    """Look up Transport enum based on upper case string param."""
    return Transport(member.upper())

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
      'a networked emulated system reader (the default), FTP or '
      'via the Sender-Initiated/Unsolicited File Transfer (SIFT/UFT) '
      'protocol as (incompletely) defined in RFC 1440.',
      epilog=__copyright__
  )

  parser.add_argument(
      '-H',
      '--host',
      default='Hercules',
      help='The TCP/IP hostname of the server to connect to; '
      'files are delivered to '
      'the specified login on this host unless the UFT or remote node options '
      'are specified. '
      '(Default: %(default)s)',
      type=socket.gethostbyname,
  )
  parser.add_argument(
      '-p',
      '--port',
      default=0,
      metavar='PORT',
      help='The TCP port number of the system to send the file via. '
      '(Default: '
      f'{ASCII_DEFAULT_PORT} for ASCII reader files, '
      f'{EBCDIC_DEFAULT_PORT} for EBCDIC reader files, '
      f'{FTP_DEFAULT_PORT} for FTP connections, '
      f'and {UFT_DEFAULT_PORT} for UFT connections)',
      type=_PositiveInteger,
  )
  parser.add_argument(
      '-l',
      '--login',
      '--user',
      '--id',
      default=getpass.getuser().upper(),
      help='User login id to send file to. '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-P',
      '--password',
      '--passwd',
      help='FTP Password of login id to send file to. '
      ' Not used by RDR or UFT transports. '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-a',
      '--account',
      '--acct',
      default=None,
      help='FTP Account (minidisk password) of login id to send file to. '
      ' Not used by RDR or UFT transports. '
      '(Default: %(default)s)',
      type=_StringToken,
  )
  parser.add_argument(
      '-r',
      '--remote_node',
      default=None,
      metavar='REMOTE_NODE',
      help='The node name that the file is forwarded to via RSCS '
      'after receipt on the TCP/IP server host. '
      '(Default: %(default)s, that is deliver on the TCP/IP server host.)',
      type=_StringToken,
  )
  transports = ', '.join(list(Transport))
  parser.add_argument(
      '-T',
      '--transport',
      type=_TransportUpper,
      default=Transport.RDR,
      choices=[f'{choice}' for choice in Transport],
      help=f'One of the connection protocols of {transports} '
      'to send the file via. '
      '(Default: %(default)s)'
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
      help='Filemode (class) to spool file as.'
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
      'via the EBCDIC reader port, FTP binary mode, or UTF mode E. '
      '(Default: %(default)s, except this option is automatically '
      'enabled for files of type VMARC and XMI, '
      'which are always in EBCDIC.)'
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
      'To avoid mucking things up on such an OS-based system, '
      'no VM READ header card will preface the file. '
      '(Default: %(default)s, '
      'except that this option is automatically enabled for '
      'remote systems with OS or MVS in their name '
      'and for files of type XMI, JCL, or JOB.)'
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
    '-d',
    '--debug',
    default=0,
    action='count',
    help='Report additional debugging information about the transfer. '
    '(Default: %(default)s)')
  parser.add_argument(
      '-v',
      '--version',
      action='version',
      version='%(prog)s ' + __version__)
  parser.add_argument(
      'file',
      nargs='+',
      help='File(s) to send to VM',
      type=str,
  )
  return parser.parse_args(command_line)


def _HostName(keywords, port=False):
  """Format hostname, host IP address, and port for messages."""
  if port:
    return (f'{socket.gethostbyaddr(keywords["host"])[0]}:'
            f'{keywords["port"]} '
            f'({keywords["host"]})')

  return (f'{socket.gethostbyaddr(keywords["host"])[0]}:'
          f'{keywords["port"]} '
          f'({keywords["host"]})')

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

  for offset in range(0, len(buffer), 4096):
    network_socket.send(buffer[offset:offset + 4096])
    if debug:
      print(offset, flush=True)
    time.sleep(0.20)

  if debug:
    print('')


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
  """Send a file to the IBM host via a remote UFT server"""

  if not file_info['is_ebcdic']:
    # Internet protocol is \r\n for new lines.
    data_buffer = data_buffer.replace('\n', '\r\n')
    file_info['length'] = len(data_buffer)

  if keywords['debug']:
    print(f'Opening UFT host {_HostName(keywords, port=True)} '
        f'for {_CharacterSet(file_info["is_ebcdic"])} '
        f'file {file_info["fname"]}.{file_info["ftype"]} '
        f'with {file_info["length"]} bytes '
        f'for user {keywords["login"]})')

  try:
    network_socket = socket.create_connection(
        (keywords['host'],
         keywords['port']))
  except (OSError) as ex:
    print('Connection to '
          f'{_HostName(keywords, port=True)} failed.',
          ex)
    sys.exit(ex.errno)

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
      network_socket.close()
    except (OSError, ConnectionResetError) as ex:
      print('Error during shutdown/close of UFT socket:', ex)
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
    id_card = (f'USERID {keywords["rscs_vm"]:8.8s} '
           f'CLASS {file_info["fmode"]:1.1s} '
           f'NAME {file_info["fname"]:8.8s} {file_info["ftype"]:8.8s}')
    tag_card = f'{keywords["remote_node"]:8.8s} {keywords["login"]:8.8s}'
  else:
    # Local user
    id_card = (f'USERID {keywords["login"]:8.8s} '
           f'CLASS {file_info["fmode"]:1.1s} '
           f'NAME {file_info["fname"]:8.8s} {file_info["ftype"]:8.8s}')
    tag_card = None

  if is_os:
    read_card = None
  else:
    # :READ  PROFILE  EXEC     A1 AHD191 03/18/18 16:18:44
    disk_label = socket.gethostname().upper().split('.')[0].split('-')[0]
    read_card = (':READ  '
           f'{file_info["fname"]:8.8s} '
           f'{file_info["ftype"]:8.8s} '
           f'{file_info["fmode"]:2.2s} '
           f'{disk_label:6.6s} '
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
  """Send a file to the IBM host via a networked VM virtual reader"""

  if keywords['debug']:
    print(f'Opening VM reader on host {_HostName(keywords, port=True)} '
        f'for {_CharacterSet(file_info["is_ebcdic"])} file '
        f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
        f'for user {keywords["login"]}')

  try:
    network_socket = socket.create_connection((keywords['host'],
                                               keywords['port']))
  except (OSError, ConnectionRefusedError) as ex:
    print(f'Connection to {_HostName(keywords, port=True)} reader failed.',
          ex)
    sys.exit(ex.errno)

  try:
    _ReaderPrologue(keywords,
            file_info,
            network_socket)

    _Send(network_socket, data_buffer, keywords['debug'])
  finally:
    try:
      network_socket.shutdown(socket.SHUT_RDWR) # pylint: disable=E1101
      network_socket.close()
    except (OSError, ConnectionResetError) as ex:
      print('Error during shutdown/close of reader socket:', ex)
      # sys.exit(ex.errno)

    print('File '
          f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
          'sent to '
          f'{_HostName(keywords)} '
          'via reader')


def _FTPSend(keywords,
            file_info,
            data_buffer):
  """Send a file to the IBM host via FTP"""

  if keywords['debug']:
    print(f'Opening VM reader on host {_HostName(keywords, port=True)} '
        f'for {_CharacterSet(file_info["is_ebcdic"])} file '
        f'{file_info["fname"]} {file_info["ftype"]} {file_info["fmode"]} '
        f'for user {keywords["login"]}')

  if 'password' not in keywords or not keywords['password']:
    print('Password not provided for', keywords['transport'])
    sys.exit(89)

  connection = FTP()

  if keywords['debug']:
    connection.set_debuglevel(min(keywords['debug'], 2))

  try:
    connection.connect(host=keywords['host'], port=keywords['port'])
  except (OSError, ConnectionRefusedError) as ex:
    print(f'Connection to {_HostName(keywords, port=True)} reader failed.',
          ex)
    sys.exit(ex.errno)

  try:
    if 'account' in keywords:
      connection.login(user=keywords['login'],
                       passwd=keywords['password'],
                       acct=keywords['account'])
      # Send the account provided, to act as minidisk 191 password.
      connection.sendcmd(f'ACCT {keywords["account"]}')
    else:
      connection.login(user=keywords['login'], passwd=keywords['password'])
  except (ftplib.error_perm,) as ex:
    print(f'Login to {_HostName(keywords)} failed:', ex)
    sys.exit(96)

  text = connection.sendcmd('SYST').replace('-', ' ').splitlines()[0]
  token = text.split(maxsplit=4)
  print(text)

  match token[0:4]:
    case ('215','MVS','Type:','L8'):
      print('System',
            _HostName(keywords),
            'is running MVS/370 3.8 (not supported)')
      sys.exit(97)

    case ('215', 'VM/ESA', _, _) | ('215', 'VM', _, _) if not keywords['account']:
      print('System',
             _HostName(keywords),
             'is running VM and no account was supplied.')
      sys.exit(96)

    case ('215', 'VM/ESA', _, _) | ('215', 'VM', _, _):
      pass

    case ('215', 'MVS', _, _):
      pass

    case _:
      print('System', _HostName(keywords), 'is running unsupported', token[1])
      sys.exit(95)

  if keywords['debug']:
    print('System', _HostName(keywords), 'is running', token[1])

  stor_command = (f'STOR '
                  f'{file_info["fname"]}.'
                  f'{file_info["ftype"]}.'
                  f'{file_info["fmode"]}')

  if file_info['is_ebcdic']:
    with io.BytesIO(initial_bytes=data_buffer) as handle:
      connection.storbinary(stor_command, handle)
  else:
    byte_buffer = bytes.fromhex(''.join([f'{ord(x):02x}'
                                         for x in data_buffer]))
    with io.BytesIO(initial_bytes=byte_buffer) as handle:
      connection.storbinary(stor_command, handle)

    connection.storlines(stor_command, handle)


def _ProcessFile(file_path, keywords):   # pylint: disable=R0914
  """Send a single file to VM, prefixed by USERID and READ cards."""
  file_path = path.abspath(path.expanduser(file_path))
  length = path.getsize(file_path)
  date = time.strftime('%D %T', time.localtime(path.getmtime(file_path)))

  _DEFAULT_PORT = {
    Transport.FTP: FTP_DEFAULT_PORT,
    Transport.RDR: (ASCII_DEFAULT_PORT,
                    EBCDIC_DEFAULT_PORT)[keywords['ebcdic']],
    Transport.UFT: UFT_DEFAULT_PORT
  }

  if not keywords['port']:
    keywords['port'] = _DEFAULT_PORT[keywords['transport']]

  base_name = path.basename(file_path).replace('_', '$').upper()
  base_name = base_name.strip().strip('.').split('.')
  fname = base_name[0]

  if len(base_name) == 1:
    ftype = keywords['filetype_default']
  else:
    ftype = base_name[1][:8]
  fmode = keywords['filemode'][:2]

  is_ebcdic = keywords['ebcdic'] or ftype in ('VMARC', 'XMI')

  if is_ebcdic and length % 80:
    raise RuntimeError(f'Length of file {file_path} '
               f'is not a multiple of 80, it is {length}')

  # Ignore possible use of "with", we have two opens for the same handle
  # pylint: disable=R1732
  if is_ebcdic:
    with open(file_path, 'rb') as file_handle:
      data_buffer = file_handle.read()
  else:
    with open(file_path,
              'rt',
              encoding='utf-8',
              errors='replace') as file_handle:
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

  match keywords['transport']:
    case Transport.UFT:
      _UftSend(keywords, file_info, data_buffer)

    case Transport.RDR:
      _ReaderSend(keywords, file_info, data_buffer)

    case Transport.FTP:
      _FTPSend(keywords, file_info, data_buffer)

    case _:
      # This shuld never happen (trappd by arg parsing)
      print('Invalid transport:', keywords['transport'])
      sys.exit(99)

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
