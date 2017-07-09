
# Use the GNU utilities if they are installed.

    if [ -f /usr/local/bin/gls ]; then
        alias ls='gls --color --group-directories-first'
    else
        alias ls='ls -G'
    fi
    alias ll='ls -l'
    alias la='ll -A'


# Make dangerous operations prompt for confirmation

    alias rm='rm -i'
    alias mv='mv -i'
    alias cp='cp -i'


# Increase the scope of files that ag will search

    alias ag='ag -f --hidden'


# Colorize grep

    alias grep='grep --color'
    alias egrep='egrep --color'
    alias fgrep='fgrep --color'
    alias zgrep='zgrep --color'


# Make env output easier to read

    alias env='env | sort'


# Run iPython as a shell

    alias ipysh='ipython --profile=shell'


# PyEnv helper
#
# This is a command that I miss from virtualenv_wrapper.  It doesn't work perfectly in PyEnv,
# the issue arises when there are more than one virtualenv in scope when the command is run; for
# example, when a project needs bothPY2 and PY3 available so that tox will run.

    alias cdsitepackages='pushd ~/.pyenv/versions/$(pyenv version-name)/lib/python2.7/site-packages/'


# Homebrew
#
# This is implemented in aliases.local, a file that does not get committed to the repo.  The
# reason for this alias is to prevent the token from being captured in a crash report, during
# local development, and exposed in said report.  This technique prevents the token from being
# present in the environment variables.  It will not show up in the bash history either.

    #alias brew='HOMEBREW_GITHUB_API_TOKEN=foo brew'


# Networking helpers

    # The second form is a little easier to read, but mostly I prefer the second one because
    # it returns the result without quotes.  Otherwise, the two are identical.
    #alias myip='dig TXT +short o-o.myaddr.l.google.com @ns1.google.com'
    alias myip='dig +short myip.opendns.com @resolver1.opendns.com'

    alias ifactive="ifconfig | pcregrep -M -o '^[^\t:]+:([^\n]|\n\t)*status: active'"

    # !!!: ngrep needs to be installed for this to work.
    #alias sniff="sudo ngrep -d 'en0' -t '^(GET|POST) ' 'tcp and port 80'"
    #alias httpdump='sudo tcpdump -i en0 -n -s 0 -w - | grep -a -o -E "Host: .*|GET \/.*"'


# Hide/show hidden files in Finder... meh
#
# There are several interesting aliases in Mathias B's dotfiles.  Go check them out.
#  https://github.com/mathiasbynens/dotfiles/blob/master/.aliases

    alias show='defaults write come.apple.finder AppleShowAllFiles -bool true && killall Finder'
    alias hide='defaults write come.apple.finder AppleShowAllFiles -bool false && killall Finder'


# Ring the terminal bell and put a badge on Terminal.app's dock icon

    alias badge="tput bel"


# Make Grunt print stack traces by default

    command -v grunt > /dev/null && alias grunt="grunt --stack"


# http://xkcd.com/530

    alias stfu="osascript -e 'set volume output muted true'"
    alias pumpitup="osascript -e 'set volume output volume 60'"


# Reload the shell without starting a new subshell

    alias reload='exec $SHELL --login'


# Print path components on their own line

    alias path='echo -e ${PATH//:/\\n}'


# Render the Zen

    alias zen='python -c "import this"'

