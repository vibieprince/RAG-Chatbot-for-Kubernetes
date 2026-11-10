"""
Pytest configuration and environment fixtures for Kubernetes Agentic RAG tests.
"""
import os

# Disable external network telemetry in tests to ensure deterministic local execution
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["LOGFIRE_IGNORE_NO_CONFIG"] = "1"
