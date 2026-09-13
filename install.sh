#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-only
set -eu
case "$0" in */*) directory=${0%/*} ;; *) directory=. ;; esac
exec sh "$directory/launch.sh" _install "$@"
