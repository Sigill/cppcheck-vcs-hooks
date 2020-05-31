#!/bin/bash

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

COLOR_RED='\e[0;31m'
COLOR_GREEN='\e[0;32m'
COLOR_BLUE='\e[0;34m'
COLOR_LRED='\e[0;91m'
COLOR_LGREEN='\e[0;92m'
COLOR_NC='\e[0m'

declare -i verbose=0
from=
to=
change=
ignore=
untracked=n
declare -a files
declare -a cppcheckoptions=("--enable=warning,style,performance,portability" "--language=c++" "--inconclusive")
errorexitcode=0
wd="$PWD"

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
  echo "  --hg DIR         Location of the repository."
  echo "                   If not specified, use current working directory."
  echo "  --exitcode       Exit code if findings are found (default is 0)."
  echo "  -v/--verbose     Verbose mode."
  echo "  -h/--help        Print this help."
  echo
  echo "Default cppcheck options are: ${cppcheckoptions[@]}."
}

assert_arg() {
  if [ -z "$2" ]; then
    >&2 echo "$0: option $1 requires a non-empty argument"
    exit 1
  fi
}

while :; do
  case $1 in
    --from)
      assert_arg "$1" "$2"
      from="$2"
      shift
      ;;
    --to)
      assert_arg "$1" "$2"
      to="$2"
      shift
      ;;
    -c|--change)
      assert_arg "$1" "$2"
      from="p1($2)"
      to="$2"
      change="$2"
      shift
      ;;
    --ignore)
      assert_arg "$1" "$2"
      ignore="$2"
      shift
      ;;
    -u|--untracked)
      untracked=y
      ;;
    --exitcode)
      assert_arg "$1" "$2"
      errorexitcode="$2"
      shift
      ;;
    -f|--file)
      assert_arg "$1" "$2"
      files+=("$2")
      shift
      ;;
    --hg)
      assert_arg "$1" "$2"
      wd=$2
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
  [ $verbose -gt 1 ] && >&2 printcmd "$@"
  "$@"
}

run_cppcheck() {
    declare -a CMD=(cppcheck -q "${cppcheckoptions[@]}" --relative-paths="$1" "$1/$2")
    [ $verbose -gt 1 ] && >&2 printcmd "${CMD[@]}"
    # Swap stderr & stdout
    "${CMD[@]}" 3>&2 2>&1 1>&3 | cppcheck_filter
}

process_file() {
    local f="$1"
    local a="$2"

    local src="$HG_ROOT/$f"

    local fwd="$TMPDIR/$i"
    mkdir -p "$fwd"
    pushd "$fwd" > /dev/null


    local process_left=y
    if [ -z "$from" -o "$a" != "M" ]; then
      process_left=n
    fi

    if [ "$process_left" = "y" ]; then
        local leftf="$fwd/L/$f"
        mkdir -p `dirname "$leftf"`

        run hg cat -R "$HG_ROOT" "${REV1_ARGS[@]}" "$src" -o "$leftf"
    fi

    declare -a waitpids

    if [ -s "$fwd/L/$f" ]; then
        run_cppcheck "$fwd/L" "$f" > "$fwd/findings-l" &
        waitpids+=("$!")
    fi


    local rightf="$fwd/R/$f"
    mkdir -p `dirname "$rightf"`

    if [ -z "$to" ]; then
        run cp "$src" "$rightf"
    elif [ "$process_left" = "y" ]; then
        run cp "$leftf" "$rightf" && \
        run hg diff -R "$HG_ROOT" -a "${RANGE_ARGS[@]}" "$src" > "$fwd/patchfile" && \
        run patch -us -p1 --posix --batch -d "$fwd/R" -i "$fwd/patchfile"
    else
        run hg cat -R "$HG_ROOT" "${REV2_ARGS[@]}" "$src" -o "$rightf"
    fi

    if [ -s "$fwd/R/$f" ]; then
        run_cppcheck "$fwd/R" "$f" > "$fwd/findings-r"
        waitpids+=("$!")
    fi

    wait "${waitpid[@]}"

    if [ ! -s "$fwd/R/$f" ]; then
        popd > /dev/null
        continue
    fi


    if [ $verbose -gt 2 ]; then
        if [ "$process_left" = "y" ]; then
            >&2 colorize "$COLOR_RED" cat "$leftf"
            >&2 colorize "$COLOR_LRED" cat "$fwd/findings-l"
        fi

        >&2 colorize "$COLOR_GREEN" cat "$rightf"
        >&2 colorize "$COLOR_LGREEN" cat "$fwd/findings-r"
    fi

    if [ -f "$fwd/findings-l" -a -f "$fwd/findings-r" ]; then
        python3 "$SCRIPTDIR/cppcheck-diff-findings.py" "$fwd/findings-l" "$fwd/findings-r" >> "$TMPDIR/findings"
    else
        cat "$fwd/findings-r" >> "$TMPDIR/findings"
    fi

    popd > /dev/null
}

HG_ROOT=$(hg --cwd "$wd" root)
if [ -z "$HG_ROOT" ] ; then
    echo "not an hg repo..."
    exit 1
fi

if [ -n "$to" ]; then
    nparents=$(run hg log -R "$HG_ROOT" --rev "parents($to)" --template '{rev}\n' | wc -l)
    if [ "$nparents" -ne 1 ]; then
        [ $verbose -gt 0 ] && >&2 echo "$to is a merge, skipping"
        exit
    fi
fi

declare -a REV1_ARGS
if [ -n "$from" ]; then
    REV1_ARGS+=('--rev' "$from")
fi

declare -a REV2_ARGS
if [ -n "$to" ]; then
    REV2_ARGS+=('--rev' "$to")
fi

declare -a RANGE_ARGS
if [ -z "$change" ]; then
    RANGE_ARGS+=("${REV1_ARGS[@]}")
    RANGE_ARGS+=("${REV2_ARGS[@]}")
else
    RANGE_ARGS+=('--change' "$change")
fi

[[ "$untracked" = "y" ]] && U_ARG="-u" || U_ARG=""
readarray -t files < <( run hg status -R "$HG_ROOT" "${RANGE_ARGS[@]}" -m -a $U_ARG "${files[@]}"| grep -E '^[MA?]\s.*\.(cpp|cxx|h|hxx)$' )

TMPDIR=$(mktemp -d --tmpdir cppcheck.mercurial.XXXXXXXXXX)

for i in "${!files[@]}"
do
    l="${files[$i]}"
    a=$(echo "$l" | awk '{print $1}')
    f=$(echo "$l" | awk '{print $2}')
    i=$((i+1))
    [ $verbose -gt 0 ] && >&2 colorize "$COLOR_BLUE" echo "$i Running cppcheck on:  $f"

    process_file "$f" "$a"
done

exitcode=0

if [ -s $TMPDIR/findings ]; then
    cat "$TMPDIR/findings"
    exitcode=$errorexitcode
fi

rm -rf "$TMPDIR"
exit $exitcode
