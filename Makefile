# vim: ts=8 noexpandtab

sample/molson/%:  ${HOME}/hercules/molson/%
	cp "$<" "$@"

sbin/%:  /usr/local/sbin/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"



all:   	binary

binary:	bin	\
	sbin	\
	sbin/dump-to-disk.sh	\
	bin/vmsubmit.py	\
	bin/hercules.sh	\
	bin/6to4_tunnel.sh	\
	bin/hercules.sh	\
	bin/hercules_route_lcs.py

samples: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc 

bin sbin sample/molson:
	mkdir -p $@
