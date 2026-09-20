"""cfgstack: 配置分层合并包。"""

from cfgstack.stack import (
    ConfigStack,
    MissingKeyError,
    load_config,
    merge_dicts,
    merge_profiles,
    required_subset,
)

__all__ = [
    "ConfigStack",
    "MissingKeyError",
    "load_config",
    "merge_dicts",
    "merge_profiles",
    "required_subset",
]
