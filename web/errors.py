class RunnerException(Exception):
    pass


class CloneFailed(RunnerException):
    pass


class CheckoutFailed(RunnerException):
    pass


class UnknownScanner(RunnerException):
    pass