#!/usr/bin/env bash

#                            BUILD SH
#                      hercules-config-kew.sh
#
#            Perform customized optiimized build for hercules of a Rasperry Pi
#
#               Date: 5 Jan 2022
#             Author: ahd@kew.com (Drew Derbyshire)
#            Address: Kendra Electronic Wonderworks
#                     Kenmore, WA

#	This script is a shorthand method of running configure with a
#	specific set of options, including a custom version string which
#	indicates the current git branch name and commit count.

#	Things this does:
#	- Passes any command line arguments directly to ./configure
#	- Delivers the binaries to directories under /usr/local/spimhawk or
#	  /use/local/hyerpion
#	- Use clang-9, clang, or gcc in that order.
#	- Allows (subject o te actual build support) to shared (dymanic) or static
#	  libraries.
#	- For ARM processor builds under Linux Optimizes the build according to
#	  the Raspberry Pi reported.
#	- Run paraellal make for the number of processors reported on the system.

#    This should work on a X86 running Linux, but no special optimizations are
#	done.

#	To use, switch to the root directory of the source respository, and run
#	this command.

#	Copy this file to ./config and edit the options as required.
#	This allows you to specify your own site-specific prefix and
#	other preferences in a file not tracked by git.

git status  > /dev/null
RC=${?}

if [ 0 -ne ${RC} ] ; then
	echo ''
	echo "git status failed (rc = ${RC}), is this a valid repository?"
	exit ${RC}
fi

TAG="$(head -1 <<< "$(git tag --sort='-*authordate')" )"
if  grep -E "(^|[^\\d.])4\\." <<< "${TAG}" ; then
	 EDITION=hyperion
elif grep -E '(^|[^\\d.])3\\.' <<< "${TAG}" ; then
	 EDITION=spinhawk
elif [ "hyperion" = "$(basename "$(pwd)" )" ] ; then
	 EDITION=hyperion
elif [ "spinhawk" = "$(basename "$(pwd)" )" ] ; then
	 EDITION=spinhawk
else
	 EDITION=spinhawk
fi

###
###	Options we like to change
###

# Or just hard code gcc if you prefer it.
if [ -x /usr/bin/clang-9 ] ; then
	CC=clang-9
elif [ -x /usr/bin/clang-9 ] ; then
	CC=clang
else
	CC=gcc
fi
# CC=gcc


silent=				#	--silent
static=false		# 	static=true may not work with some of versions Hercules!
build_prefix=/usr/local

# Static may not work with some versions of Hercules!
if ${static} ; then
	CUSTOM_LIB="static_libraries"
else
	CUSTOM_LIB="shared_libraries"
fi

VERSION=$(awk -F"[(,)]" '/^AM_INIT_AUTOMAKE/ {print $3}' configure.ac)
BUILT_LOCATION="${LOGNAME}@$(hostname):$(pwd)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT_COUNT="$(wc -l <<< "$(git log --oneline)" )"
CUSTOM="${BUILT_LOCATION}-${VERSION}-${CUSTOM_LIB}-${BRANCH}-${COMMIT_COUNT}"

build_prefix="${build_prefix}/${EDITION}"

declare -a build_options
declare -a build_optimizations
declare -a gcc_build_optimizations

build_options=(
	"${build_options[@]}"
	"CC=${CC}"
	"--prefix=${build_prefix}"
	"--enable-custom=${CUSTOM}"
	"${silent}"
	"--enable-setuid-hercifc=hercules"
	"--enable-cckd-bzip2"
	"--enable-het-bzip2"
	"--disable-external-gui"
	"--disable-silent-rules"
	"--enable-multi-cpu=4"
	)

build_optimizations=(
	"-O3"
	"-pipe"
	)

gcc_build_optimizations=(
	"-frename-registers"
	)

# Static libraries may not work with some versions of Hercules!
if ${static} ; then
	build_options=(
		"${build_options[@]}"
	 	--enable-static
	 	--disable-shared
	)
fi

if [ "hyperion" = "${EDITION}" ] ; then
	build_options=(
		"${build_options[@]}"
		"--enable-extpkgs=${build_prefix}"
		)
