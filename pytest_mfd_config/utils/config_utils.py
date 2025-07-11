# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Config utils."""

import logging
import re
from dataclasses import dataclass, InitVar
from io import StringIO
from pathlib import Path
from typing import List, TYPE_CHECKING, Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2_workarounds import MultiLineInclude
from mfd_common_libs import add_logging_level, log_levels
from ruamel.yaml import YAML

from .exceptions import ObjectCantBeFoundError

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)

if TYPE_CHECKING:
    from mfd_connect import (
        RPyCConnection,
        SSHConnection,
        TelnetConnection,
        LocalConnection,
        SolConnection,
        SerialConnection,
        TunneledSSHConnection,
    )
    from mfd_connect.tunneled_rpyc import TunneledRPyCConnection


def _hide_secrets(yaml_str: str) -> str:
    """
    Hide the entire secrets part in the YAML string.

    :param yaml_str: The original YAML string
    :return: The YAML string with the secrets part hidden
    """
    secrets_pattern = re.compile(r"secrets:\n(?:\s*-\s*name:.*\n\s*value:\n*\s*.*\n?)+", re.MULTILINE)
    return secrets_pattern.sub("secrets: [HIDDEN]\n", yaml_str)


def _log_config(filename: str, config: dict) -> None:
    """
    Log content of config dictionary.

    Load dictionary as YAML object into string and replace passwords.

    :param filename: Name of config file.
    :param config: Content of loaded config.
    """
    tmp_stream = StringIO()
    YAML().dump(config, tmp_stream)
    password_regex = r"(?P<password_field>.*password.*:\s*)(?P<password>.*)"
    content = re.sub(password_regex, r"\1******", tmp_stream.getvalue())
    content = _hide_secrets(content)
    logger.log(level=log_levels.MODULE_DEBUG, msg=f"Config file {filename} content:\n{content}")


def load_config(filename: str) -> dict:
    """Read yaml content."""
    with open(filename) as f:
        return YAML(typ="safe", pure=True).load(f)


def load_test_config(filename: str) -> dict[str, Any]:
    """
    Read yaml content and render as a jinja template.

    :param filename: Path to the file
    :return: Rendered content as a dictionary
    """
    test_config_path = Path(filename)
    env = Environment(
        loader=FileSystemLoader(test_config_path.parent), extensions=[MultiLineInclude], autoescape=select_autoescape()
    )
    rendered_content = env.get_template(test_config_path.name).render()
    return YAML(typ="safe", pure=True).load(rendered_content)


def get_item_by_name(name: str, list_of_objects: List[Any]) -> Any:
    """
    Get object from list by name.

    :param name: Name of the object
    :param list_of_objects: List of the objects we search through
    :raises: ObjectCantBeFoundError
    :return: Single object from the list
    """
    for obj in list_of_objects:
        if not hasattr(obj, "name"):
            raise ValueError(f"Objects of {type(obj)} do not have 'name' attribute.")

        if obj.name == name:
            return obj
    else:
        raise ObjectCantBeFoundError(f"There is no object on the list named - {name}")


@dataclass
class Connections:
    """Class for instantiated connections."""

    local: Optional["LocalConnection"] = None
    rpyc: Optional["RPyCConnection"] = None
    serial: Optional["SerialConnection"] = None
    sol: Optional["SolConnection"] = None
    ssh: Optional["SSHConnection"] = None
    tunneled_rpyc: Optional["TunneledRPyCConnection"] = None
    tunneled_ssh: Optional["TunneledSSHConnection"] = None
    telnet: Optional["TelnetConnection"] = None
    _connections: InitVar[List] = None

    def __post_init__(self, _connections: List):
        for connection in _connections:
            setattr(self, str(connection), connection)
