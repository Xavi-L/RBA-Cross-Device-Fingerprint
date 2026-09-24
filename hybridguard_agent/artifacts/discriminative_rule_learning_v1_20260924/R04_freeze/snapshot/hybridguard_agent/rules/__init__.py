"""Registry-controlled deterministic rule execution."""

from .executor import execute_deterministic_rules, load_predicate_registry

__all__ = ["execute_deterministic_rules", "load_predicate_registry"]
