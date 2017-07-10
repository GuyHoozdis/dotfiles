# I spot checked several of the commands and it seems like many of them aren't valid. I
# keep seeing "does not exist" when I try to query the properties.  To make sure it wasn't
# typos I started copy-pasting queries.  Same result.
#
# I used the following command to extract all of the property changes, transform it
# from a write into a read operation, drop the value that would have been written,
# sorted what was left, and then uniqified that.
#
#   $ egrep "^defaults write" configure.sh | awk '{ print , read,  }' | sort | uniq > test.sh
# 
# I have found one or two that will respond, of the queries below, but most of they are
# not found.  I wonder if this has just been passed around so much it suffers from bitrot.
#
# Notice in the queryies below I only kept the _domain_, not the property.  That allowed
# me to make a shorter list.  When a domain does exist, the query will respond with all
# of the values for that domain.  Then you can examine specific properties under that
# domain.
#
# I'm getting the same result.  Even under a domain that works, most of the properties
# that the configuration script would try to write just don't exist.  Here's an example:
#
# Going down the list here, one by one, we eventually get a response from:
#
#   $ defaults read com.apple.Finder
#
# Next, we go back to the installation script to see some of the properties that the
# script would have tried to set...
#
#   $ defaults read com.apple.Finder QuitMenuItem
#   The domain/default pair of (com.apple.Finder, QuitMenuItem) does not exist
#
#   $ defaults read com.apple.Finder DisabeAllAnimations
#   The domain/default pair of (com.apple.Finder, DisabeAllAnimations) does not exist#
#
#   $ defaults read com.apple.Finder AppleShowAllFiles
#   0
#
#   $ defaults read com.apple.Finder AppleShowAllExtensions
#   The domain/default pair of (com.apple.Finder, AppleShowAllExtensions) does not exist
#
# ... so three out of those 4, under the one domain that existed so far, were non-sensical.
# I think this osx configuration script is dead.


defaults read "com.apple.sound.beep.feedback"
defaults read "com.apple.systemsound"
defaults read NSGlobalDomain
defaults read com.apple.ActivityMonitor
defaults read com.apple.BezelServices
defaults read com.apple.BluetoothAudioAgent
defaults read com.apple.DiskUtility
defaults read com.apple.Finder
defaults read com.apple.LaunchServices
defaults read com.apple.NetworkBrowser
defaults read com.apple.QuickTimePlayerX
defaults read com.apple.Safari
defaults read com.apple.SoftwareUpdate
defaults read com.apple.Terminal
defaults read com.apple.TextEdit
defaults read com.apple.TimeMachine
defaults read com.apple.addressbook
defaults read com.apple.appstore
defaults read com.apple.dashboard
defaults read com.apple.desktopservices
defaults read com.apple.dock
defaults read com.apple.driver.AppleBluetoothMultitouch.trackpad
defaults read com.apple.finder
defaults read com.apple.frameworks.diskimages
defaults read com.apple.helpviewer
defaults read com.apple.iCal
defaults read com.apple.mail
defaults read com.apple.messageshelper.MessageController
defaults read com.apple.print.PrintingPrefs
defaults read com.apple.screencapture
defaults read com.apple.spotlight
defaults read com.apple.systempreferences
defaults read com.apple.systemsound
defaults read com.apple.systemuiserver
defaults read com.apple.terminal
defaults read com.apple.touchbar.agent
defaults read com.apple.universalaccess
defaults read com.divisiblebyzero.Spectacle
defaults read com.google.Chrome
defaults read com.google.Chrome.canary
defaults read com.googlecode.iterm2
defaults read com.irradiatedsoftware.SizeUp
defaults read com.operasoftware.Opera
defaults read com.operasoftware.OperaDeveloper
defaults read com.tapbots.TweetbotMac
defaults read com.twitter.twitter-mac
defaults read org.m0k.transmission
defaults read ~/Library/Preferences/org.gpgtools.gpgmail
