#/bin/sh
MYNAME="$(basename $0)"

BACKUP_DIRECTORY=/export/backup
MIN_DAYS_TO_DELETE=100
DAYS_OF_DIFFERENTIAL_BACKUP=6
DAYS_TO_DELETE=365
FULL_WEEKLY_DAYS_TO_DELETE=90
DAILY_DIFFERENTIAL_DAYS_TO_DELETE=30
MAX_PERCENT_IN_USE=90
SECONDS_PER_DAY=86400

# Log an message to system log; may also log to system error if --stderr passed
log_message () {
	priority=$1
	shift

	logger	\
		--id=$$ \
		--tag=${MYNAME}	\
		--priority daemon.${priority}	\
		"$@"
}


# Log an error message to system log and stderr
log_error() {
	log_message error --stderr "$@"
}

# Log an notice message to system log; may also log to system error --stderr passed
log_notice() {
	log_message notice --stderr "$@"
}


# Determine if directory is root directory of a file system
is_directory_fs_root () {
	root_directory=${1:?["No directory supplied."]}

	# Check backup directory is its own file system
	if mount | fgrep -q " ${root_directory} " ; then
	 	# directory is its own file system
	 	return 0
	else
		# directory is a child directory
		return 1
	fi
}


if [ ! -d ${BACKUP_DIRECTORY} ] ; then
  log_error ${BACKUP_DIRECTORY} does not exist
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

# Determine if we have any backups
ls ${BACKUP_DIRECTORY}/dump-*-full.tgz 2>/dev/null > /dev/null
if [ 0 -ne $? ] ; then
 log_error "No backup found with name matching ${BACKUP_DIRECTORY}/dump-*-full.tgz"
 exit 2
fi

# Clean up moderately old weekly backups of all types (leaving monthly)
log_notice "Deleting weekly backups older than ${FULL_WEEKLY_DAYS_TO_DELETE} days"
find	\
	${BACKUP_DIRECTORY}	\
	-type f 	\
	-name 'dump-*.tgz'	\
	! -name 'dump-*-????-??-0[1-7]_*.tgz'	\
	-mtime +${FULL_WEEKLY_DAYS_TO_DELETE}	\
	-ls	\
	-delete	\
	| sort -k 11
echo ''


# Clean up moderately differential backups (leaving full)
log_notice "Deleting differential backups older than ${DAILY_DIFFERENTIAL_DAYS_TO_DELETE} days"
find	\
	${BACKUP_DIRECTORY}	\
	-type f 	\
	-name 'dump-*-diff.tgz'	\
	-mtime +${DAILY_DIFFERENTIAL_DAYS_TO_DELETE}	\
	-ls	\
	-delete	\
	| sort -k 11
echo ''

# Determine date of oldest full backup
OLDEST_DUMP_FILE="`ls -rt ${BACKUP_DIRECTORY}/dump-*-full.tgz | fmt -1 | head -1`"
OLDEST_DUMP_DATE="$(expr $(date -r ${OLDEST_DUMP_FILE} +%s ) / ${SECONDS_PER_DAY} )"
CURRENT_DATE="$expr( $(date +%s) / ${SECONDS_PER_DAY} )"
DAYS_TO_DELETE="$(expr $CURRENT_DATE - $OLDEST_DUMP_DATE - $DAYS_OF_DIFFERENTIAL_BACKUP )"

log_notice	\
	"Oldest backup ${OLDEST_DUMP_FILE} is" \
	"$(expr $CURRENT_DATE - $OLDEST_DUMP_DATE ) days old"

first_pass=true 
while [ `df ${BACKUP_DIRECTORY} | awk '/dev/ {print $5}' | sed -e 's/%//'` -ge ${MAX_PERCENT_IN_USE} ]	\
	&& [ ${DAYS_TO_DELETE} -ge ${MIN_DAYS_TO_DELETE} ]
do
        log_notice "Looking for any backups to delete in ${BACKUP_DIRECTORY} older than ${DAYS_TO_DELETE} days"
	find	\
		${BACKUP_DIRECTORY}	\
		-maxdepth 1	\
		-name "dump-*.tgz"	\
		-type f	\
		-mtime +${DAYS_TO_DELETE}	\
		-ls	\
		-delete	\
		| sort -k 11
	DAYS_TO_DELETE="$(expr ${DAYS_TO_DELETE} - $DAYS_OF_DIFFERENTIAL_BACKUP - 1)"
	first_pass=false
done

if $first_pass ; then 
	log_notice "No backups needed to be unconditionally deleted from ${BACKUP_DIRECTORY}."
fi

echo ' '
df -h ${BACKUP_DIRECTORY} | log_notice
echo ' '
