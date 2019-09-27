# vim: ts=8 noexpandtab

sample/molson/%:  ${HOME}/hercules/molson/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"

all:   	binary

binary:	bin/vmsubmit.py

samples: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc 

bin sample/molson:
	mkdir -p $@
