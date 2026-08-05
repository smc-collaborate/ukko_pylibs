def isRunning() -> bool:
    """Returns True if the application is running, False if it is stopping."""
    from appAssist import app  # <-- Import here to avoid circular import issues

    return app.isRunning()


def doHalt(reason: str):
    """Halts the application with a reason."""
    from appAssist import app  # <-- Import here to avoid circular import issues

    app.doHalt(reason)
