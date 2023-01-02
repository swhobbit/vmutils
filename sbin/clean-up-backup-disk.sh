#/bin/sh
MY_NAME="$(basename $0)"
SECONDS_PER_DAY=86400
DAYS_OF_DIFFERENTIAL_BACKUP=6

BACKUP_DIRECTORY=/export/backup
MIN_DAYS_TO_DELETE_AFTER=100
DAYS_TO_DELETE_AFTER=365
FULL_WEEKLY_DAYS_TO_DELETE_AFTER=90
DAILY_DIFFERENTIAL_DAYS_TO_DELETE_AFTER=30
CLEANED=false

# Percentage in use above which we start deleting ALL oldest backups
HIGH_WATER_PERCENT_IN_USE=90
# Once we start deleting all backups, delete down to this percentage
# in use
LOW_WATER_PERCENT_IN_USE="$(expr ${HIGH_WATER_PERCENT_IN_USE} \* 3 / 4)"

# Log an message to system log; if --stderr passed, will also log to stderr
log_message () {
	priority=$1
	shift

	logger	\
		--id=$$ \
		--tag=${MY_NAME}	\
		--priority daemon.${priority}	\
		"${@:?'No message specified'}"
}


# Log an error message to both system log and stderr
log_error () {
	log_message error --stderr "${@:?'No error message specified'}"
}

# Log a notice message to both system log and stderr
log_notice () {
	log_message notice --stderr "${@:?'No notice specified'}"
}


# Determine if directory is root directory of a file system
is_directory_fs_root () {
	target_directory=${1:?'No directory supplied.'}

	# Check target directory is its own file system
	findmnt ${target_directory}	> /dev/null
	return $?
}

# Report amount in use by directory
file_system_percent_in_use() {
	target_directory=${1:?'No directory supplied.'}
	echo `df ${target_directory} | awk '/dev/ {print $5}' | sed -e 's/%//'`
}


if [ ! -d ${BACKUP_DIRECTORY} ] ; then
	log_error "${BACKUP_DIRECTORY} does not exist"
	exit 99
fi

if [ -f ${BACKUP_DIRECTORY}/NO_BACKUP ] ; then
	log_notice "Backup disabled by ${BACKUP_DIRECTORY}/NO_BACKUP"
	exit 0
fi

# Check backup directory is its own file system
if is_directory_fs_root ${BACKUP_DIRECTORY} ; then
	 : No operation, backup directory is its own file system, which is good.
else
	log_error "Backup directory ${BACKUP_DIRECTORY} is not mounted on its own file system, exiting."
	exit 99
fi

# Determine if we have ANY backups
ls ${BACKUP_DIRECTORY}/dump-*-full.tgz 2>/dev/null > /dev/null
if [ 0 -ne $? ] ; then
	log_error "No backup found with name matching ${BACKUP_DIRECTORY}/dump-*-full.tgz"
	exit 2
fi

# Do monthly optional clean up; if we're truly low on space when we are
# not doing this clean up, some of these files may get scrubbed anywayc
# below.
if [ "$(date +%d)" -le 7 ] ; then

	# Clean up moderately old weekly backups of all types (leaving monthly)
	log_notice "Deleting weekly backups older than ${FULL_WEEKLY_DAYS_TO_DELETE_AFTER} days"
	find	\
		${BACKUP_DIRECTORY}	\
		-type f 	\
		-name 'dump-*.tgz'	\
		! -name 'dump-*-????-??-0[1-7]_*.tgz'	\
		-mtime +${FULL_WEEKLY_DAYS_TO_DELETE_AFTER}	\
		-ls	\
		-delete	\
		| sort -k 11
	echo ''

	# Clean up moderately old differential backups (leaving full)
	log_notice "Deleting differential backups older than ${DAILY_DIFFERENTIAL_DAYS_TO_DELETE_AFTER} days"
	find	\
		${BACKUP_DIRECTORY}	\
		-type f 	\
		-name 'dump-*-diff.tgz'	\
		-mtime +${DAILY_DIFFERENTIAL_DAYS_TO_DELETE_AFTER}	\
		-ls	\
		-delete	\
		| sort -k 11
	echo ''

	# Clean up moderately old incomplete backups (leaving completed)
	log_notice "Deleting incomplete backups older than ${DAYS_OF_DIFFERENTIAL_BACKUP} days"
	find	\
		${BACKUP_DIRECTORY}	\
		-type f 	\
		-name 'dump-*-temp-*.tgz'	\
		-mtime +${DAYS_OF_DIFFERENTIAL_BACKUP}	\
		-ls	\
		-delete	\
		| sort -k 11
	echo ''

	CLEANED=true

fi

# Determine date of oldest full backup
OLDEST_DUMP_FILE="`ls -rt ${BACKUP_DIRECTORY}/dump-*-full.tgz | fmt -1 | head -1`"
OLDEST_DUMP_EPOCH_DAY="$(expr $(date -r ${OLDEST_DUMP_FILE} +%s ) / ${SECONDS_PER_DAY} )"
CURRENT_EPOCH_DAY="$expr( $(date +%s) / ${SECONDS_PER_DAY} )"
DAYS_TO_DELETE_AFTER="$(expr $CURRENT_EPOCH_DAY - $OLDEST_DUMP_EPOCH_DAY - $DAYS_OF_DIFFERENTIAL_BACKUP )"

log_notice	\
	"Oldest backup ${OLDEST_DUMP_FILE} is" \
	"$(expr ${CURRENT_EPOCH_DAY} - ${OLDEST_DUMP_EPOCH_DAY} ) days old"

first_pass=true
ALLOWED_PERCENT_IN_USE=${HIGH_WATER_PERCENT_IN_USE}
while [ $(file_system_percent_in_use ${BACKUP_DIRECTORY}) -ge ${ALLOWED_PERCENT_IN_USE} ]	\
	&& [ ${DAYS_TO_DELETE_AFTER} -ge ${MIN_DAYS_TO_DELETE_AFTER} ]
do
	log_notice "Looking for backups ${DAYS_TO_DELETE_AFTER} days old to delete in ${BACKUP_DIRECTORY}"
	find	\
		${BACKUP_DIRECTORY}	\
		-maxdepth 1	\
		-name "dump-*.tgz"	\
		-type f	\
		-mtime +${DAYS_TO_DELETE_AFTER}	\
		-ls	\
		-delete	\
		| sort -k 11
	DAYS_TO_DELETE_AFTER="$(expr ${DAYS_TO_DELETE_AFTER} - $DAYS_OF_DIFFERENTIAL_BACKUP - 1)"
	ALLOWED_PERCENT_IN_USE=${LOW_WATER_PERCENT_IN_USE}
	first_pass=false
done

if $first_pass ; then
	log_notice "No backups deleted for space from ${BACKUP_DIRECTORY}."
else
	CLEANED=true
fi


if "${CLEANED}" ; then
	fstrim -v ${BACKUP_DIRECTORY}
	echo ' '
	df -h ${BACKUP_DIRECTORY}
fi

echo ' '
