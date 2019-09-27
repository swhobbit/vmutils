# vim: ts=8 noexpandtab

sample/molson/%:  ${HOME}/hercules/molson/%
	cp "$<" "$@"

sample/olivia/%:  ${HOME}/hercules/olivia/%
	cp "$<" "$@"

sample/veronica/%:  ${HOME}/hercules/veronica/%
	cp "$<" "$@"

sample/victoria/%:  ${HOME}/hercules/victoria/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"

all:   	binary samples

binary:	bin/vmsubmit.py

samples: 	sample/molson	\
        sample/molson/hercules.window.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc 

bin sample/molson:
	mkdir -p $@
