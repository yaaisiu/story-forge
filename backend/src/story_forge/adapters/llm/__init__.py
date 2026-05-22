"""LLM adapter layer (spec §6.5).

One `LLMProvider` Protocol; concrete adapters implement it. `OllamaProvider`
serves both the local-small and cloud-free tiers (same Ollama API, different
host/key). Paid-cloud and meta-provider adapters land in later milestones.
"""
