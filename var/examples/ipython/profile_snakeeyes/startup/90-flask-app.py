from __future__ import absolute_import

from snakeeyes import app as AppFactory


def reload_application(app=None, with_blueprints=True, with_extensions=True,
                       with_authentication=True, **settings_overrides):

    application = AppFactory.configure_app(app=app)
    application.config.from_pyfile('settings_local.py')
    if settings_overrides:
        application.config.update(**settings_overrides)

    if with_blueprints:
        AppFactory.register_blueprints(application)
    if with_extensions:
        AppFactory.register_extensions(application)
    if with_authentication:
        from snakeeyes.blueprints.user.models import User
        # AppFactory.register_authentication(application, User)
        AppFactory.register_authenticators(application, User)

    application_context = application.app_context()
    application_context.push()

    return application, application_context


application, application_context = reload_application()
