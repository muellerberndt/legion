"""Decorators for action classes"""


def no_autobot(cls):
    """Decorator to mark an action as not available for Autobot.

    Usage:
        @no_autobot
        class MyAction(BaseAction):
            ...
    """
    setattr(cls, "_no_autobot", True)
    return cls