fi

if [ "x86_64" = "$(uname -m)" ] ; then
	# No special options
	:
elif [ "GNU/Linux" != "$(uname -o)" ] ; then
	echo "$0 doesn't know how to configure for OS $(uname -o) on $(uname -m)!"
	exit 97
else
	# We assume Raspberry Pi ARM
	build_optimizations=(
		"${build_optimizations[@]}"
		"-mfloat-abi=hard"
		)

	# Raspberry Pi ARM has many flavors, we customize by model.
	# https://gist.github.com/fm4dd/c663217935dc17f0fc73c9c81b0aa845
	MODEL="$(sed -E -e 's/Model.+: Raspberry Pi (Compute Module )?([0-9]|Zero).+$/\2/' <<< "$(grep '^Model'	/proc/cpuinfo)" )"

	if [ "Zero" = "${MODEL}" ] || [ "1" -eq "${MODEL}" ]; then
		build_optimizations=(
			"${build_optimizations[@]}"
			"-mcpu=arm1176jzf-s"
			"-mtune=arm1176jzf-s"
			"-mfpu=vfp"
			"-mtune=arm1176jzf-s"
			)
	elif [ "2" -eq "${MODEL}" ] ; then
		build_optimizations=(
			"-mcpu=cortex-a7"
			"-mfloat-abi=hard"
			"-mfpu=neon-vfpv4"
			"-mtune=cortex-a7"
		)
	elif [ "3" -eq "${MODEL}" ] ; then
		build_optimizations=(
			"${build_optimizations[@]}"
			"-mcpu=cortex-a53"
			"-mtune=cortex-a53"
			)
		gcc_build_optimizations=(
			"${gcc_build_optimizations[@]}"
			"-mneon-for-64bits"
			)
	elif [ "4" -eq "${MODEL}" ] ; then
		build_optimizations=(
			"${build_optimizations[@]}"
			"-mcpu=cortex-a72"
			"-mtune=cortex-a72"
			"-mfpu=neon-fp-armv8"
			"-mtune=cortex-a72"
		)
		gcc_build_optimizations=(
			"${gcc_build_optimizations[@]}"
			"-mneon-for-64bits"
			)
	elif [ "" = "${MODEL}" ] ; then
		echo "$0 doesn't know how to read model on OS $(uname -o) on $(uname -m)!"
		exit 98
	else
		echo "$0 doesn't know the optimizations for Raspberry Pi ${MODEL}"
		exit 98
	fi
fi

if [ ${CC} = "gcc" ] ; then
	build_optimizations=(
		"${build_optimizations[@]}"
		"${gcc_build_optimizations[@]}"
		)
fi

echo ""
uname -a
echo ""

./util/bldlvlck || exit $?
echo ""

# From Hyperion build instructions:
# 	Please note that SDL Hyperion comes pre-delivered with an already
# 	pre-generated ./configure script, so doing a ./autogen.sh is not
# 	necessary and is in fact now strongly discouraged.
#
# Thus, we run autogen.ah for spinhawk only.
if [ "spinhawk" = "${EDITION}" ] ; then
	echo ""
	chmod a+x autogen.sh
	./autogen.sh || exit $?
fi

quoted_build_optimizations="$(awk '{$1=$1;print}' <<< "${build_optimizations[@]}" )"

# shellcheck disable=SC2086
echo Build options: "${build_options[@]}" --enable-optimization=\"${quoted_build_optimizations}\" "${@}"
echo ""

# shellcheck disable=SC2086
# shellcheck disable=SC2068
time ./configure ${build_options[@]} --enable-optimization="${quoted_build_optimizations}" "${@}" || exit $?
echo ""

# Prevent libtool from failing the build because of its own brain damage
sed	\
	-i.bak	\
	-E	\
	-e 's/deplibs_check_method=".+"/deplibs_check_method="pass_all"/'	\
	libtool	\
	|| exit $?

time make clean || exit $?
echo ""

if [ -x /usr/bin/nproc ] ; then
	make_opt="-j $(nproc)"
else
	make_opt=""
fi

time make ${make_opt}
exit $?
