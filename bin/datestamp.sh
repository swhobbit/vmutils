#!/bin/sh
if [ 0 -ne "$#" ] ; then 
	exec $0 > $1
fi

read message
while [ $? -eq 0 ] ; do
	echo "$(date +"${DATE_FORMAT:-%F}") ${message}"
	trap 'continue' 2
	read message
done
