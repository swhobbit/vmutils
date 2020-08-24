#/bin/sh
NOW=`date +%F_%H.%M.%S`
BACKUP_DIRECTORY=/export/backup
DIFFERENTIAL_TOUCH_FILE="${BACKUP_DIRECTORY}/status-backup-$(hostname -s).touch"
DAY_OF_WEEK=$(date +"%w")
MYNAME="`basename $0`"

# Log an message to system log; may also log to system error --stderr passed
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
	log_message notice "$@"
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

# Always record current package list
dpkg -l > /etc/current-package-list.txt

if [ ! -d ${BACKUP_DIRECTORY} ] ; then
  log_error ${BACKUP_DIRECTORY} does not exist
  exit 99
fi

if [ -f ${BACKUP_DIRECTORY}/NO_BACKUP ] ; then
  log_notice "Backup disabled by ${BACKUP_DIRECTORY}/NO_BACKUP"
  exit 0
fi

# Check backup directory is its own file system
if is_directory_fs_root  ${BACKUP_DIRECTORY} ; then 
 : No operation, backup directory is its own file system, which is good.
else 
 log_error "Backup directory ${BACKUP_DIRECTORY} is not mounted on its own file system, exiting."
 exit 99
fi

# Prevent non-root backups to the directory and its files
chmod go= ${BACKUP_DIRECTORY}
umask 0077

# Delete obsolete (over 6 days old) touch files (which will force a
# full backup)
find ${BACKUP_DIRECTORY} -name "`basename ${DIFFERENTIAL_TOUCH_FILE}`" -daystart -mtime +6 -ls -delete

# Take a full backup when status file does not exist (see above), and
# differential dumps based on that dump.

if [ ! -f ${DIFFERENTIAL_TOUCH_FILE} ] ; then
  # Note that it's not the official touch file until backup completes.
  touch "${DIFFERENTIAL_TOUCH_FILE}.new"
  INCREMENTAL_OPTION=""
  BACKUP_TYPE=full
else
  INCREMENTAL_OPTION="--newer-mtime ${DIFFERENTIAL_TOUCH_FILE}"
  BACKUP_TYPE=diff
fi

cd /
DIRECTORIES=""
# Determine what directories to backup.  
#
# (That it is, don't call cause errors by trying to backup things which
# do not exist on the current system.

# Directories only backed up if their own file system
for entry in	\
      export/git	\
      home/hercules
  do
    # Note leading slash added for fs check
    if is_directory_fs_root /${entry} ; then
      DIRECTORIES="${DIRECTORIES} ${entry}"
    fi
  done

# Directories/files backed up unconditionally.  
#
# NOTE: The directories are not de-dupped by tar; for example, if
#       fee/fie is on the same file system as fee, it will get
#       backed up twice. 
for entry in	\
	boot/grub	\
	boot/*.txt	\
	${BOOT}	\
	etc	\
	export	\
	home	\
	usr/local/bin	\
	usr/local/home	\
	usr/local/sbin
  do
    if [ -d ${entry} -o -f ${entry} ] ; then
      DIRECTORIES="${DIRECTORIES} ${entry}"
    fi
  done

log_notice "Executing ${BACKUP_TYPE} backup for ${DIRECTORIES}"

tar	\
      --create	\
      --use-compress-program=pigz	\
      --file ${BACKUP_DIRECTORY}/dump-$(hostname -s)-${NOW}-${BACKUP_TYPE}.tgz	\
      ${INCREMENTAL_OPTION}	\
      --exclude=.cache	\
      --exclude=backup	\
      --one-file-system	\
      --atime-preserve	\
      --acls		\
      $@	\
      ${DIRECTORIES}
TAR_RETURN_CODE=$?

# If backup is clean, and we have a new differential timestamp, make it
# the real one.
if [ ${TAR_RETURN_CODE} -ne 0 ] ; then 
  log_error Backup failed, return code ${TAR_RETURN_CODE} 
elif [ -f "${DIFFERENTIAL_TOUCH_FILE}.new" ] ; then
  mv "${DIFFERENTIAL_TOUCH_FILE}.new" "${DIFFERENTIAL_TOUCH_FILE}" 
  log_notice --stderr ${BACKUP_TYPE} complete, and be will the baseline for differential backups.
else 
  log_notice ${BACKUP_TYPE} backup complete.
fi

exit ${TAR_RETURN_CODE}
