"""
Schema Loader Utility for Master Parameter JSON
Loads component structure from master_parameter_schema.json at runtime
"""

import json
import os
from functools import lru_cache
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_master_parameter_schema() -> Dict[str, Any]:
    """
    Load and cache master parameter schema from config

    Returns:
        Dict containing schema configuration with components and features

    Raises:
        FileNotFoundError: If schema file not found
        json.JSONDecodeError: If schema file is invalid JSON
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "master_parameter_schema.json"
        )

        with open(config_path, "r") as f:
            schema = json.load(f)

        logger.info(f"Loaded master parameter schema v{schema.get('version', 'unknown')}")
        logger.info(f"Components defined: {list(schema.get('components', {}).keys())}")

        return schema

    except FileNotFoundError:
        logger.error(f"Schema file not found at {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema file: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load schema: {e}")
        raise


def get_component_list() -> List[str]:
    """
    Get list of all component names from schema

    Returns:
        List of component names (e.g., ["power_source", "feeder", ...])
    """
    schema = load_master_parameter_schema()
    components = list(schema["components"].keys())
    logger.info(f"Component list: {components}")
    return components


def get_component_features(component_name: str) -> List[str]:
    """
    Get list of features for a specific component

    Args:
        component_name: Name of component (e.g., "power_source")

    Returns:
        List of feature names for this component

    Raises:
        KeyError: If component not found in schema
    """
    schema = load_master_parameter_schema()

    if component_name not in schema["components"]:
        raise KeyError(f"Component '{component_name}' not found in schema")

    features = schema["components"][component_name].get("features", [])
    logger.info(f"Features for {component_name}: {features}")
    return features


def get_product_name_enabled_components() -> List[str]:
    """
    Get list of components where product_name feature is enabled

    Returns:
        List of component names (e.g., ["power_source", "feeder", "cooler"])
    """
    schema = load_master_parameter_schema()
    enabled_components = schema.get("product_name_enabled_components", [])
    logger.info(f"Product name enabled for: {enabled_components}")
    return enabled_components


def validate_component_dict(component_name: str, component_dict: Dict[str, Any]) -> bool:
    """
    Validate that all keys in component dict are defined in schema

    Args:
        component_name: Name of component
        component_dict: Dict of component features to validate

    Returns:
        True if all keys are valid, False otherwise

    Logs warnings for invalid keys
    """
    try:
        valid_features = get_component_features(component_name)

        invalid_keys = []
        for key in component_dict.keys():
            if key not in valid_features:
                invalid_keys.append(key)

        if invalid_keys:
            logger.warning(
                f"Invalid keys in {component_name}: {invalid_keys}. "
                f"Valid keys: {valid_features}"
            )
            return False

        return True

    except KeyError:
        logger.error(f"Component '{component_name}' not found in schema")
        return False


@lru_cache(maxsize=1)
def load_accessory_category_mappings() -> Dict[str, Any]:
    """
    Load and cache accessory category mappings from config
    Maps user terms to Neo4j category names for LLM extraction

    Returns:
        Dict with mappings structure from accessory_category_mappings.json
    """
    try:
        config_path = os.path.join(
            os.path.dirname(__file__),
            "accessory_category_mappings.json"
        )

        with open(config_path, "r") as f:
            mappings_config = json.load(f)

        logger.info(f"Loaded accessory category mappings v{mappings_config.get('version', 'unknown')}")
        return mappings_config

    except FileNotFoundError:
        logger.warning(f"Accessory category mappings file not found at {config_path}, using defaults")
        return {"mappings": {}}
    except Exception as e:
        logger.error(f"Failed to load accessory category mappings: {e}")
        return {"mappings": {}}


def get_accessory_category_mappings() -> Dict[str, Any]:
    """
    Get accessory category mappings
    Maps user terms to Neo4j category names for LLM extraction

    Returns:
        Dict with category mappings:
        {
            "Remote": {
                "category_name": "Remote",
                "user_terms": ["remote", "remotes", ...]
            },
            ...
        }
    """
    config = load_accessory_category_mappings()
    mappings = config.get("mappings", {})
    logger.info(f"Retrieved {len(mappings)} accessory category mappings")
    return mappings


# Convenience function to get schema version
def get_schema_version() -> str:
    """Get schema version string"""
    schema = load_master_parameter_schema()
    return schema.get("version", "unknown")
