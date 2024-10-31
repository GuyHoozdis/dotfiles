#!/usr/bin/env bash

set -eou pipefail

EXIT_INSTALLED=0
EXIT_MISSING=1
EXIT_INELIGIBLE=2
EXIT_ERROR=-1

return_code=$EXIT_ERROR

# If cpu is Apple branded, use arch binary to check if x86_64 code can run
if [[ "$(sysctl -n machdep.cpu.brand_string)" == *'Apple'* ]]; then
    if arch -x86_64 /usr/bin/true 2> /dev/null; then
        result="Installed"
        return_code=0
    else
        result="Missing"
        return_code=1
    fi
else
    result="Ineligible"
    return_code=2
fi

echo "$result"
exit $return_code
