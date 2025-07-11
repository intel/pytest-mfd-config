# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Test utils."""

from textwrap import dedent

import pytest
from jinja2 import Template
from mfd_common_libs import log_levels

from pytest_mfd_config.utils.config_utils import (
    get_item_by_name,
    load_config,
    _log_config,
    load_test_config,
    _hide_secrets,
)
from pytest_mfd_config.utils.exceptions import ObjectCantBeFoundError


class FooWithName:
    """FooWithName Test Class."""

    name: str

    def __init__(self, name: str) -> None:
        """Create FooWithName object."""
        self.name = name


class FooWithoutName:
    """FooWithoutName Test Class."""

    id: int  # noqa A003

    def __init__(self, id: int) -> None:  # noqa A002
        """Create FooWithoutName object."""
        self.id = id
        self.topology = None


class TestUtils:
    def test_get_item_by_name_success(self):
        foo_1 = FooWithName(name="a")
        foo_2 = FooWithName(name="b")
        foo_3 = FooWithName(name="c")

        list_of_objects = [foo_1, foo_2, foo_3]

        assert foo_1 == get_item_by_name(name="a", list_of_objects=list_of_objects)

    def test_get_item_by_name_not_found(self):
        foo_1 = FooWithName(name="a")
        foo_2 = FooWithName(name="b")
        foo_3 = FooWithName(name="c")

        list_of_objects = [foo_1, foo_2, foo_3]
        with pytest.raises(ObjectCantBeFoundError):
            get_item_by_name(name="d", list_of_objects=list_of_objects)

    def test_get_item_by_name_missing_name(self):
        list_of_objects = [FooWithoutName(id=1), FooWithoutName(id=2)]
        with pytest.raises(ValueError):
            get_item_by_name(name="d", list_of_objects=list_of_objects)

    def test_load_config(self, mocker):
        content = dedent(
            """\
        ---
        metadata:
          version: '2.5'
        hosts:
        - name: sut
          mng_ip_address: 10.0.0.1
          instantiate: true
          role: sut
          network_interfaces:
          - pci_device: 8086:1572
            interface_index: 0
            ips:
              - value: 1.1.1.1
                mask: 8
          connections:
          - ip_address: 10.0.0.1
            connection_type: SSHConnection       # type of mfd-connect connection
            connection_options:
              username: root                     # credentials for SSH connection
              password: abc                    # acceptable are all input parameters for this type of connection"""
        )
        mocker.patch("builtins.open", mocker.mock_open(read_data=content))
        assert load_config("")

    def test_load_test_config(self, mocker):
        filename = "test_config.yaml"
        yaml_content = "key: value"

        mocker.patch("builtins.open", mocker.mock_open(read_data=yaml_content))
        mocker.patch(
            "pytest_mfd_config.utils.config_utils.Environment.get_template", return_value=Template(yaml_content)
        )
        result = load_test_config(filename)

        assert result == {"key": "value"}

    def test__log_config(self, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        config = {
            "metadata": {"version": "2.1"},
            "hosts": [
                {
                    "name": "sut",
                    "mng_ip_address": "10.0.0.1",
                    "instantiate": True,
                    "role": "sut",
                    "network_interfaces": [
                        {"pci_device": "8086:1572", "interface_index": 0, "ips": [{"value": "1.1.1.1", "mask": 8}]}
                    ],
                    "connections": [
                        {
                            "ip_address": "10.0.0.1",
                            "connection_type": "SSHConnection",
                            "connection_options": {"username": "root", "password": "abc"},
                        }
                    ],
                }
            ],
        }
        _log_config("topology_config.yaml", config)
        assert "password: abc" not in caplog.text
        assert "password: ******" in caplog.text

    def test__log_config_without_password(self, caplog):
        caplog.set_level(log_levels.MODULE_DEBUG)
        config = {
            "metadata": {"version": "2.1"},
            "hosts": [
                {
                    "name": "sut",
                    "mng_ip_address": "10.0.0.1",
                    "instantiate": True,
                    "role": "sut",
                    "network_interfaces": [
                        {"pci_device": "8086:1572", "interface_index": 0, "ips": [{"value": "1.1.1.1", "mask": 8}]}
                    ],
                    "connections": [
                        {
                            "ip_address": "10.0.0.1",
                            "connection_type": "SSHConnection",
                            "connection_options": {"username": "root", "password": "abc"},
                        }
                    ],
                }
            ],
        }
        _log_config("topology_config.yaml", config)
        assert "- name: sut" in caplog.text

    def test__hide_secrets(self):
        yaml_str = dedent(
            """\
            secrets:
              - name: secret1
                value: abc123
              - name: secret2
                value: def456
            """
        )
        expected_result = "secrets: [HIDDEN]\n"
        assert _hide_secrets(yaml_str) == expected_result

    def test__hide_secrets_no_secrets(self):
        yaml_str = dedent(
            """\
            metadata:
              version: '2.5'
            hosts:
              - name: sut
                mng_ip_address: 10.0.0.1
            """
        )
        assert _hide_secrets(yaml_str) == yaml_str
