#!/bin/bash

COLOR_RED='\e[0;31m'
COLOR_GREEN='\e[0;32m'
COLOR_BLUE='\e[0;34m'
COLOR_LRED='\e[0;91m'
COLOR_LGREEN='\e[0;92m'
COLOR_NC='\e[0m'

declare -i verbose=0
from=
to=
ignore=
untracked=n
declare -a files
declare -a cppcheckoptions=("--enable=warning,style,performance,portability" "--language=c++" "--inconclusive")
errorexitcode=0

function usage
{
  echo "Usage: $0 [options...] [-- cppcheck options...]"
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
  echo "  --ignore FILE    Ignore patterns."
  echo "                   The first line of each finding will be run through"
  echo "                   grep -f FILE. In case of match, the finding is ignored."
  echo "  -f/--file FILE   File to analyse."
  echo "                   If not specified, the list of files is automatically"
  echo "                   using hg status."
  echo "  -u/--untracked   Include untracked files."
  echo "  --exitcode       Exit code if findings are found (default is 0)."
  echo "  -v/--verbose     Verbose mode."
  echo "  -h/--help        Print this help."
  echo
  echo "Default cppcheck options are: ${cppcheckoptions[@]}."
}


while :; do
  case $1 in
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
    --ignore)
      if [ -z "$2" ]; then
        >&2 echo '"--ignore" requires a non-empty argument.'
        exit 1
      fi
      ignore=$2
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
    -f|--file)
      if [ -z "$2" ]; then
        >&2 echo '"--file" requires a non-empty argument.'
        exit 1
      fi
      files+=("$2")
      shift
      ;;
    -v|--verbose)
      verbose=$((verbose + 1))
      ;;
    -h|--help)
      >&2 usage
      exit
      ;;
    --)
      shift
      cppcheckoptions=("$@")
      break
      ;;
    *) # No more options, stop parsing arguments.
      break
  esac

  shift
done

cppcheck_filter() {
    if [ -n "$ignore" -a -f "$ignore" ]; then
        local path=
        while read; do
            if [[ $REPLY =~ ^([^:]*):[0-9]+:[0-9]+: ]]; then
                echo "$REPLY" | grep -q -f $ignore
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
    else
        cat
    fi
}

colorize() {
    echo -ne "$1"
    shift
    "$@"
    echo -ne "$COLOR_NC"
}

printcmd() {
  colorize "$COLOR_BLUE" echo "$@"
}

run() {
  [ $verbose -gt 0 ] && >&2 printcmd "$@"
  "$@"
}

run_cppcheck() {
    declare -a CMD=(cppcheck -q "${cppcheckoptions[@]}" --relative-paths="$1" "$1/$2")
    [ $verbose -gt 0 ] && >&2 printcmd "${CMD[@]}"
    # Swap stderr & stdout
    "${CMD[@]}" 3>&2 2>&1 1>&3 | cppcheck_filter
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

if [ ${#files[@]} -eq 0 ]; then
    [[ "$untracked" = "y" ]] && U_ARG="-u" || U_ARG=""
    readarray -t files < <( run hg status -R "$HG_ROOT" "${REV1_ARGS[@]}" "${REV2_ARGS[@]}" -m -a $U_ARG | grep -E '^[MA?].*\.(cpp|cxx|h|hxx)$' | sed 's/^[MA?]\s*//' )
fi

TMPDIR=$(mktemp -d --tmpdir cppcheck.mercurial.XXXXXXXXXX)

for i in "${!files[@]}"
do
    f="${files[$i]}"
    i=$((i+1))
    >&2 colorize "$COLOR_BLUE" echo "$i Running cppcheck on:  $f"
    src="$HG_ROOT/$f"

    fwd="$TMPDIR/$i"
    mkdir -p "$fwd" && pushd "$fwd" > /dev/null


    rightf="$fwd/R/$f"
    mkdir -p `dirname "$rightf"`

    if [ -z "$to" ]; then
        run cp "$src" "$rightf"
    else
        run hg cat -R "$HG_ROOT" "${REV2_ARG[@]}" "$src" -o "$rightf"
    fi

    run_cppcheck "$fwd/R" "$f" > "$fwd/findings-r"


    if [ -n "$from" ]; then
        leftf="$fwd/L/$f"
        mkdir -p `dirname "$leftf"`

        run cp "$rightf" "$leftf"
        run hg diff -R "$HG_ROOT" "${REV1_ARGS[@]}" "${REV2_ARGS[@]}" "$src" > "$fwd/patchfile"
        run patch -Rs -p1 --posix -d "$fwd/L" -i "$fwd/patchfile"
        #hg cat -R "$HG_ROOT" "${REV1_ARGS[@]}" "$HG_ROOT/$f" > "$TMPDIR/L/$f"
        run_cppcheck "$fwd/L" "$f" > "$fwd/findings-l"
    fi

    if [ $verbose -gt 1 ]; then
        if [ -n "$from" ]; then
            >&2 colorize "$COLOR_RED" cat "$leftf"
            >&2 colorize "$COLOR_LRED" cat "$fwd/findings-l"
        fi

        >&2 colorize "$COLOR_GREEN" cat "$rightf"
        >&2 colorize "$COLOR_LGREEN" cat "$fwd/findings-r"
    fi

    if [ -n "$from" ]; then
        run cppcheck-diff-findings.py "$fwd/findings-l" "$fwd/findings-r" >> "$TMPDIR/findings"
    else
        cat "$fwd/findings-r" >> "$TMPDIR/findings"
    fi

    popd > /dev/null
done

exitcode=0

if [ -s $TMPDIR/findings ]; then
    echo "The following new cppcheck warnings were detected:"
    cat "$TMPDIR/findings"
    exitcode=$errorexitcode
fi

rm -rf "$TMPDIR"
exit $exitcode
