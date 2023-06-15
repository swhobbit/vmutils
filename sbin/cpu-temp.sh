#!/bin/sh

# Print the CPU temperature if it's changed.

# Raspberry Pi location of temp
TEMPERATURE_FILE=/sys/class/thermal/thermal_zone0/temp
BASENAME=$(basename $0)
ROOT_NAME=/var/run/${BASENAME}.previous

# Don't run if we can't read the CPU temperature
if [ ! -r ${TEMPERATURE_FILE} ]
then
	exit 99
fi

# Fetch the opreviously read temperature, or t set to 0 if we don't have
# it (for example, after a reboot).
if [ -f ${ROOT_NAME} ]
then
	read OLD_TEMP < ${ROOT_NAME}
else
        OLD_TEMP=0
fi

# Also get current temperature
read NEW_TEMP < ${TEMPERATURE_FILE}

# Compute positive delta between the lower and higher temperatures
if [ ${OLD_TEMP} -ge ${NEW_TEMP} ]
then
	DELTA=`expr ${OLD_TEMP} - ${NEW_TEMP}`
else
	DELTA=`expr ${NEW_TEMP} - ${OLD_TEMP}`
fi

# Report save and new temperature if it's up or down one full degree
# since we last reported and saved it.
if [ ${DELTA} -ge 1000 ]
then
	printf 'CPU temperature %d.%d%s'	\
		$(expr ${NEW_TEMP} / 1000)	\
		$(expr $(expr ${NEW_TEMP} % 1000) / 100)	\
		'ᴼC'	\
		| logger --id=$$ -t ${BASENAME} -p daemon.info
	echo ${NEW_TEMP} > ${ROOT_NAME}
fi
