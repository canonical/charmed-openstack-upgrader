from typing import List

from cou.apps.app import Application


class AppFactory:
    apps_type = {}

    @classmethod
    def create(cls, app_type: str, **params):
        if app_type not in cls.apps_type:
            return Application(**params)
        return cls.apps_type[app_type](**params)

    @classmethod
    def register_application(cls, app_types: List):
        def decorator(application):
            for app_type in app_types:
                cls.apps_type[app_type] = application

        return decorator
