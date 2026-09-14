class PalimpsestError(Exception):
    """A safe, structured error at the application boundary."""

    def __init__(self, code, message, exit_code=4, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}
