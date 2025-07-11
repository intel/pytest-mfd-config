# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Test Config unittests."""

from textwrap import dedent

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from mfd_model.config import HostPairConnectionModel


class TestTestConfig:
    CONNECTION_YAML = dedent(
        """
      bidirectional: false
      hosts: [xhc, client]
    """
    )

    def test_connections_from_file_correctly_parsed(self):
        yaml_loader = YAML(typ="safe", pure=True)
        host_pair_dict = yaml_loader.load(self.CONNECTION_YAML)
        host_pair = HostPairConnectionModel(**host_pair_dict)
        assert host_pair

    def test_connections_hosts_key_length_check_pass(self):
        assert isinstance(HostPairConnectionModel(bidirectional=True, hosts=["aaa", "bbb"]), HostPairConnectionModel)

    def test_connections_hosts_key_length_check_fail(self):
        with pytest.raises(ValueError):
            HostPairConnectionModel(bidirectional=True, hosts=["aaa", "bbb", "ccc"])

    def test_connections_bidirectional_is_not_boolean(self):
        with pytest.raises(ValidationError):
            HostPairConnectionModel(bidirectional="foo", hosts=["aaa", "bbb"])
