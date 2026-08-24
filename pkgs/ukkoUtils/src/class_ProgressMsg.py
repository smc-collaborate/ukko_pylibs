class ProgressMsg:
    def __init__(
        self,
        msg: str,
        extraDetails: str | list | None = None,
        timeout_sec: float | None = None,
    ):
        self.msg = msg
        if isinstance(extraDetails, list):
            self.extraDetails = "\n".join([str(x) for x in extraDetails])
        elif isinstance(extraDetails, str):
            self.extraDetails = extraDetails
        else:
            self.extraDetails = ""

        self.timeout_sec = timeout_sec

    def asText(self) -> str:
        result = self.msg

        if self.timeout_sec is not None:
            if self.timeout_sec <= 0:
                result += " (Timeout now)".format(self.timeout_sec)
            else:
                result += " (Timeout in {:.0f} seconds)".format(self.timeout_sec)

        if self.extraDetails:
            result += "\n" + self.extraDetails
        return result


class IWithProgressMarker_Interface:

    def asProgressMarker(self) -> ProgressMsg:
        return ProgressMsg("<<NOT_IMPLEMENTED>>")
