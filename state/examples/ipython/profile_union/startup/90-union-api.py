from __future__ import absolute_import
from __future__ import print_function

import os
import sys


THRESHOLD = 10
OVERRIDE = os.environ.get('UNION_PROFILE_FORCE', 'False').lower() == 'true'
DEFER = os.environ.get('UNION_PROFILE_DEFER', 'False').lower() == 'true'

twelve_factor_config = {
    key: value
    for key, value in os.environ.items()
    if key.startswith('APP_') or key.startswith('MYSQL_')
}


try:
    if DEFER:
        raise EnvironmentError("Defer loading Union API components")

    if len(twelve_factor_config) < THRESHOLD and not OVERRIDE:
        raise EnvironmentError(
            "Failed to detect 12-factor app config in the current environment. "
            "Use 'UNION_PROFILE_FORCE=True ipython --profile union' or load "
            "the environment with configuration data."
        )

    import sqlalchemy as sa
    import sqlalchemy_utils as sautils

    from pos_api.utils import moment
    from pos_api.utils.logger import getLogger
    from pos_api import (
        controllers,
        models,
        resources,
        run_app,
        schemas,
        settings,
    )
    import couch_worker.run, sqs_worker.run
except EnvironmentError as ex:
    print(ex.message, file=sys.stderr)
except ImportError as ex:
    print(ex.message, file=sys.stderr)
else:
    # TODO: Migrate everything under a scope to clean up the shell env
    format_sa_logger_name = 'sqlalchemy.{}'.format
    sa_modules = ['dialect', 'engine', 'pool', 'orm']
    db_log_level = settings.get('APP_DB_LOG_LEVEL')
    [getLogger(name).setLevel(db_log_level)
     for name in map(format_sa_logger_name, sa_modules)]


# TODO: Trying this out
def _initialize_application():
    from argparse import Namespace
    import pos_api.celery

    class _ReadOnly(Namespace):
        def __iter__(self):
            for value in self.__dict__.itervalues():
                yield value

    class Application(_ReadOnly):
        """Readonly container for the initialized application components.
        """

    class Workers(_ReadOnly):
        """Readonly container to organize access to the async workers
        """

    db_dsn = settings.get('APP_DB_DSN').rstrip('/')
    engine = sa.create_engine(db_dsn)
    session = models.Session.configure(bind=engine)
    return Application(**{
        'settings': settings,
        'engine': engine,
        'session': models.Session.configure(bind=engine),
        'api': run_app.app,
        'workers': Workers(**{
            'celery': pos_api.celery,
            'couch': couch_worker,
            'sqs': sqs_worker,
        }),
    })


app = application = _initialize_application() if not DEFER else None
