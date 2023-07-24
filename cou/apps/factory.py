from typing import List, Optional

from cou.steps.application.app import StandardApplication


class AppFactory:
    apps_type = {}

    @classmethod
    def create(cls, app_type: str, **params):
        if app_type not in cls.apps_type:
            return StandardApplication(**params)
        return cls.subclasses[app_type](params)

    @classmethod
    def register_application(cls, app_types: List, series: Optional[str] = None):
        def decorator(application):
            for app_type in app_types:
                key = app_type
                if series:
                    key = f"{app_type}-{series}"
                cls.apps_type[key] = application
                return application

        return decorator
