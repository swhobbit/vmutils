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

BINARY_LINK="${HOME}/bin/hercules.d/${HERCULES_NAME:?'NO SYSTEM NAME SET'}"
LOG_DIRECTORY=log
LOG_PATH=${LOG_DIRECTORY}/hercules-${HERCULES_NAME}.log

SYSLOG_PATH=${LOG_DIRECTORY}/syslog-${HERCULES_NAME}.log

SCRATCH_PATH="../scratch/${HERCULES_NAME:?'NO SYSTEM NAME SET'}/shadow"

# Check if we're already running under screen.
SCREEN_COUNT="`screen -ls ${HERCULES_NAME} | fgrep -w -c ${HERCULES_NAME}`"
if [ ${SCREEN_COUNT} -gt 1 ] ; then
  echo "Hercules ${HERCULES_NAME} already running! Exiting."
  screen -ls
  sleep 5
  exit 99
elif [ ${SCREEN_COUNT} -ne 1 ] ; then
  echo "Hercules ${HERCULES_NAME} not found in screen -ls output! Exiting."
  screen -ls
  sleep  5
  exit 99
fi

# Make sure we can find hercules binary
if [ -z $(which hercules) ] ; then
  echo "hercules binary not found! Exiting."
  sleep 5
  exit 98
fi

[ -d "${SCRATCH_PATH}" ]		|| mkdir -p "${SCRATCH_PATH}"
[ -d "${LOG_DIRECTORY}" ]		|| mkdir -p "${LOG_DIRECTORY}"
[ -d "$(dirname ${BINARY_LINK})" ]	|| mkdir -p "$(dirname ${BINARY_LINK})"

# We link to the real binary as under our system name; it makes the emulator
# show as the system name in ps. We always remove and relink because the
# path to the real binary may have changed locations.

if [ -x "${BINARY_LINK}" ]; then
	rm "${BINARY_LINK}" || ( sleep 5; exit 99)
fi

ln -s "$(which hercules)" "${BINARY_LINK}" || (sleep 5 ; exit 99)

if [ -s ${LOG_PATH} ] ; then
        OLD_LOG_PATH=${LOG_DIRECTORY}/hercules-${HERCULES_NAME}-$(date -r ${LOG_PATH} +%F_%H.%M.%S).log
        mv ${LOG_PATH} ${OLD_LOG_PATH}
else
        echo "No old ${LOG_PATH} exists.
fi

if [ -s ${SYSLOG_PATH} ] ; then
        OLD_SYSLOG_PATH=${LOG_DIRECTORY}/syslog-${HERCULES_NAME}-$(date -r ${SYSLOG_PATH} +%F_%H.%M.%S).log
        mv ${SYSLOG_PATH} ${OLD_SYSLOG_PATH}
else 
        echo "No old ${SYSLOG_PATH} exists.
fi

# Save time future for setting the clock on OS/MVT
export HERCULES_IPL_TIME="$(date +date=$(expr $(date +%y) + 100 - 28).%j,clock=%H.%M.%S)"

if fgrep --silent -i datestamp ${HERCULES_NAME}.conf ; then
        echo "${BINARY_LINK}" -f ${HERCULES_NAME}.conf ">" ${LOG_PATH}
        exec "${BINARY_LINK}" -f ${HERCULES_NAME}.conf > ${LOG_PATH}
else 
        # Spinhawk (old) hercules, no date on log info
        echo "${BINARY_LINK}" -f ${HERCULES_NAME}.conf "|" datestamp ">" ${LOG_PATH}
        "${BINARY_LINK}" -f ${HERCULES_NAME}.conf | datestamp.sh > ${LOG_PATH}
fi
