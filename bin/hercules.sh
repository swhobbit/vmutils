#!/bin/sh
BINARY_LINK="${HOME}/bin/hercules/${HERCULES_NAME:?'NO SYSTEM NAME SET'}"
LOG_DIRECTORY=log
LOG=${LOG_DIRECTORY}/${HERCULES_NAME}.log

# Check if we're already running under screen.
SCREEN_COUNT="`screen -ls ${HERCULES_NAME} | grep -c ${HERCULES_NAME}`"
if [ ${SCREEN_COUNT} -gt 1 ] ; then 
  echo "Hercules ${HERCULES_NAME} already running!"
  sleep 5
  exit 99
elif [ ${SCREEN_COUNT} -ne 1 ] ; then                                             
  echo "Hercules ${HERCULES_NAME} not found in screen -ls output!" 
  sleep 5
  exit 99 
fi

[ -d ${LOG_DIRECTORY} ]		|| mkdir -p ${LOG_DIRECTORY}
[ -d "$(dirname ${BINARY_LINK})" ]	|| mkdir -p "$(dirname ${BINARY_LINK})"


#  We do a link to the real binary because this makes the emulator show as
#  the system name in ps. We always remove and relink because the path to
#  original may have changed locations.
if [ -x "${BINARY_LINK}" ]; then
	rm "${BINARY_LINK}"
fi
ln -s "$(which hercules)" "${BINARY_LINK}"

echo "${BINARY_LINK}" -f ${HERCULES_NAME}.conf 
exec "${BINARY_LINK}" -f ${HERCULES_NAME}.conf
