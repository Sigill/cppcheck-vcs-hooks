#!/bin/sh

YELLOW="\e[93m"
RESET="\e[0m"

run() {
  local first=$1
  shift
  echo -e "${YELLOW}$first${RESET} $@"
  $@
}

PATH=$PWD:$PATH
HG_ROOT=$(mktemp -d)

pushd "$HG_ROOT" > /dev/null
hg init

touch f.cpp
hg add f.cpp
hg commit -m "Commit 0"
COMMIT=$(hg id -i)

cat << EOF > f.cpp
#include <string>
std::string f(const std::string s) {
  return s + s;
}
EOF

declare -a BASECMD=(cppcheck-mercurial.sh -v)
#declare -a BASECMD=(/opt/python3/bin/python3 ~/Apps/cppcheck-vcs-utils/cppcheck-mercurial.py)

run "Commit 0+ (pass by const ref)" "${BASECMD[@]}"
run "Commit 0+ (skipped, no parent)" "${BASECMD[@]}" --from 'p1(tip) or 0' --to tip
run "Commit 0+ (pass by const ref)" "${BASECMD[@]}" --from 'p1(tip) or 0'

hg commit -m "Commit 1"
COMMIT=$(hg id -i)

run "Commit 1 (empty)" "${BASECMD[@]}"
run "Commit 1 (pass by const ref)" "${BASECMD[@]}" --from 'p1(tip) or 0' --to tip
run "Commit 1 (pass by const ref)" "${BASECMD[@]}" --from 'p1(tip) or 0'
run "Commit 1 (pass by const ref)" "${BASECMD[@]}" -c tip

hg mv f.cpp g.cpp
cat << EOF > g.cpp
#include <string>

std::string f(const std::string s) {
  try {
    return s + s;
  } catch (const std::exception ex) {
    throw std::runtime_error(ex.what());
  }
}
EOF

run "Commit 1+ (pass by const ref, catch by ref)" "${BASECMD[@]}"
run "Commit 1+ (pass by const ref, catch by ref)" "${BASECMD[@]}" --from 'p1(tip) or 0'

hg commit -m "Commit 2"
COMMIT=$(hg id -i)

run "Commit 2 (empty)" "${BASECMD[@]}"
run "Commit 2 (pass by const ref, catch by ref)" "${BASECMD[@]}" --from 'p1(tip) or 0' --to tip

cat << EOF > g.cpp
#include <string>


std::string f(const std::string s) {
  try {
    return s + s;
  } catch (const std::exception& ex) {
    throw std::runtime_error(ex.what());
  }
}
EOF

run "Commit 2+ (pass by const ref)" "${BASECMD[@]}"
run "Commit 2+ (skipped)" "${BASECMD[@]}" --from 'p1(tip) or 0' 

hg commit -m "Commit 3"
COMMIT=$(hg id -i)

run "Commit 3 (empty)" "${BASECMD[@]}"
run "Commit 3 (pass by const ref)" "${BASECMD[@]}" --from 'p1(tip) or 0' --to tip

popd "$HG_ROOT" > /dev/null

rm -rf "$HG_ROOT"
