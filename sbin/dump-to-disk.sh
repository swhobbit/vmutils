#/bin/sh
NOW=`date +%F_%H.%M.%S`
TARGET_DIRECTORY=/export/backup
INCREMENTAL_TOUCH_FILE="${TARGET_DIRECTORY}/status-backup-$(hostname -s).touch"
DAY_OF_WEEK=$(date +"%w")

if mount | fgrep -q " /export/backup " ; then 
 : No operation  
else 
 echo "Backup directory ${TARGET_DIRECTORY} is not mounted on its own file system, exiting."
 exit 99
fi

if [ -d /boot/grub ] ; then
  BOOT="boot/grub"
else
  BOOT="boot/*.txt"
fi

if [ -d /usr/local/home ] ; then
   LOCAL_HOME=usr/local/home
elif [ -d /home/hercules ] ; then
   LOCAL_HOME=home/hercules
else
   LOCAL_HOME=
fi

if [ -d /export/git ] ; then
   LOCAL_GIT=export/git
else
   LOCAL_GIT=
fi

chmod go= ${TARGET_DIRECTORY}
umask 0077

# delete obsolete touch files (which will force a full backup)
find ${TARGET_DIRECTORY} -name "status-backup-*.touch" -daystart -mtime +6 -ls -delete
find ${TARGET_DIRECTORY} -name "`basename ${INCREMENTAL_TOUCH_FILE}`" -daystart -mtime +6 -ls -delete

# Take a full backup on each Monday (or when status file gets old), and
# incremental dumps based on that dump.

### if [ ! -f ${INCREMENTAL_TOUCH_FILE} -o ${DAY_OF_WEEK} -eq 1 ] ; then

if [ ! -f ${INCREMENTAL_TOUCH_FILE} ] ; then
    touch "${INCREMENTAL_TOUCH_FILE}"
    INCREMENTAL_OPTION=""
    BACKUP_TYPE=full
else
    INCREMENTAL_OPTION="--newer-mtime ${INCREMENTAL_TOUCH_FILE}"
    BACKUP_TYPE=diff
fi

if [ -d ${TARGET_DIRECTORY} ] ; then
  dpkg -l > /etc/current-package-list.txt
  cd /
  exec tar	\
	-c	\
	--use-compress-program=pigz	\
	--file ${TARGET_DIRECTORY}/dump-$(hostname -s)-${NOW}-${BACKUP_TYPE}.tgz	\
	${INCREMENTAL_OPTION}	\
	--exclude=.cache	\
	--exclude=backup	\
	--one-file-system	\
	--atime-preserve	\
	--acls		\
	$@	\
	${BOOT}	\
	etc	\
	export	\
	home	\
	${LOCAL_HOME}	\
	${LOCAL_GIT}	\
	usr/local/bin	\
	usr/local/sbin
else
  echo ${TARGET_DIRECTORY} does not exist
  exit 99
fi
