#!/usr/bin/env python3

# vim: expandtab sw=2 ts=2

"""This is for use with the Hercules mainframe emulator when an emulated LCS
device requires network routing.

How it works:

* Examine the OAT file to determine the network address of the Hercules machine.
* Use the 'ip' command to scan the output of the ip command for one or all
  TAP network devices in the Linux environment to find one with no IPv4
  address assigned. The device specified on the command line or a device
  matching the MAC address of the Hercules machine is preferred.
* Use the 'ip' command to add an IPv4 address to the TAP device (located in the
  previous step) on the subnet of the Hercules machine (located in the first
  step) with route mask of /24.

The second 'ip' command to modify the TAP adapter requires root privileges.
For the command to succeed, it is wrapped by the 'sudo' command; for this to
run without prompting for a password every time, the following should be added
the 'sudousers' file via 'visudo':

    # Allow Hercules group to twiddle network w/o a password:
    %hercules     ALL = NOPASSWD: /sbin/ip

Where 'hercules' is the group Hercules runs under.

(If you're running all of Hercules as root, a suggestion: DON'T.)

To automatically run this command when Hercules opens a new TAP
device, specify these automatic operator commands via the Hercule
console or in the Hercules run file (hercules.rc) before issuing
the IPL command:

    hao tgt HHCLC055I (tap[0-9]+)
    hao cmd sh hercules_route_lcs.py -d $1 hercules.oat
"""

import argparse
import errno
import re
import subprocess
import sys

__author__ = "ahd@kew.com (Drew Derbyshire)"

__version__ = "1.0.3"

_PARSER = argparse.ArgumentParser(
    description='Assign IP address to route Hercules machine via TAP device',
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=True,
    epilog='Additional information:\n \n' + __doc__)


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
                       help='Specify a tap device to check.\n',
                       default=argparse.SUPPRESS,
                       type=str)
  _PARSER.add_argument('oat',
                       nargs='+',
                       type=argparse.FileType('r'),
                       help='File with the Hercules LCS network device address')


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

  args = ('ip -4 addr list ' + (device or '')).split()
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
