#!/usr/bin/env python3
"""
Test suite for data_schema.py

Tests all validation functions, type coercion, and edge cases.
"""

import json
import sys
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, '/home/josep/projects/claudecode-job/clients/g3dt/automation')

from data_schema import (
    DATA_ENTRY_SCHEMA,
    FieldDefinition,
    ValidationError,
    coerce_type,
    validate_field,
    validate_data,
    coerce_all,
    to_json_schema,
    get_required_fields,
    get_field_names_by_type,
)


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def record(self, test_name: str, passed: bool, error_msg: str = ""):
        if passed:
            self.passed += 1
            print(f"  PASS: {test_name}")
        else:
            self.failed += 1
            self.failures.append(f"{test_name}: {error_msg}")
            print(f"  FAIL: {test_name} - {error_msg}")


def test_validate_field_valid_values(results: TestResults):
    """Test validate_field with valid values."""
    print("\n=== Testing validate_field with valid values ===")

    # Valid string
    errors = validate_field('architect_name', 'Joan Garcia', DATA_ENTRY_SCHEMA)
    results.record("Valid string value", len(errors) == 0, str(errors))

    # Valid choice value
    errors = validate_field('building_type', 'Habitatge aïllat', DATA_ENTRY_SCHEMA)
    results.record("Valid choice value", len(errors) == 0, str(errors))

    # Valid float
    errors = validate_field('superficie_parcela_m2', 450.0, DATA_ENTRY_SCHEMA)
    results.record("Valid float value", len(errors) == 0, str(errors))

    # Valid float as string
    errors = validate_field('superficie_parcela_m2', '450.5', DATA_ENTRY_SCHEMA)
    results.record("Valid float as string", len(errors) == 0, str(errors))

    # Valid boolean
    errors = validate_field('has_basement', True, DATA_ENTRY_SCHEMA)
    results.record("Valid boolean value", len(errors) == 0, str(errors))

    # Valid int
    errors = validate_field('num_soil_levels', 2, DATA_ENTRY_SCHEMA)
    results.record("Valid int value", len(errors) == 0, str(errors))


def test_validate_field_invalid_values(results: TestResults):
    """Test validate_field with invalid values."""
    print("\n=== Testing validate_field with invalid values ===")

    # Unknown field
    errors = validate_field('unknown_field', 'value', DATA_ENTRY_SCHEMA)
    results.record(
        "Unknown field returns error",
        len(errors) > 0 and 'desconegut' in errors[0].lower(),
        f"Expected unknown field error, got: {errors}"
    )

    # Required field with None
    errors = validate_field('architect_name', None, DATA_ENTRY_SCHEMA)
    results.record(
        "Required field with None returns error",
        len(errors) > 0 and 'obligatori' in errors[0].lower(),
        f"Expected required field error, got: {errors}"
    )

    # Required field with empty string
    errors = validate_field('architect_name', '', DATA_ENTRY_SCHEMA)
    results.record(
        "Required field with empty string returns error",
        len(errors) > 0 and 'obligatori' in errors[0].lower(),
        f"Expected required field error, got: {errors}"
    )

    # Invalid choice value
    errors = validate_field('building_type', 'Invalid Type', DATA_ENTRY_SCHEMA)
    results.record(
        "Invalid choice value returns error",
        len(errors) > 0 and 'tipus' in errors[0].lower() or 'valid' in errors[0].lower(),
        f"Expected choice error, got: {errors}"
    )

    # Invalid float value
    errors = validate_field('superficie_parcela_m2', 'not_a_number', DATA_ENTRY_SCHEMA)
    results.record(
        "Invalid float value returns error",
        len(errors) > 0,
        f"Expected type error, got: {errors}"
    )

    # Invalid boolean value
    errors = validate_field('has_basement', 'maybe', DATA_ENTRY_SCHEMA)
    results.record(
        "Invalid boolean value returns error",
        len(errors) > 0,
        f"Expected type error, got: {errors}"
    )


def test_validate_data_missing_required(results: TestResults):
    """Test validate_data with missing required fields."""
    print("\n=== Testing validate_data with missing required fields ===")

    # Empty data
    errors = validate_data({})
    required_fields = get_required_fields()
    results.record(
        "Empty data returns errors for all required fields",
        len(errors) == len(required_fields),
        f"Expected {len(required_fields)} errors, got {len(errors)}: {list(errors.keys())}"
    )

    # Partial data
    partial_data = {
        'architect_name': 'Joan Garcia',
        'architect_company': 'Arquitectura Garcia',
    }
    errors = validate_data(partial_data)
    missing_required = [f for f in required_fields if f not in partial_data]
    results.record(
        "Partial data returns errors for missing required fields",
        len(errors) == len(missing_required),
        f"Expected {len(missing_required)} errors, got {len(errors)}: {list(errors.keys())}"
    )

    # Unknown field in data
    data_with_unknown = {
        'architect_name': 'Joan Garcia',
        'unknown_field': 'value',
    }
    errors = validate_data(data_with_unknown)
    results.record(
        "Unknown field in data is flagged",
        '_unknown' in errors,
        f"Expected _unknown in errors, got: {list(errors.keys())}"
    )


