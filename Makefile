# vim: ts=8 noexpandtab

sample/molson/%:  ${HOME}/hercules/molson/%
	cp "$<" "$@"

sbin/%:  /usr/local/sbin/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"

common/%: ${HOME}/hercules/common/%
	cp "$<" "$@"

all:   	binary_files common_files

binary_files:	bin	\
	sbin	\
	sbin/dump-to-disk.sh	\
	bin/vmsubmit.py	\
	bin/hercules.sh	\
	bin/6to4_tunnel.sh	\
	bin/hercules.sh	\
	bin/hercules_route_lcs.py

common_files:	common	\
	common/hercules-370-common.conf	\
	common/hercules-under-screen.rc	\
	common/screen-hercules.rc

samples_files: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc 

bin sbin common sample/molson:
	mkdir -p $@
