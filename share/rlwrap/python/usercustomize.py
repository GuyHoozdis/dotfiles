# XXX: This didn't work very well.  I it is doing too much during the otherwise
# fradgile startup process.  See some of the other *.pth files.  They don't do
# this.  NewRelic does, but... idk... running the debug info colleciton was
# problematic.


# Path configuration to support rlwrap filters written in python
import os
import sys

from datetime import datetime


RLWRAP_STARTUP_DEBUG_ENABLED = os.environ.get(
    'RLWRAP_FILTER_STARTUP_DEBUG', 'off'
).lower() in ('on', 'true', '1', 'yes', 'y')


def debug(message_template, *template_args):
    format_message = (
        "RLWRAP_FILTER: {timestamp} ({ppid}:{pid}) - {message}"
    ).format
    message_kwargs = {
        'message': message_template.format(*template_args),
        'timestamp': datetime.now(), 'pid': os.getpid(), 'ppid': os.getppid(),
    }
    message = format_message(**message_kwargs)
    sys.stdout.write(message)
    sys.stdout.flush()


def section_header(header, align='=^', width=72, **kwargs):
    header_template = "{:{align}{width}.{precision}}"
    if not kwargs.get('precision'):
        kwargs['precision'] = len(header)
    kwargs['message'] = " {} ".format(header.strip())
    kwargs['align'] = '<' if len(header) > width else align
    kwargs['width'] = width

    sys.stdout.write(header_template, **kwargs)
    sys.stdout.flush()



# Gather some system information to help figure out what is happening when
# things go wrong.
def debug_info():
    import ipdb; ipdb.sset_trace();  # Breakpoint
    debug("Module Search path bootstraping: {}", __file__)

    section_header("Platform / Framework")
    debug("sys.platform = {0!r}", sys.platform)
    debug("sys.executable = {0!r}", sys.executable)
    debug("sys.version = \n\t{0}\n\t{1}", *sys.version.split('\n'))
    debug("sys.version_info = {0!r}", sys.version_info)
    debug("sys.byteorder = {0}", sys.byteorder)

    section_header("Path / Directory")
    debug("CWD = {0!r}", os.getcwd())
    debug("HERE = {0!r}", os.path.dirname(__file__))
    debug("sys.prefix= {0!r}", sys.prefix)
    debug("sys.exec_prefix= {0!r}", sys.exec_prefix)
    debug("sys.path = \n\t{0}", '\n\t'.join(sys.path))
    debug("sys.meta_path = \n\t{0}", '\n\t'.join(sys.meta_path))

    section_header("Environment / Config")
    debug("sys.flags = {0!r}", sys.flags)
    debug("PYTHONDONTWRITEBYTECODE = {0!r}", sys.dont_write_bytecode)
    environment_variables = sorted([
        (k, v) for k, v in os.environ.items()
        if k.startswith('RLWRAP') or k.startswith('PYTHON')
    ])
    for envvar, value in environment_variables:
        debug("{0} = {1!r}", envvar, value)


def add_rlwrap_filters_path_to_module_search_path(rlwrap_filters_path):
    if not os.path.isdir(rlwrap_filters_path):
        debug("Failed to locate rlwrap filter directory", RLWRAP_FILTER)
        return

    sys.path.append(rlwrap_filters_path)


# TODO:
# - Genericize this lookup, for now just hardcode it to prove this approach
# -
RLWRAP_FILTERLIB = '/usr/local/share/rlwrap/filters'
try:
    if RLWRAP_STARTUP_DEBUG_ENABLED:
        debug_info()

    add_rlwrap_filters_path_to_module_search_path(RLWRAP_FILTERLIB)
except:
    if not os.environ.get('PYTHONVERBOSE', False):
        from textwrap import dedent
        previous_command = (
            "$ {1} 2>&1 | tee rlwrap-filters-bug-report.txt"
        ).format(
            ' '.join(sys.argv) if getattr(sys, 'argv', None) else '<command>'
        )
        sys.stderr.write(dedent("""
            Fatal: Unhandled exception in {0}.  Failed to collect debug info
            while loading RLWRAP_FILTER path customizations. :( sorrry.

            Enable PYTHONVERBOSE and re-run last command to create a bug
            report.

                {previous_command}
        """.format(__file__, previous_command=previous_command)))
        sys.stderr.flush()
        raise
