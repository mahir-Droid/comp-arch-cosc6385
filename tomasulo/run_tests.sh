#!/bin/bash
# runs every test case in testcases/ with issue width 1, 2, 3 and 4
# and stores the output in results/<testcase>_width<N>.txt
cd "$(dirname "$0")/code"
mkdir -p ../results
for test in ../testcases/*.txt; do
    name=$(basename "$test" .txt)
    for width in 1 2 3 4; do
        # replace (or add) the issue width line of the test case
        grep -iv "^issue width" "$test" | sed "s/^ROB entries.*/&\nIssue width = $width/" > /tmp/tomasulo_input.txt
        python3 main.py /tmp/tomasulo_input.txt > "../results/${name}_width${width}.txt"
        echo "$name width $width -> results/${name}_width${width}.txt"
    done
done
rm -f /tmp/tomasulo_input.txt
