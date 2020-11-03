#!/bin/sh

# vim:	ts=8 sw=8 expandtab

# *------------------------------------------------------------------- *
# *                          hercules.sh                               *
# *                                                                    *
# *			Run Hercules (assuming we are invoked under    *
# *			screen) for a specific emulated machine        *
# *			takeing care to:			       *
# *								       *
# *			1) Set the name of the executable to the       *
# *  			   name of the machine via a link.	       *
# *			2) Verify this is the only session of screen   *
# *			   running with the name of executable.	       *
# *			3) Enable logging			       *
# *                                                                    *
# *              Date: 19 Sep 2019                                     *
# *            Author: ahd@kew.com (Drew Derbyshire)                   *
# *           Address: Kendra Electronic Wonderworks                   *
# *                    Kenmore, WA                                     *
# *------------------------------------------------------------------- *

BINARY_LINK="${HOME}/bin/hercules/${HERCULES_NAME:?'NO SYSTEM NAME SET'}"
LOG_DIRECTORY=log
LOG_PATH=${LOG_DIRECTORY}/hercules-${HERCULES_NAME}.log

# Check if we're already running under screen.
SCREEN_COUNT="`screen -ls ${HERCULES_NAME} | fgrep -w -c ${HERCULES_NAME}`"
if [ ${SCREEN_COUNT} -gt 1 ] ; then
  echo "Hercules ${HERCULES_NAME} already running!"
  screen -ls
  sleep 10
  exit 99
elif [ ${SCREEN_COUNT} -ne 1 ] ; then
  echo "Hercules ${HERCULES_NAME} not found in screen -ls output!"
  screen -ls
  sleep  10
  exit 99
fi

[ -d ${LOG_DIRECTORY} ]		|| mkdir -p ${LOG_DIRECTORY}
[ -d "$(dirname ${BINARY_LINK})" ]	|| mkdir -p "$(dirname ${BINARY_LINK})"

# We link to the real binary as under our system name; it makes the emulator
# show as the system name in ps. We always remove and relink because the
# path to the real binary may have changed locations.

if [ -x "${BINARY_LINK}" ]; then
	rm "${BINARY_LINK}"
fi

ln -s "$(which hercules)" "${BINARY_LINK}"

echo "${BINARY_LINK}" -f ${HERCULES_NAME}.conf ">" ${LOG_PATH}
"${BINARY_LINK}" -f ${HERCULES_NAME}.conf > ${LOG_PATH}
