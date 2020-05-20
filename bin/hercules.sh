#!/bin/sh
BINARY="${HOME}/bin/hercules/${HERCULES_NAME:?'NO SYSTEM NAME'}"
LOG=${1:=log/${HERCULES_NAME}}.log
LOG_DIRECTORY=`dirname ${LOG}`

[ -d ${LOG_DIRECTORY} ]		|| mkdir -p ${LOG_DIRECTORY}
[ -d "$(dirname ${BINARY})" ]	|| mkdir -p "$(dirname ${BINARY})"

# We always remove because path to original may have changed
if [ -x "${BINARY}" ]; then
	rm "${BINARY}"
fi
ln -s "$(which hercules)" "${BINARY}"

# echo "${BINARY}" -f ${HERCULES_NAME}.conf ">" ${LOG}
# exec "${BINARY}" -f ${HERCULES_NAME}.conf > ${LOG}

echo "${BINARY}" -f ${HERCULES_NAME}.conf 
exec "${BINARY}" -f ${HERCULES_NAME}.conf
