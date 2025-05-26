#!/bin/bash
#
# (Linux / macOS)  Make this script executable with:
#     chmod +x check_autopep8.sh
# and then run it as:
#     ./check_autopep8.sh
#
# PURPOSE
# This loop walks through the current directory tree and inspects every
# Python source file, except the ones you explicitly exclude, to see whether
# it already conforms to the formatting rules enforced by autopep8. A file
# that needs reformatting is reported.
# 
# ADDING OR REMOVING FILE PATTERNS
# To skip a file, append another '! -name "pattern.py"'  right after the
# existing exclusions.  To include additional files, change or add extra
# '-name "*.something"'  filters before the first  '! -name'  clause.
# The find command evaluates the tests left to right, so place inclusions
# first and exclusions later to keep the logic readable.

EXIT_CODE=0

find . -type f -name "*.py" \
        ! -name "urls.py" \
        ! -name "models.py" \
        ! -name "*.ipynb" \
        -print0 |
while IFS= read -r -d '' file; do
    autopep8 "$file" \
             --exit-code \
             --max-line-length=100 \
             --ignore=E203,W503 \
             --select=E,W \
             --aggressive \
             > /dev/null

    if [ $? -ne 0 ]; then
        echo "Formatting needed: $file"
        EXIT_CODE=1
    fi
done

exit $EXIT_CODE
