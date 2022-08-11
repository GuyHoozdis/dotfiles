# Readline Wrapper (rlwrap)

I use this to get vi key-bindings in interpreters that don't natively offer
that functionality.  As time goes on those shells might not need this anymore.
I am leaving this here for reference.


# Local rlwrap Enhancements

At the time of writing the [rlwrap][rlwrap-source] was on v0.43.  The
filters and configuration here are based on that version. 

See the manpages (i.e. `man rlwrap`) for documentation with a fair level
of detail.  Examples of how to use `rlwrap` are sprinkled throughout the
documentation, the source, and the installed files.


## Configuration

Important directories:

 - `/usr/local/Cellar/rlwrap/<version>/` is the root of a specifically installed version.
 - `/usr/local/share/rlwrap/` is a link into the currently installed version. It exposes a 
    consistent path reference prefix to the `filters` and `completion` directories.
 - `/usr/local/opt/rlwrap/` is a link into the currently installed version.  It exposes a
    consistent path reference prefix to the `bin` directory and the entire application.
 - [PYTHONSITEUSER][py-site-user] or [site.USER_SITE][py-site-module]
 - `PYTHONPATH` or `PYTHONSTARTUP`
 - `$HOME/.local/share/rlwrap/` is this directory, the root of my custom filters  and 
    completions for `rlwrap`.  The `RLWRAP_FILTERDIR` will point to into the `filters`
    directory rooted here.

You can inspect the current configuration on your system with the command:

    $ python3 -m site
    sys.path = [
        '/Users/username/.local',
        '/Users/username/.pyenv/versions/3.6.1/lib/python36.zip',
        '/Users/username/.pyenv/versions/3.6.1/lib/python3.6',
        '/Users/username/.pyenv/versions/3.6.1/lib/python3.6/lib-dynload',
        '/Users/username/.local/lib/python3.6/site-packages',
        '/Users/username/.pyenv/versions/3.6.1/lib/python3.6/site-packages',
    ]
    USER_BASE: '/Users/username/.local' (exists)
    USER_SITE: '/Users/username/.local/lib/python3.6/site-packages' (exists)
    ENABLE_USER_SITE: True

If you, or your system administrator, have explicitly disabled the `USER_SITE` feature, then
you will have to use `PYTHONPATH`, modify code, or in some other way ensure that the various
components can all find each other.  If available to you, using the `USER_SITE` functionality
will be an easy and robust approach.

    $ mkdir -p $(python3 -m site --user-site)
    # Create a `usercustomize.pth` module in the directory created above
    # TODO: I should make this an installable package.
    $ vi $(python3 -m site --user-site)/usercustomize.pth
    
Set `RLWRAP_STARTUP_DEBUG=yes` to get some debug logging.




[py-site-user]: https://docs.python.org/2/using/cmdline.html#envvar-PYTHONNOUSERSITE
[py-site-module]: https://docs.python.org/2/library/site.html#site.USER_SITE


## Filters

The filters that come packaged with the binary will be located under the default
settings for `RLWRAP_FILTERDIR` if it is not explicitly or if it merely points to
the installed `.../share/filters` directory.

We don't want to put our code there though - our custom filters.  That directory
will be overwritten or changed as rlwrap updates.  It's not our directory to write
into.  An appropriate directory for our rlwrap filters would be here (i.e. in
`~/.local/share/rlwrap/filters`).  `RLWRAP_FILTERDIR` should be configured to
point to that directory.

Notice that once that is done commands like the following no longer work.

    $ rlwrap -z listing

A symlink back into a consistently named path would be a reasonable solution
to this issue.  For my own education, I have decided to port listing over to
python.


### listing

From the original filter...

> This filter is only used to get a list of filters via `rlwrap -z listingr`. It
> is not usable as a filter (and would do nothing useful).

See `/usr/local/share/rlwrap/filters/listing`


### node.py

There is not a filter of this that exists yet, but the work here is roughly 
following the efforts documented in the posts/articles below:

 - https://stackoverflow.com/questions/43505223/a-node-shell-based-on-gnu-readline/43677273#43677273
 - https://stackoverflow.com/questions/9210931/can-rlwrap-use-a-wrapped-commands-own-tab-completion/9219349#9219349
 - http://amacfie.github.io/2017/05/20/building-JS-shell/



[rlwrap-source]: https://github.com/hanslub42/rlwrap/tree/v0.43
[rlwrap-filter-source]: https://github.com/hanslub42/rlwrap/tree/v0.43/

