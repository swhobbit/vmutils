# vim: ts=8 noexpandtab

sample/molson/%:  ${HOME}/hercules/molson/%
	cp "$<" "$@"

cron/%:  /etc/cron.d/%
	cp "$<" "$@"

sbin/%:  /usr/local/sbin/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"

common/%: ${HOME}/hercules/common/%
	cp "$<" "$@"

all:   	binary_files common_files cron_files

binary_files:	\
	bin	\
	bin/6to4_tunnel.sh	\
	bin/hercules_route_lcs.py	\
	bin/hercules.sh	\
	bin/spool.py	\
	bin/vmsubmit.py	\
	sbin	\
	sbin/dump-to-disk.sh

common_files:	common	\
	common/hercules-370-common.conf	\
	common/hercules-under-screen.rc	\
	common/screen-hercules.rc

cron_files:	\
	cron	\
	cron/dump

samples_files: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc 

cron bin sbin common sample/molson:
	mkdir -p $@
