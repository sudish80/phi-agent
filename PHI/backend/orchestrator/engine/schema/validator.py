"""Schema validation utilities for tool parameters."""

from typing import Any, Dict, List, Optional, get_type_hints


def validate_tool_params(params: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    """Validate tool parameters against a JSON schema. Returns error string or None."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    for key in required:
        if key not in params or params[key] is None:
            return f"Missing required parameter: '{key}'"

    for key, val in params.items():
        prop = properties.get(key)
        if not prop:
            continue
        expected = prop.get("type", "string")
        if expected == "string" and not isinstance(val, str):
            return f"Parameter '{key}' should be string, got {type(val).__name__}"
        if expected == "integer" and not isinstance(val, int):
            return f"Parameter '{key}' should be integer, got {type(val).__name__}"
        if expected == "number" and not isinstance(val, (int, float)):
            return f"Parameter '{key}' should be number, got {type(val).__name__}"
        if expected == "boolean" and not isinstance(val, bool):
            return f"Parameter '{key}' should be boolean, got {type(val).__name__}"
        if expected == "array" and not isinstance(val, list):
            return f"Parameter '{key}' should be array, got {type(val).__name__}"
        if expected == "object" and not isinstance(val, dict):
            return f"Parameter '{key}' should be object, got {type(val).__name__}"

        enum_vals = prop.get("enum")
        if enum_vals and val not in enum_vals:
            return f"Parameter '{key}' must be one of: {enum_vals}"

    return None


def clean_schema_for_provider(schema: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Adapt schema for provider-specific restrictions."""
    if provider == "gemini":
        return _clean_for_gemini(schema)
    if provider == "xai":
        return _clean_for_xai(schema)
    return schema


def _clean_for_gemini(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Remove features Gemini doesn't support."""
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for k, v in schema.items():
        if k in ("default", "examples", "const"):
            continue
        if isinstance(v, dict):
            cleaned[k] = _clean_for_gemini(v)
        elif isinstance(v, list):
            cleaned[k] = [_clean_for_gemini(i) if isinstance(i, dict) else i for i in v]
        else:
            cleaned[k] = v
    return cleaned


def _clean_for_xai(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Remove features xAI doesn't support."""
    return _clean_for_gemini(schema)
