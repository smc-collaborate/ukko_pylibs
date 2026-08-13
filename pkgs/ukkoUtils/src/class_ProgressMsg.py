class ProgressMsg:
    def __init__(self, msg: str, timeout_sec: float | None = None):
        self.msg = msg
        self.timeout_sec = timeout_sec

    def asText(self) -> str:
        result = self.msg

        if self.timeout_sec is not None:
            if self.timeout_sec <= 0:
                result += " (Timeout now)".format(self.timeout_sec)
            else:
                result += " (Timeout in {:.1f} seconds)".format(self.timeout_sec)

        return result
