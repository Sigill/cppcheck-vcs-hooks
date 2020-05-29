#!/bin/sh

function usage
{
  echo "Usage: $0 [-h] [--from REV] [--to REV] [-c REV] [--tip|--tip+]"
  echo
  echo "Run cppcheck on the files modified between two Mercurial revisions."
  echo "By default, it will process uncommited changes (--from tip)."
  echo
  echo "Options:"
  echo "  --from REV       Revision to start from (NOT inclusive, only changes"
  echo "                   introduced AFTER this revision will be considered."
  echo "                   Use p1(REV) to start from the first parent."
  echo "                   See 'hg help revset' for more details."
  echo "  --to REV         Last revision to consider (inclusive)."
  echo "  -c/--change REV  Consider changes introduced by this revision."
  echo "                   Equivalent to --from \"p1(REV)\" --to REV."
  echo "  tip              Analyse changes introduced in last revision."
  echo "                   Equivalent to --from \"p1(tip)\" --to tip"
  echo "  tip+             Analyse changes introduced in last revision,"
  echo "                   including uncommited changes."
  echo "                   Equivalent to --from \"p1(tip)\""
  echo "  -h/--help        Print this help."
}

from=tip
to=

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
    tip)
      from="p1(tip)"
      to=tip
      ;;
    tip+)
      from="p1(tip)"
      to=
      ;;
    *) # No more options, stop parsing arguments.
      break
  esac

  shift
done

get_altered_files() {
  local FROM_ARG="--rev $1"
  local TO_ARG="--rev $2"

  if [ -z "$2" ]; then
      TO_ARG=
  fi

  hg status -R "$HG_ROOT" $FROM_ARG $TO_ARG -m -a | grep -E '^[MA].*\.(cpp|cxx|h|hxx)$' | sed 's/[MA]\s//'
}

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

HG_ROOT=`hg root`

if [ -z "$HG_ROOT" ] ; then
    echo "not an hg repo..."
    exit 1
fi

ALTERED_FILES=$(get_altered_files "$from" "$to")

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
    >&2 echo "Checking for errors:  $i"
    mkdir -p `dirname "$TMPDIR/$i"`

    if [ -z "$to" ]; then
        cp "$HG_ROOT/$i" "$TMPDIR/$i.curr"
    else
        hg cat -R "$HG_ROOT" --rev "$to" "$HG_ROOT/$i" > "$TMPDIR/$i.curr" &
    fi

    hg cat -R "$HG_ROOT" --rev "$from" "$HG_ROOT/$i" > "$TMPDIR/$i.prev" &
    wait # hg cat can be slow, execute them in parallel and wait

    cppcheck -q --enable=style,performance,portability --language=c++ --inconclusive "$TMPDIR/$i.prev" 2>&1 | sed "s@$TMPDIR/$i.prev@$i@" | cppcheck_filter "$FILTER_LINE_FILE" > "$TMPDIR/findings-l"
    cppcheck -q --enable=style,performance,portability --language=c++ --inconclusive "$TMPDIR/$i.curr" 2>&1 | sed "s@$TMPDIR/$i.curr@$i@" | cppcheck_filter "$FILTER_LINE_FILE" > "$TMPDIR/findings-r"

    cppcheck-diff-findings.py "$TMPDIR/findings-l" "$TMPDIR/findings-r" >> "$TMPDIR/findings"
done

if [ -s $TMPDIR/findings ] ; then
    echo "The following new cppcheck warnings were detected:"
    cat "$TMPDIR/findings"
fi

rm -rf "$TMPDIR"
