# vim: ts=8 noexpandtab

# This Makefile pulls working files into this directory for archival
# via git.

sample/molson/%:  ${HOME}/hercules/molson/%
	cp -f "$<" "$@"

cron/%:  /etc/cron.d/%
	cp -f "$<" "$@"

sbin/%:  /usr/local/sbin/%
	cp -f "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp -f "$<" "$@"

common/%: ${HOME}/hercules/common/%
	cp -f "$<" "$@"

all:   	binary_files common_files cron_files

binary_files:	\
	bin	\
	bin/6to4_tunnel.sh	\
	bin/hercules_route_lcs.py	\
	bin/hercules.sh	\
	bin/spool.py	\
	bin/vmsubmit.py	\
	sbin	\
	sbin/cpu-temp.sh	\
	sbin/clean-up-backup-disk.sh	\
	sbin/dump-to-backup-disk.sh

common_files:	common	\
	common/kew-herclogo.txt	\
	common/hercules-370-common.conf	\
	common/hercules-under-screen.rc	\
	common/screen-hercules.rc

cron_files:	\
	cron	\
	cron/cpu-temp	\
	cron/dump

samples_files: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc

cron bin sbin common sample/molson:
	mkdir -p $@
