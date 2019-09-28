#!/bin/sh 

# victoria.hh.kew.com has address 192.168.205.2
# victoria.hh.kew.com has IPv6 address 2001:470:b:625:268:68ff:fe00:cd02
HOST="${1:?'Missing host name'}"
PORT="${2:?'Missing port number'}"
IPv4=`host ${HOST} | awk '/has address/ {print $4}'`
IPv6=`host ${HOST} | awk '/has IPv6 address/ {print $5}'`

echo ip addr add ${IPv6}/64  dev eth0

sudo 6tunnel -u nobody -6 -4 -l ${HOST} ${PORT} ${HOST} 
exit $?
