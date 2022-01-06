#!/bin/sh 
#	
#		6to4_tunnel.sh 
#		
#		Wrapper to send IPv6 traffic for a host to associated or different
#		IPv4 address
#	
#		 Author: ahd@kew.com (Drew Derbyshire)
#	                 Kendra Electronic Wonderworks, Kenmore WA
#	           Date: 28 September 2019
#	
#	Most software up through the 1990s does not support IPv6.  This can lead
#	to issues where a modern client tries to reach a server on a host with
#	both IPv6 and IPv4 addresses, and gives up after failing to connect to
#	the IPv6 port. This script, in combination with the program 6tunnel,
#	tunnels traffic via an IPv6 source host & port to an IPv4 host & port.
#	
#	The default operation, with two operands, is to forward IPv6 host H/port P
#	to the IPv4 address of host H on port P.  This of course assumes that host
#	H has a valid routable IPv4 stack running.  For example:
#	
#		6to4_tunnel.sh widget.xx.sample.com 23 
#	
#	would route port 23 of the IPv6 address of widget to port 23 on the IPv4
#	address for widget.
#	
#	An extended mode is to forward host IPv6 host H/port P to a second host/
#	port combination, for example to forward to the listening port of an
#	emulator such as hercules. This uses four operands, the source host & port
#	and destination host & port. For example:
#	
#		6to4_tunnel.sh gizmo.xx.sample.com 23 localhost 2023
#	
#	would route from port 23 of the IPv6 address of gizmo to port 2023 on the
#	local host.
#
#	NOTE: Assumes the current user has passwordless sudo access to the ip and
#	6tunnel commands, or is able & willing to enter their sudo password every
#	time this script is run.

SOURCE_HOST="${1:?'Missing host name'}"
SOURCE_PORT="${2:?'Missing port number'}"
TARGET_HOST="${3:-${SOURCE_HOST}}"
TARGET_PORT="${4:-${SOURCE_PORT}}"

# sample-host.hh.kew.com has address 192.168.205.2
# sample-host.hh.kew.com has IPv6 address 2001:4567:b:3987:3456:68dd:fe00:cd02
IPv6=`host -t AAAA ${SOURCE_HOST} | awk '/has IPv6 address/ {print $5}'`

# Make the current host an alias of the IPv6 host address 
sudo ip addr add ${IPv6}/64  dev eth0

sudo 6tunnel -u nobody -6 -4 -l ${SOURCE_HOST} ${SOURCE_PORT} ${TARGET_HOST} ${TARGET_PORT}
exit $?
