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

if [ "${USER}" != "hercules" ] ; then 
        echo "Script $0 must be run as user hercules"
        sleep 2
        exit 88
fi

export  SCRATCH_DIRECTORY="../scratch/${HERCULES_NAME:?'NO SYSTEM NAME SET'}/shadow"
LOG_DIRECTORY=log

BINARY_LINK="../bin.d/${HERCULES_NAME:?'NO SYSTEM NAME SET'}"
LOG_PATH=${LOG_DIRECTORY}/hercules-${HERCULES_NAME}.log

SYSLOG_PATH=${LOG_DIRECTORY}/syslog-${HERCULES_NAME}.log

# Check if an instance with this name is already running under screen.
SCREEN_COUNT="`screen -ls ${HERCULES_NAME} | fgrep -w -c ${HERCULES_NAME}`"
if [ ${SCREEN_COUNT} -gt 1 ] ; then
  echo "Hercules ${HERCULES_NAME} already running! Exiting."
  echo ''
  screen -ls
  sleep 3
  exit 99
elif [ ${SCREEN_COUNT} -ne 1 ] ; then
  echo "Hercules ${HERCULES_NAME} not found in screen -ls output! Exiting."
  echo ''
  screen -ls
  sleep  3
  exit 99
fi

# Make sure we can find hercules binary
if [ -z $(which hercules) ] ; then
  echo "hercules binary not found! Exiting."
  echo ''
  sleep 3
  exit 98
fi

for directory in        \
        .       \
        dasd    \
        print   \
        punch   \
        shadow  \
        ${LOG_DIRECTORY}        \
        "${SCRATCH_DIRECTORY}"  \
        "$(dirname ${BINARY_LINK})" ; do
        [ -d "${directory}" ] || mkdir -p "${directory}" || (sleep 5 ; exit 99)
        if [ -w "${directory}" ] ; then
                # No op
                echo
        else
                echo "Directory ${directory} is not writable."
                sleep 5
                exit 99
        fi
done

# We link to (and use) the real binary under our system name; it makes
# the emulator show as the system name in ps. We always remove and relink
# because the path to the real binary may have changed locations.

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

# If HERCULES_ADDRESS is not set, translate HERCULES_HOST into an address
# (with a generic default) for network connections.

if [ -z "${HERCULES_ADDRESS}" ] && [ -n "${HERCULES_HOST}" ] ; then

        TEMP_ADDRESS="`host ${HERCULES_HOST} | awk '/has address/ { print $4}'`"
        if [ -n "${TEMP_ADDRESS}" ] ; then
                export HERCULES_ADDRESS="${TEMP_ADDRESS}"
                sudo ip -4 addr add ${HERCULES_ADDRESS}/16 dev eth0
        else
                export HERCULES_ADDRESS="0.0.0.0"
        fi
fi

PATH="$(dirname ${BINARY_LINK}):${PATH}"
BINARY_BASENAME="$(basename ${BINARY_LINK})"

if [ ".${HERCULES_VERSION}" = ".spinhawk" ] ; then
        # Spinhawk (old) hercules, no date on log info
        echo "${BINARY_BASENAME}" -f ${HERCULES_NAME}.conf "|" datestamp ">" ${LOG_PATH}
        "${BINARY_BASENAME}" -f ${HERCULES_NAME}.conf | datestamp.sh > ${LOG_PATH}
else
        echo HERCULES_RC=../common/shadow-hercules-under-screen.rc "${BINARY_BASENAME}" -f ${HERCULES_NAME}-dasd-io.conf ">" ${LOG_PATH}
        HERCULES_RC=../common/shadow-hercules-under-screen.rc "${BINARY_BASENAME}" -f ${HERCULES_NAME}-dasd-io.conf > ${LOG_PATH} || (sleep 5 ; exit 99)
        echo "${BINARY_BASENAME}" -f ${HERCULES_NAME}.conf ">>" ${LOG_PATH}
        exec "${BINARY_BASENAME}" -f ${HERCULES_NAME}.conf >> ${LOG_PATH}
fi
