class TalkAuditError(Exception):
    """Base error. `code` is stable and matches the API error codes in docs/06-API.md."""

    code = "internal_error"


class NotFoundError(TalkAuditError):
    # Also raised for other orgs' resources, so callers can't tell they exist.
    code = "not_found"
