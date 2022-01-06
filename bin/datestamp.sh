#!/bin/sh
read message
while [ $? -eq 0 ] ; do
	echo "$(date +%F) ${message}"
	read message
done
