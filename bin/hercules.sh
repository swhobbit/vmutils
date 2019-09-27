#!/bin/sh 
LOG=${1:=log/hercules.log}
DIRECTORY=`dirname ${LOG}`
[ -d ${DIRECTORY} ] || mkdir -p ${DIRECTORY}
exec hercules -f ${HERCULES_NAME}.conf > ${LOG}
