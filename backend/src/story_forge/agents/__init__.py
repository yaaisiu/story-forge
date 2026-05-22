"""Agents — thin, testable orchestration modules (spec §6.5).

Each agent owns one logical task, its Pydantic output schema, and its prompt
templates (in `prompts/`). An agent depends on the `LLMProvider` Protocol, never
on a concrete adapter, so it is unit-testable against a mock.
"""