def test_coerce_type_strings(results: TestResults):
    """Test coerce_type for string fields."""
    print("\n=== Testing coerce_type for strings ===")

    str_field = FieldDefinition(field_type='str', required=True)

    # Normal string
    result = coerce_type('  hello world  ', str_field)
    results.record(
        "String strips whitespace",
        result == 'hello world',
        f"Expected 'hello world', got '{result}'"
    )

    # Empty string returns default
    result = coerce_type('', str_field)
    results.record(
        "Empty string returns None (default)",
        result is None,
        f"Expected None, got {result}"
    )

    # None returns default
    result = coerce_type(None, str_field)
    results.record(
        "None returns None (default)",
        result is None,
        f"Expected None, got {result}"
    )


def test_coerce_type_floats(results: TestResults):
    """Test coerce_type for float fields including Catalan decimals."""
    print("\n=== Testing coerce_type for floats (including Catalan decimals) ===")

    float_field = FieldDefinition(field_type='float', required=False, default=0.0)

    # Normal float
    result = coerce_type(123.45, float_field)
    results.record(
        "Float passes through",
        result == 123.45,
        f"Expected 123.45, got {result}"
    )

    # Integer converts to float
    result = coerce_type(123, float_field)
    results.record(
        "Integer converts to float",
        result == 123.0 and isinstance(result, float),
        f"Expected 123.0 (float), got {result} ({type(result)})"
    )

    # String with dot decimal
    result = coerce_type('123.45', float_field)
    results.record(
        "String with dot decimal converts",
        result == 123.45,
        f"Expected 123.45, got {result}"
    )

    # Catalan comma decimal
    result = coerce_type('123,45', float_field)
    results.record(
        "Catalan comma decimal '123,45' converts to 123.45",
        result == 123.45,
        f"Expected 123.45, got {result}"
    )

    # String with whitespace
    result = coerce_type('  456,78  ', float_field)
    results.record(
        "Catalan decimal with whitespace converts",
        result == 456.78,
        f"Expected 456.78, got {result}"
    )

    # Empty returns default
    result = coerce_type('', float_field)
    results.record(
        "Empty string returns default",
        result == 0.0,
        f"Expected 0.0, got {result}"
    )

    # Invalid string raises
    try:
        coerce_type('not_a_number', float_field)
        results.record("Invalid float string raises error", False, "Expected ValueError")
    except ValueError:
        results.record("Invalid float string raises error", True)


def test_coerce_type_booleans(results: TestResults):
    """Test coerce_type for boolean fields with various inputs."""
    print("\n=== Testing coerce_type for booleans ===")

    bool_field = FieldDefinition(field_type='bool', required=False, default=False)

    # Boolean True
    result = coerce_type(True, bool_field)
    results.record("Boolean True passes through", result is True, f"Got {result}")

    # Boolean False
    result = coerce_type(False, bool_field)
    results.record("Boolean False passes through", result is False, f"Got {result}")

    # String 'true'
    result = coerce_type('true', bool_field)
    results.record("'true' converts to True", result is True, f"Got {result}")

    # String 'false'
    result = coerce_type('false', bool_field)
    results.record("'false' converts to False", result is False, f"Got {result}")

    # String '1'
    result = coerce_type('1', bool_field)
    results.record("'1' converts to True", result is True, f"Got {result}")

    # String '0'
    result = coerce_type('0', bool_field)
    results.record("'0' converts to False", result is False, f"Got {result}")

    # Catalan 'si'
    result = coerce_type('si', bool_field)
    results.record("Catalan 'si' converts to True", result is True, f"Got {result}")

    # Catalan 'si' with accent
    result = coerce_type('sí', bool_field)
    results.record("Catalan 'sí' (accented) converts to True", result is True, f"Got {result}")

    # String 'yes'
    result = coerce_type('yes', bool_field)
    results.record("'yes' converts to True", result is True, f"Got {result}")

    # String 'no'
    result = coerce_type('no', bool_field)
    results.record("'no' converts to False", result is False, f"Got {result}")

    # Case insensitive
    result = coerce_type('YES', bool_field)
    results.record("'YES' (uppercase) converts to True", result is True, f"Got {result}")

    result = coerce_type('SI', bool_field)
    results.record("'SI' (uppercase) converts to True", result is True, f"Got {result}")

    # Invalid boolean raises
    try:
        coerce_type('maybe', bool_field)
        results.record("Invalid boolean string raises error", False, "Expected ValueError")
    except ValueError:
        results.record("Invalid boolean string raises error", True)


