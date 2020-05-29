#!/bin/bash

function usage
{
  echo "Usage: $0 [-h] [--from REV] [--to REV] [-c REV]"
  echo
  echo "Run cppcheck on the files modified between two Mercurial revisions."
  echo "By default, it will only process uncommited changes (what you see"
  echo "when you do hg diff, aka --from tip)."
  echo
  echo "Options:"
  echo "  --from REV       Revision to start from (NOT inclusive, only changes"
  echo "                   introduced AFTER this revision will be considered."
  echo "                   Use p1(REV) to start from the first parent."
  echo "                   See 'hg help revset' for more details."
  echo "  --to REV         Last revision to consider (inclusive)."
  echo "  -c/--change REV  Consider changes introduced by this revision."
  echo "                   Equivalent to --from \"p1(REV)\" --to REV."
  echo "  -u/--untracked   Include untracked files."
  echo "  --exitcode       Exit code if findings are found (default is 0)."
  echo "  -h/--help        Print this help."
}

from=
to=
untracked=n
errorexitcode=0

while :; do
  case $1 in
    -h|--help)
      >&2 usage
      exit
      ;;
    --from)
      if [ -z "$2" ]; then
        >&2 echo '"--from" requires a non-empty argument.'
        exit 1
      fi
      from=$2
      shift
      ;;
    --to)
      if [ -z "$2" ]; then
        >&2 echo '"--to" requires a non-empty argument.'
        exit 1
      fi
      to=$2
      shift
      ;;
    -c|--change)
      if [ -z "$2" ]; then
        >&2 echo '"--change" requires a non-empty argument.'
        exit 1
      fi
      from="p1($2)"
      to=$2
      shift
      ;;
    -u|--untracked)
      untracked=y
      ;;
    --exitcode)
      if [ -z "$2" ]; then
        >&2 echo '"--exitcode" requires a non-empty argument.'
        exit 1
      fi
      errorexitcode=$2
      shift
      ;;
    *) # No more options, stop parsing arguments.
      break
  esac

  shift
done

cppcheck_filter() {
    local path=
    while read; do
        if [[ $REPLY =~ ^([^:]*):[0-9]+:[0-9]+: ]]; then
            echo "$REPLY" | grep -q -f $1
            if [[ $? -ne 0 ]]; then
                path=${BASH_REMATCH[1]}
                echo $REPLY
            else
                path=
            fi
        elif [[ -n $path ]]; then
            echo $REPLY
        fi
    done
}

run_cppcheck() {
    cppcheck -q --enable=style,performance,portability --language=c++ --inconclusive "$1" 2>&1 | cppcheck_filter "$FILTER_LINE_FILE"
}

HG_ROOT=`hg root`

if [ -z "$HG_ROOT" ] ; then
    echo "not an hg repo..."
    exit 1
fi

declare -a REV1_ARGS
declare -a REV2_ARGS

if [ -n "$from" ]; then
    REV1_ARGS+=('--rev' "$from")
fi

if [ -n "$to" ]; then
    REV2_ARGS+=('--rev' "$to")
fi

#echo rev1 "${REV1_ARGS[@]}"
#echo rev2 "${REV2_ARGS[@]}"

[[ "$untracked" = "y" ]] && U_ARG="-u" || U_ARG=""
ALTERED_FILES=$(hg status -R "$HG_ROOT" "${REV1_ARGS[@]}" "${REV2_ARGS[@]}" -m -a $U_ARG | grep -E '^[MA?].*\.(cpp|cxx|h|hxx)$' | sed 's/[MA?]\s//')

TMPDIR=/tmp/cppcheck-hook
mkdir -p "$TMPDIR"

FILTER_LINE_FILE=$TMPDIR/cppcheck-ignore
echo 'does not have a constructor
(information)
is not initialized in the constructor
C-style pointer casting
[Aa]ssert
convertion between' > $FILTER_LINE_FILE

rm -f "$TMPDIR/findings"

SAVEIFS=$IFS
IFS=$(echo -en "\n\b")
for i in $ALTERED_FILES
do
    >&2 echo "Running cppcheck on:  $i"


    mkdir -p `dirname "$TMPDIR/R/$i"`

    if [ -z "$to" ]; then
        cp "$HG_ROOT/$i" "$TMPDIR/R/$i"
    else
        hg cat -R "$HG_ROOT" "${REV2_ARG[@]}" "$HG_ROOT/$i" > "$TMPDIR/R/$i"
    fi

    pushd "$TMPDIR/R" > /dev/null
    run_cppcheck "$i" > "$TMPDIR/findings-r"
    popd > /dev/null


    if [ -n "$from" ]; then
        mkdir -p `dirname "$TMPDIR/L/$i"`

        pushd "$TMPDIR/L" > /dev/null
        cp "$TMPDIR/R/$i" "$TMPDIR/L/$i"
        hg diff -R "$HG_ROOT" "${REV1_ARGS[@]}" "${REV2_ARGS[@]}" "$HG_ROOT/$i" | patch -Rs -p1
        #hg cat -R "$HG_ROOT" "${REV1_ARGS[@]}" "$HG_ROOT/$i" > "$TMPDIR/L/$i"
        run_cppcheck "$i" > "$TMPDIR/findings-l"
        popd > /dev/null

        cppcheck-diff-findings.py "$TMPDIR/findings-l" "$TMPDIR/findings-r" >> "$TMPDIR/findings"
    else
        cat "$TMPDIR/findings-r" >> "$TMPDIR/findings"
    fi
done

exitcode=0

if [ -s $TMPDIR/findings ]; then
    echo "The following new cppcheck warnings were detected:"
    cat "$TMPDIR/findings"
    exitcode=$errorexitcode
fi

rm -rf "$TMPDIR"
exit $exitcode
