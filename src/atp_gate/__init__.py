"""Pre-match ATP input and PAPER-ONLY selection gate; no betting integration.

Research-only modules need not import the gate's optional-at-runtime
Pydantic contracts. Public package exports remain backwards compatible.
"""
from importlib import import_module

__all__ = ['DecisionInput', 'DecisionOutput', 'evaluate', 'apply_profit_lock']
_EXPORTS = {
    'DecisionInput': '.contracts',
    'DecisionOutput': '.contracts',
    'evaluate': '.policy',
    'apply_profit_lock': '.policy',
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_EXPORTS[name], __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