def test_coerce_type_integers(results: TestResults):
    """Test coerce_type for integer fields."""
    print("\n=== Testing coerce_type for integers ===")

    int_field = FieldDefinition(field_type='int', required=False, default=1)

    # Integer passes through
    result = coerce_type(42, int_field)
    results.record("Integer passes through", result == 42, f"Got {result}")

    # Float converts to int
    result = coerce_type(42.7, int_field)
    results.record("Float 42.7 converts to int 42", result == 42, f"Got {result}")

    # String converts
    result = coerce_type('42', int_field)
    results.record("String '42' converts to int", result == 42, f"Got {result}")

    # Empty returns default
    result = coerce_type('', int_field)
    results.record("Empty string returns default (1)", result == 1, f"Got {result}")


def test_coerce_type_choices(results: TestResults):
    """Test coerce_type for choice fields."""
    print("\n=== Testing coerce_type for choices ===")

    choice_field = FieldDefinition(
        field_type='choice',
        required=True,
        options=['option1', 'option2', 'option3']
    )

    # Valid choice
    result = coerce_type('option1', choice_field)
    results.record("Valid choice value passes", result == 'option1', f"Got {result}")

    # Valid choice with whitespace
    result = coerce_type('  option2  ', choice_field)
    results.record("Choice with whitespace is stripped", result == 'option2', f"Got {result}")

    # Invalid choice raises
    try:
        coerce_type('invalid_option', choice_field)
        results.record("Invalid choice value raises error", False, "Expected ValueError")
    except ValueError as e:
        results.record(
            "Invalid choice value raises error with options",
            'option1' in str(e) and 'option2' in str(e),
            f"Got: {e}"
        )

    # Dynamic choice field (empty options accepts any value)
    dynamic_choice = FieldDefinition(
        field_type='choice',
        required=False,
        options=[]  # Empty - dynamically populated
    )
    result = coerce_type('any_value', dynamic_choice)
    results.record(
        "Empty options list accepts any value",
        result == 'any_value',
        f"Got {result}"
    )


def test_to_json_schema(results: TestResults):
    """Test to_json_schema produces valid JSON."""
    print("\n=== Testing to_json_schema ===")

    json_schema = to_json_schema()

    # Has required top-level keys
    results.record(
        "JSON Schema has $schema key",
        '$schema' in json_schema,
        f"Keys: {list(json_schema.keys())}"
    )

    results.record(
        "JSON Schema has properties",
        'properties' in json_schema,
        f"Keys: {list(json_schema.keys())}"
    )

    results.record(
        "JSON Schema has required array",
        'required' in json_schema and isinstance(json_schema['required'], list),
        f"Got: {type(json_schema.get('required'))}"
    )

    # Required fields match
    required_in_schema = json_schema['required']
    required_from_func = get_required_fields()
    results.record(
        "Required fields match get_required_fields()",
        set(required_in_schema) == set(required_from_func),
        f"Schema: {required_in_schema}, Function: {required_from_func}"
    )

    # Can serialize to JSON string
    try:
        json_str = json.dumps(json_schema, ensure_ascii=False)
        results.record(
            "JSON Schema serializes to valid JSON",
            len(json_str) > 0,
            ""
        )
    except Exception as e:
        results.record("JSON Schema serializes to valid JSON", False, str(e))

    # Check type mappings
    props = json_schema['properties']
    results.record(
        "String field has type 'string'",
        props['architect_name']['type'] == 'string',
        f"Got: {props['architect_name'].get('type')}"
    )
    results.record(
        "Float field has type 'number'",
        props['superficie_parcela_m2']['type'] == 'number',
        f"Got: {props['superficie_parcela_m2'].get('type')}"
    )
    results.record(
        "Bool field has type 'boolean'",
        props['has_basement']['type'] == 'boolean',
        f"Got: {props['has_basement'].get('type')}"
    )
    results.record(
        "Int field has type 'integer'",
        props['num_soil_levels']['type'] == 'integer',
        f"Got: {props['num_soil_levels'].get('type')}"
    )
    results.record(
        "Choice field has enum",
        'enum' in props['building_type'],
        f"Keys: {list(props['building_type'].keys())}"
    )


