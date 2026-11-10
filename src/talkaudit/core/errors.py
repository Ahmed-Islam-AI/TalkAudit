class TalkAuditError(Exception):
    """Base error. `code` is stable and matches the API error codes in docs/06-API.md."""

    code = "internal_error"


class NotFoundError(TalkAuditError):
    # Also raised for other orgs' resources, so callers can't tell they exist.
    code = "not_found"


class SpecError(TalkAuditError):
    """Problems in spec files. Each problem names the file (or both files) involved."""

    code = "validation_error"

    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


class PackNotFoundError(TalkAuditError):
    code = "pack_not_found"
