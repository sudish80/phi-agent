import pytest
from backend.orchestrator.engine.schema.validator import (
    validate_tool_params,
    clean_schema_for_provider,
)


class TestValidateToolParams:
    def test_valid_params_pass(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        }
        error = validate_tool_params({"name": "test", "count": 5}, schema)
        assert error is None

    def test_missing_required(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        error = validate_tool_params({}, schema)
        assert error == "Missing required parameter: 'name'"

    def test_wrong_type_string(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        error = validate_tool_params({"name": 42}, schema)
        assert error == "Parameter 'name' should be string, got int"

    def test_wrong_type_integer(self):
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
            "required": ["age"],
        }
        error = validate_tool_params({"age": "twenty"}, schema)
        assert error == "Parameter 'age' should be integer, got str"

    def test_wrong_type_number(self):
        schema = {
            "type": "object",
            "properties": {"price": {"type": "number"}},
            "required": ["price"],
        }
        error = validate_tool_params({"price": "free"}, schema)
        assert error == "Parameter 'price' should be number, got str"

    def test_number_accepts_int_or_float(self):
        schema = {
            "type": "object",
            "properties": {"val": {"type": "number"}},
            "required": ["val"],
        }
        assert validate_tool_params({"val": 42}, schema) is None
        assert validate_tool_params({"val": 3.14}, schema) is None

    def test_wrong_type_boolean(self):
        schema = {
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
            "required": ["flag"],
        }
        error = validate_tool_params({"flag": "true"}, schema)
        assert error == "Parameter 'flag' should be boolean, got str"

    def test_wrong_type_array(self):
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        error = validate_tool_params({"items": "not_array"}, schema)
        assert error == "Parameter 'items' should be array, got str"

    def test_wrong_type_object(self):
        schema = {
            "type": "object",
            "properties": {"meta": {"type": "object"}},
            "required": ["meta"],
        }
        error = validate_tool_params({"meta": "string"}, schema)
        assert error == "Parameter 'meta' should be object, got str"

    def test_enum_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "color": {"type": "string", "enum": ["red", "green", "blue"]}
            },
            "required": ["color"],
        }
        error = validate_tool_params({"color": "yellow"}, schema)
        assert error == "Parameter 'color' must be one of: ['red', 'green', 'blue']"

    def test_enum_valid_value(self):
        schema = {
            "type": "object",
            "properties": {
                "color": {"type": "string", "enum": ["red", "blue"]}
            },
            "required": ["color"],
        }
        assert validate_tool_params({"color": "blue"}, schema) is None

    def test_unknown_params_ignored(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        error = validate_tool_params({"name": "test", "extra": "ignored"}, schema)
        assert error is None

    def test_no_schema_properties_returns_none(self):
        schema = {"type": "object"}
        error = validate_tool_params({"anything": 1}, schema)
        assert error is None

    def test_required_param_none_value(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        error = validate_tool_params({"name": None}, schema)
        assert error == "Missing required parameter: 'name'"


class TestCleanSchemaForProvider:
    def test_gemini_removes_default_examples_const(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "foo", "examples": ["a", "b"]},
                "value": {"type": "integer", "const": 42},
            },
        }
        cleaned = clean_schema_for_provider(schema, "gemini")
        props = cleaned["properties"]
        assert "default" not in props["name"]
        assert "examples" not in props["name"]
        assert "const" not in props["value"]

    def test_gemini_preserves_other_fields(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name"},
            },
        }
        cleaned = clean_schema_for_provider(schema, "gemini")
        assert cleaned["properties"]["name"]["type"] == "string"
        assert cleaned["properties"]["name"]["description"] == "The name"

    def test_xai_uses_gemini_cleaner(self):
        schema = {
            "type": "object",
            "properties": {"x": {"type": "integer", "default": 0}},
        }
        cleaned = clean_schema_for_provider(schema, "xai")
        assert "default" not in cleaned["properties"]["x"]

    def test_unknown_provider_returns_unchanged(self):
        schema = {"type": "object", "properties": {}}
        assert clean_schema_for_provider(schema, "openai") is schema

    def test_nested_object_cleaned_recursively(self):
        schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "val": {"type": "integer", "default": 99},
                    },
                },
            },
        }
        cleaned = clean_schema_for_provider(schema, "gemini")
        assert "default" not in cleaned["properties"]["nested"]["properties"]["val"]

    def test_nested_list_cleaned(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"x": {"type": "integer", "default": 0}},
            },
        }
        cleaned = clean_schema_for_provider(schema, "gemini")
        assert "default" not in cleaned["items"]["properties"]["x"]

    def test_non_dict_schema_returns_as_is(self):
        assert clean_schema_for_provider("string", "gemini") == "string"
        assert clean_schema_for_provider(None, "gemini") is None
