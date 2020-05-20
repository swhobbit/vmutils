#!/usr/bin/env python3

# vim: expandtab sw=2 ts=2

"""Add a subnetwork IP address to the correct TAP adapter for a VM."""

import argparse
import errno
import re
import subprocess
import sys

__author__ = "ahd@kew.com (Drew Derbyshire)"

__version__ = "1.0.2"

_PARSER = argparse.ArgumentParser(
    description='Generate IP address to route Hercules tap device',
    add_help=True)


def _BuildParser():
  """Add command arguments to the command line parser."""
  _PARSER.add_argument('--version',
                       '-v',
                       help='Print the program version',
                       action='version',
                       version='%(prog)s by {} version {}'.format(
                           __author__, __version__))
  _PARSER.add_argument('--device',
                       '-d',
                       help='tap device to check and if void of an IP'
                       ' address and if none found, add one.',
                       default=argparse.SUPPRESS,
                       type=str)
  _PARSER.add_argument('oat',
                       default=argparse.SUPPRESS,
                       nargs='+',
                       type=argparse.FileType('r'),
                       help='OAT file to read for MAC and IP addresses'
                       ' of the Hercules device')


def _ReadOatFile(handle):
  """The OAT file for the LCS Ethernet and network addresses"""
  mac_address = None
  machine_ip = None

  regex_ip = re.compile(
      r'\s*[\dA-Fa-f]+\s+IP\s+00\s+PRI\s+((\d{1,3}\.){3}\d{1,3})\s*')
  regex_mac = re.compile(
      r'\s*HWADD\s+00\s+(([\dA-Fa-f]{2,2}[-:]){5}[\dA-Fa-f]{2,2})\s*')

  for data in handle:
    data = data.rstrip()
    print(data, end='\t')
    match = regex_ip.match(data)
    if match:
      machine_ip = match.group(1)
      print('IP =', machine_ip, end='\t')
    else:
      match = regex_mac.match(data)
      if match:
        mac_address = match.group(1).replace('-', ':').lower()
        print('MAC =', mac_address, end='\t')
    print()

  if not mac_address:
    print('No MAC address found, exiting')
    sys.exit(errno.ENXIO)
  elif not machine_ip:
    print('No IP address found, exiting')
    sys.exit(errno.ENODATA)

  return (mac_address, machine_ip)


def _ReadOneInterface(entry, mac, gateway_ip, device):
  """Parse 'ip addr list' entry looking for our target device"""

  if not device.startswith('tap'):
    # device is not a tap device.
    return (None, None)

  this_mac = None
  for data in entry.split('\n'):
    token = data.split()

    if not token:
      continue

    if token[0] == 'inet':         # Already has an IPv4 address?
      if token[1].split('/')[0] == gateway_ip:
        print('Device',
              device,
              'is already assigned gateway',
              gateway_ip,
              'PROGRAM EXITING.')
        sys.exit(errno.EEXIST)

      print('Device', device, 'already has IPv4 address', token[1])
      return (None, None)          # ... then not usable as our interface

    if token[0] == 'link/ether':
      this_mac = token[1]

  if this_mac == mac:
    print('Device',
          device,
          'has target MAC address',
          mac)
    return (device, None)      # Perfect  match

  print('Device',
        device,
        'MAC address',
        this_mac,
        'is not the desired',
        mac)
  return (None, device)   # Possible fallback device


def _ReadInterfaces(mac, gateway_ip, device):
  """Find the unconfigured interface with the specified Mac address"""
  regex_entry = re.compile(r'^\d+:', flags=(re.DOTALL|re.MULTILINE))
  regex_device = re.compile(r'\s*([a-zA-Z]{2,4}\d*): <.+>.+')

  args = ('ip addr list ' + (device or '')).split()
  proc = subprocess.run(args,
                        capture_output=True,
                        check=True,
                        text=True)
  entries = regex_entry.split(proc.stdout)

  fallback_return = None

  for entry in entries:
    if not entry:
      continue

    device_match = regex_device.match(entry)

    if device_match:
      (device, fallback) = _ReadOneInterface(entry,
                                             mac,
                                             gateway_ip,
                                             device_match.group(1))
      if device:
        return device
      if fallback:
        fallback_return = fallback
    else:
      print('\n\tFAILED TO MATCH', entry,
            '\n\tDEVICE MATCH', device_match,
            sep='\n')

  if not fallback_return:
    print('NO ELIGIBLE DEVICE FOUND, EXITING')
    sys.exit(errno.ENOENT)

  print('Using fallback device', fallback_return)
  return fallback_return


def _ProcessOne(handle, device):
  """Parse and route one system."""
  mac_address, machine_ip = _ReadOatFile(handle)
  print(mac_address, machine_ip)

  token = machine_ip.split('.')
  if token[3] == '1':
    token[3] = '2'
  else:
    token[3] = '1'
  gateway_ip = '.'.join(token)

  device = _ReadInterfaces(mac_address, gateway_ip, device)

  args = 'sudo ip addr add xxx.xxxx.xxx.xxx/24 dev xxxx'.split()
  args[-3] = gateway_ip + '/24'
  args[-1] = device
  print('Executing:', ' '.join(args))

  subprocess.run(args,
                 stdout=sys.stdout,
                 stderr=sys.stderr,
                 check=True,
                 text=True)

def _Main():
  """Main progress to process all systems on command line."""
  print(sys.argv[0], __version__)
  _BuildParser()
  cli_flags = vars(_PARSER.parse_args())
  for system in cli_flags['oat']:
    if 'device' in cli_flags:
      _ProcessOne(system, cli_flags['device'])
    else:
      _ProcessOne(system, None)
  sys.exit(0)

if __name__ == '__main__':
  sys.exit(_Main())
