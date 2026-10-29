"""Deterministic query tools for the IATI knowledge graph.

Each tool is a parameterised, read-only Cypher template that returns rows of
(key, value, evidence). The LLM only chooses the tool and its arguments; it never
writes the Cypher, so a correctly chosen tool cannot produce a wrong number.
"""
from .templates import TOOLS, run_tool, validate_args, tool_catalog
from .resolver import OrgResolver

__all__ = ["TOOLS", "run_tool", "validate_args", "tool_catalog", "OrgResolver"]
