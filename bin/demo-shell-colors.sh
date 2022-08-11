#!/usr/bin/env bash

# This article seemed to have a reasonably concise review of the
# details about shell colors that I am looking up repeatedly.
#
#   http://jafrog.com/2013/11/23/colors-in-terminal.html
#
# Additional resources
#   http://tldp.org/HOWTO/Bash-Prompt-HOWTO/x329.html
#   https://misc.flogisoft.com/bash/tip_colors_and_formatting


for code in {30..37}; do
  echo -en "\e[${code}m"'\\e['"$code"'m'"\e[0m";
  echo -en "  \e[$code;1m"'\\e['"$code"';1m'"\e[0m";
  echo -en "  \e[$code;1m"'\\e['"$code"';2m'"\e[0m";
  echo -en "  \e[$code;3m"'\\e['"$code"';3m'"\e[0m";
  echo -en "  \e[$code;4m"'\\e['"$code"';4m'"\e[0m";
  echo -en "  \e[$((code+60))m"'\\e['"$((code+60))"'m'"\e[0m";
  echo ""
done

for code in {40..47}; do
  echo -en "\e[${code}m"'\\e['"$code"'m'"\e[0m";
  echo -en "  \e[$code;1m"'\\e['"$code"';1m'"\e[0m";
  echo -en "  \e[$code;1m"'\\e['"$code"';2m'"\e[0m";
  echo -en "  \e[$code;3m"'\\e['"$code"';3m'"\e[0m";
  echo -en "  \e[$code;4m"'\\e['"$code"';4m'"\e[0m";
  echo ""
done