def test_coerce_all(results: TestResults):
    """Test coerce_all function."""
    print("\n=== Testing coerce_all ===")

    valid_data = {
        'architect_name': '  Joan Garcia  ',
        'architect_company': 'Arquitectura Garcia',
        'building_type': 'Habitatge aïllat',
        'num_floors': 'Pb + 1Pp',
        'superficie_parcela_m2': '450,5',  # Catalan decimal
        'superficie_construida_m2': 180,
        'street_address': 'Carrer Major, 15',
        'has_basement': 'si',  # Catalan boolean
    }

    result = coerce_all(valid_data)

    # Check string trimming
    results.record(
        "coerce_all trims strings",
        result['architect_name'] == 'Joan Garcia',
        f"Got: '{result['architect_name']}'"
    )

    # Check Catalan decimal conversion
    results.record(
        "coerce_all converts Catalan decimal",
        result['superficie_parcela_m2'] == 450.5,
        f"Got: {result['superficie_parcela_m2']}"
    )

    # Check Catalan boolean conversion
    results.record(
        "coerce_all converts Catalan boolean",
        result['has_basement'] is True,
        f"Got: {result['has_basement']}"
    )

    # Check defaults are applied
    results.record(
        "coerce_all applies defaults for missing optional fields",
        result['is_urban'] is True and result['num_soil_levels'] == 1,
        f"is_urban: {result.get('is_urban')}, num_soil_levels: {result.get('num_soil_levels')}"
    )


def test_edge_cases(results: TestResults):
    """Test various edge cases."""
    print("\n=== Testing edge cases ===")

    # Empty string for optional field returns default
    field_def = FieldDefinition(field_type='str', required=False, default='default_val')
    result = coerce_type('', field_def)
    results.record(
        "Empty string for optional field returns default",
        result == 'default_val',
        f"Got: {result}"
    )

    # None for optional field returns default
    result = coerce_type(None, field_def)
    results.record(
        "None for optional field returns default",
        result == 'default_val',
        f"Got: {result}"
    )

    # ValidationError has correct attributes
    try:
        bad_data = {'architect_name': '', 'superficie_parcela_m2': 'not_a_number'}
        coerce_all(bad_data)
        results.record("coerce_all raises ValidationError", False, "Expected error")
    except ValidationError as e:
        results.record(
            "ValidationError has field_name attribute",
            hasattr(e, 'field_name') and e.field_name == 'superficie_parcela_m2',
            f"Got field_name: {getattr(e, 'field_name', 'MISSING')}"
        )


def test_helper_functions(results: TestResults):
    """Test helper functions."""
    print("\n=== Testing helper functions ===")

    # get_required_fields
    required = get_required_fields()
    expected_required = [
        'architect_name', 'architect_company', 'building_type',
        'num_floors', 'superficie_parcela_m2', 'superficie_construida_m2',
        'street_address'
    ]
    results.record(
        "get_required_fields returns correct fields",
        set(required) == set(expected_required),
        f"Got: {required}, Expected: {expected_required}"
    )

    # get_field_names_by_type
    bool_fields = get_field_names_by_type('bool')
    expected_bool = ['has_basement', 'has_retaining_walls', 'is_urban', 'is_sloped']
    results.record(
        "get_field_names_by_type('bool') returns correct fields",
        set(bool_fields) == set(expected_bool),
        f"Got: {bool_fields}"
    )

    float_fields = get_field_names_by_type('float')
    expected_float = ['superficie_parcela_m2', 'superficie_construida_m2', 'utm_x', 'utm_y', 'slope_percent']
    results.record(
        "get_field_names_by_type('float') returns correct fields",
        set(float_fields) == set(expected_float),
        f"Got: {float_fields}"
    )


def run_all_tests():
    """Run all test suites."""
    print("=" * 60)
    print("G3DT Data Schema Test Suite")
    print("=" * 60)

    results = TestResults()

    # Run all test functions
    test_validate_field_valid_values(results)
    test_validate_field_invalid_values(results)
    test_validate_data_missing_required(results)
    test_coerce_type_strings(results)
    test_coerce_type_floats(results)
    test_coerce_type_booleans(results)
    test_coerce_type_integers(results)
    test_coerce_type_choices(results)
    test_to_json_schema(results)
    test_coerce_all(results)
    test_edge_cases(results)
    test_helper_functions(results)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    total = results.passed + results.failed
    print(f"Total tests: {total}")
    print(f"Passed: {results.passed}")
    print(f"Failed: {results.failed}")

    if results.failures:
        print("\nFailed tests:")
        for failure in results.failures:
            print(f"  - {failure}")

    print("\n" + "=" * 60)
    if results.failed == 0:
        print("All tests pass")
        return 0
    else:
        print(f"{results.failed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit_code = run_all_tests()
    sys.exit(exit_code)
