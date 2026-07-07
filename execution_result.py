from dataclasses import dataclass, field


@dataclass
class ExecutionResult:
    """
    Structured outcome of running one handler. Never a silent side-effect:
    every executor/mode-manager action returns one of these, with a message
    written to be surfaced as-is in a UI (including to a screen reader).
    """
    success: bool
    message: str
    data: dict = field(default_factory=dict)
    error: str = None
