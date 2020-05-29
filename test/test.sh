#!/bin/sh

RED="\e[31m"
RESET="\e[0m"

run() {
  local first=$1
  shift
  echo -e "${RED}$first${RESET} $@"
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

run "Commit 0+ (pass by const ref)" cppcheck-mercurial.sh
run "Commit 0+ (empty)" cppcheck-mercurial.sh --from 'p1(tip) or 0' --to tip
run "Commit 0+ (pass by const ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0'

hg commit -m "Commit 1"
COMMIT=$(hg id -i)

run "Commit 1 (empty)" cppcheck-mercurial.sh
run "Commit 1 (pass by const ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0' --to tip
run "Commit 1 (pass by const ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0'
run "Commit 1 (pass by const ref)" cppcheck-mercurial.sh -c tip

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

run "Commit 1+ (pass by const ref, catch by ref)" cppcheck-mercurial.sh
run "Commit 1+ (catch by ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0'

hg commit -m "Commit 2"
COMMIT=$(hg id -i)

run "Commit 2 (empty)" cppcheck-mercurial.sh
run "Commit 2 (pass by const ref, catch by ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0' --to tip

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

run "Commit 2+ (pass by const ref)" cppcheck-mercurial.sh --from 'p1(tip) or 0' 

hg commit -m "Commit 3"
COMMIT=$(hg id -i)

run "Commit 3 (empty)" cppcheck-mercurial.sh
run "Commit 3 (empty)" cppcheck-mercurial.sh --from 'p1(tip) or 0' --to tip

popd "$HG_ROOT" > /dev/null

rm -rf "$HG_ROOT"
