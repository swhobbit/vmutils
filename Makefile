# vim: ts=8 noexpandtab

sample/molson/%:  sample/molson	${HOME}/hercules/molson/%
	cp "$<" "$@"

sample/olivia/%:  sample/olivia	${HOME}/hercules/olivia/%
	cp "$<" "$@"

sample/veronica/%:  sample/veronica	${HOME}/hercules/veronica/%
	cp "$<" "$@"

sample/victoria/%:  sample/victoria	${HOME}/hercules/victoria/%
	cp "$<" "$@"

bin/%:  ${HOME}/bin/%
	cp "$<" "$@"

all:   	binary samples

binary:	bin/vmsubmit.py

samples: 	sample/victoria sample/veronica sample/olivia sample/molson	\
        sample/molson/hercules.windows.rc    \
        sample/molson/molson.conf  \
        sample/molson/screen.rc      \
        sample/olivia/hercules.windows.rc    \
        sample/olivia/olivia.conf  \
        sample/olivia/screen.rc      \
        sample/veronica/hercules.windows.rc    \
        sample/veronica/hercules.windows.rc    \
        sample/veronica/hercules.windows.rc    \
        sample/veronica/screen.rc      \
        sample/veronica/screen.rc      \
        sample/veronica/screen.rc      \
        sample/veronica/veronica.conf  \
        sample/veronica/veronica.conf  \
        sample/veronica/veronica.conf  \
        sample/victoria/hercules.windows.rc    \
        sample/victoria/screen.rc      \
        sample/victoria/victoria.conf 

bin sample/victoria sample/veronica sample/olivia sample/molson:
	mkdir -p $@
