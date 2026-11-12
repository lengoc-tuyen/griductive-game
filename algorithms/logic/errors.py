"""[A] Exceptions shared by the logic package."""


class ClueValidationError(ValueError):
    """A clue has bad parameters or refers to cells/people that do not exist."""
