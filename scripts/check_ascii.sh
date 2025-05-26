#!/bin/bash
#
# (Linux / macOS)  Make this script executable with:
#     chmod +x check_ascii.sh
# and then run it as:
#     ./check_ascii.sh
#
# PURPOSE
# This script recursively searches the current directory for files likely
# to be source code or documentation (e.g. .py, .md, .yml, etc.), and prints
# every line in those files that contains at least one non-ASCII character.
# This is useful for catching invisible or problematic encodings in commits,
# CI pipelines, or manual audits.
#
# FILE TYPES INCLUDED
# Files ending with any of the following extensions will be searched:
#     .py, .html, .md, .sh, .yml, .yaml, .env, .ini, .rst
#
# ADDING OR REMOVING FILE PATTERNS
# To include more file types, append another:
#     -o -name "*.ext" \
# before the closing parenthesis of the `find` expression.
# To exclude certain types, simply remove their `-name` lines.

find . \( \
    -name "*.py" \
    -o -name "*.html" \
    -o -name "*.md" \
    -o -name "*.sh" \
    -o -name "*.yml" \
    -o -name "*.yaml" \
    -o -name "*.env" \
    -o -name "*.ini" \
    -o -name "*.rst" \
\) -type f -print0 |
xargs -0 ggrep --color='auto' -Pn "[^\x00-\x7F]"
