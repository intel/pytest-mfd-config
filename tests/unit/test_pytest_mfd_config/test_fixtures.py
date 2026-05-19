# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for `pytest_mfd_config` package."""

import logging
import os
import re

from pydantic import SecretStr

import pytest
from cryptography.fernet import Fernet, InvalidToken
from mfd_common_libs import log_levels
from mfd_connect import AsyncConnection
from ruamel.yaml import YAML

from pytest_mfd_config.exceptions import PyTestMFDConfigException
from pytest_mfd_config.fixtures import (
    _get_connected_pairs,
    log_extra_data_after_test,
    get_connection_object,
    pass_parameters_from_config_file,
    parse_overwrite,
    _get_secrets,
    _get_encryption_obj,
    _decrypt_secrets,
    _decrypt_host_password,
    create_host_from_model,
)
from mfd_host import Host
from pytest_mfd_config.models.test_config import HostPairConnectionModel, SecretModel
from pytest_mfd_config.models.topology import ConnectionModel


class TestFixtures:
    CONNECTIONS_YAML = """
    connections:
    - bidirectional: no
      hosts: [xhc, client]
    - bidirectional: yes
      hosts: [xhc, imc]
    """

    class _DummyItem:
        funcargs = {"extra_data": {"tested_adapter": {"nvm": "80008213"}}}

    class _DummyItemWithoutDict:
        pass

    def test_connected_pairs_fixture(self):
        connections_dict = YAML(typ="safe", pure=True).load(self.CONNECTIONS_YAML)
        pairs = _get_connected_pairs(connections_dict)

        for pair in pairs:
            assert isinstance(pair, HostPairConnectionModel)

    def test_log_extra_data_after_test(self, caplog):
        caplog.set_level(logging.DEBUG)
        item = self._DummyItem()
        log_extra_data_after_test(item)
        assert "Extra data from test:" in caplog.text
        assert "{'tested_adapter': {'nvm': '80008213'}}" in caplog.text

    def test_log_extra_data_after_test_nolog(self, caplog):
        caplog.set_level(logging.DEBUG)
        item = self._DummyItemWithoutDict()
        log_extra_data_after_test(item)
        assert "Extra data from test:" not in caplog.text
        assert "{'tested_adapter': {'nvm': '80008213'}}" not in caplog.text

    def test_extra_data(self, pytester):
        """
        Testing if we didn't use json report it works fine without exception.

        In unittests don't know how to pass plugin calls.
        """
        pytester.makeconftest(
            """
            import pytest
            @pytest.fixture()
            def extra_data(request):
                try:
                    return request.node._json_report_extra.setdefault("metadata", {})
                except AttributeError:
                    if not getattr(request.config.option, "json_report", False):
                        # The user didn't request a JSON report, so the plugin didn't
                        # prepare a metadata context. We return a dummy dict, so the
                        # fixture can be used as expected without causing internal errors.
                        return {}
                    raise
            """
        )
        pytester.makepyfile(
            """
            def test_extra_data(extra_data):
                assert extra_data == {}
            """
        )
        result = pytester.runpytest()

        result.assert_outcomes(passed=1)

    def test_get_connection_object(self, mocker):
        mock = mocker.patch("pytest_mfd_config.fixtures._establish_connection")
        connection_model = ConnectionModel(connection_id=1, connection_type="SerialConnection")
        get_connection_object(connection_model)
        mock.assert_called_once_with(connection_model, None)
        mock.reset_mock()
        connection_mock = mocker.create_autospec(AsyncConnection)
        get_connection_object(connection_model, relative_connection=connection_mock)
        mock.assert_called_once_with(connection_model, connection_mock)
        mock.reset_mock()
        connection_model.relative_connection_id = 2
        connection_mock = mocker.Mock()
        connection_mock.model.connection_id = 2
        get_connection_object(connection_model, connection_list=[connection_mock])
        mock.assert_called_once_with(connection_model, connection_mock)

    def test_parse_overwrite_single_test_ovewritten(self):
        class ConfigMeta:
            option = "mev_system_tests_rxtx:sem_rules=lem,used_cp=dcpc"

            def getoption(self, flag=None) -> str:
                return self.option

        class MockConfig:
            def __init__(self):
                self.config = ConfigMeta()

        def metafunc():
            return MockConfig()

        expected_result = {"mev_system_tests_rxtx": {"sem_rules": "lem", "used_cp": "dcpc"}}
        assert expected_result == parse_overwrite(metafunc())

    def test_parse_overwrite_more_tests(self):
        class ConfigMeta:
            option = (
                "mev_system_tests_rxtx:sem_rules=lem,used_cp=dcpc;mev_system_tests_txtx:sem_rules=sem,used_cp=imccp"
            )

            def getoption(self, flag=None) -> str:
                return self.option

        class MockConfig:
            def __init__(self):
                self.config = ConfigMeta()

        def metafunc():
            return MockConfig()

        expected_result = {
            "mev_system_tests_rxtx": {"sem_rules": "lem", "used_cp": "dcpc"},
            "mev_system_tests_txtx": {"sem_rules": "sem", "used_cp": "imccp"},
        }
        assert expected_result == parse_overwrite(metafunc())

    def test_parse_overwrite_wrong_format(self):
        cmd = "mev_system_tests_rxtx:sem_rules,lem"

        class ConfigMeta:
            option = cmd

            def getoption(self, flag=None) -> str:
                return self.option

        class MockConfig:
            def __init__(self):
                self.config = ConfigMeta()

        def metafunc():
            return MockConfig()

        e = f"Cannot split parameters by '=' character. Make sure there are no extra whitespaces in --overwrite - {cmd}"
        with pytest.raises(ValueError, match=re.escape(e)):
            parse_overwrite(metafunc())

    def test_pass_parameters_from_config_file(self, mocker):
        class MockConfig:
            def getoption(self, flag=None) -> str:
                return ""

        metafunc = mocker.Mock(definition=mocker.Mock(own_markers=[]), fixturenames=["my_param"], config=MockConfig())
        mocker.patch(
            "pytest_mfd_config.fixtures.read_test_config_file", return_value={"my_param": "value", "other_param": "1"}
        )
        pass_parameters_from_config_file(metafunc)
        metafunc.parametrize.assert_called_once_with("my_param", ["value"], scope="session")

    def test_pass_parameters_from_config_file_with_marker(self, mocker):
        class MockConfig:
            def getoption(self, flag=None) -> str:
                return ""

        metafunc = mocker.Mock(
            definition=mocker.Mock(own_markers=[pytest.mark.my_marker]), fixturenames=["my_param"], config=MockConfig()
        )
        mocker.patch(
            "pytest_mfd_config.fixtures.read_test_config_file", return_value={"my_param": "value", "other_param": "1"}
        )
        pass_parameters_from_config_file(metafunc)
        metafunc.parametrize.assert_called_once_with("my_param", ["value"], scope="session")

    def test_pass_parameters_from_config_file_with_parametrize(self, mocker):
        class MockConfig:
            def getoption(self, flag=None) -> str:
                return ""

        metafunc = mocker.Mock(
            definition=mocker.Mock(own_markers=[pytest.mark.parametrize]),
            fixturenames=["my_param"],
            config=MockConfig(),
        )
        mocker.patch(
            "pytest_mfd_config.fixtures.read_test_config_file", return_value={"my_param": "value", "other_param": "1"}
        )
        pass_parameters_from_config_file(metafunc)
        metafunc.parametrize.assert_not_called()

    def test__get_secrets_with_secrets(self, mocker):
        test_config = {"secrets": [{"name": "secret1", "value": "encrypted_value1"}]}
        mocker.patch(
            "pytest_mfd_config.fixtures._decrypt_secrets",
            return_value={"secret1": SecretModel(name="secret1", value="decrypted_value1")},
        )
        mock_logger = mocker.patch("pytest_mfd_config.fixtures.logger")
        secrets = _get_secrets(test_config)
        assert secrets == {"secret1": SecretModel(name="secret1", value="decrypted_value1")}
        mock_logger.log.assert_called_with(level=log_levels.MODULE_DEBUG, msg="Getting secrets")

    def test__get_secrets_without_secrets(self, mocker):
        test_config = {}
        mock_logger = mocker.patch("pytest_mfd_config.fixtures.logger")
        secrets = _get_secrets(test_config)
        assert secrets == {}
        mock_logger.log.assert_called_with(
            level=log_levels.MODULE_DEBUG, msg="There is no 'secrets' key in test config file."
        )

    def test__get_encryption_obj_with_key(self, mocker):
        mocker.patch.dict(os.environ, {"AMBER_ENCRYPTION_KEY": "GWXohRLNALUC5zzulG6cZtPtxBKC7VA0mo-ING-_G1c="})
        fernet_obj = _get_encryption_obj()
        assert isinstance(fernet_obj, Fernet)

    def test__get_encryption_obj_without_key(self, mocker):
        mocker.patch.dict(os.environ, {"AMBER_ENCRYPTION_KEY": ""})
        with pytest.raises(PyTestMFDConfigException, match="AMBER_ENCRYPTION_KEY environment variable is not set."):
            _get_encryption_obj()

    def test__decrypt_secrets(self, mocker):
        secrets_dict = [{"name": "secret1", "value": "gAAAAABf2..."}]
        mock_cipher = mocker.Mock()
        mock_cipher.decrypt.return_value = b"decrypted_value1"
        mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", return_value=mock_cipher)
        secrets = _decrypt_secrets(secrets_dict)
        assert secrets == {"secret1": SecretModel(name="secret1", value="decrypted_value1")}
        mock_cipher.decrypt.assert_called_once_with(b"gAAAAABf2...")

    def test__decrypt_host_password_no_connections(self, mocker):
        host_model = mocker.Mock(name="host_model")
        host_model.name = "sut-1"
        host_model.connections = []

        get_encryption_obj = mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj")

        result = _decrypt_host_password(host_model)

        assert result is host_model
        get_encryption_obj.assert_not_called()

    def test__decrypt_host_password_no_decryption_needed_no_key(self, mocker):
        connection = mocker.Mock(name="connection")
        connection.connection_options = {"username": "admin", "port": 22}

        host_model = mocker.Mock(name="host_model")
        host_model.name = "sut-1"
        host_model.connections = [connection]

        with mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", side_effect=PyTestMFDConfigException):
            result = _decrypt_host_password(host_model)

        assert result is host_model

    def test__decrypt_host_password_keep_secretstr_as_is(self, mocker, caplog):
        caplog.set_level(level=log_levels.MODULE_DEBUG)
        connection = mocker.Mock(name="connection")
        connection.connection_options = {"username": "admin", "port": 22, "password": SecretStr("encrypted_pwd")}

        host_model = mocker.Mock(name="host_model")
        host_model.name = "sut-1"
        host_model.connections = [connection]
        mock_cipher = mocker.Mock()
        mock_cipher.decrypt.side_effect = InvalidToken
        mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", return_value=mock_cipher)

        result = _decrypt_host_password(host_model)
        log_message = "Value for 'password' is not a valid Fernet token. Keeping original value."
        assert log_message in caplog.text

        assert result is host_model.model_copy.return_value
        host_model.model_copy.assert_called_once()
        mock_cipher.decrypt.assert_called_once_with(b"encrypted_pwd")

    def test__decrypt_host_password_connection_without_options(self, mocker):
        conn_with_password = mocker.Mock(name="connection_with_password")
        conn_with_password.connection_options = {"password": SecretStr("encrypted_pwd")}

        conn_without_options = mocker.Mock(name="connection_without_options")
        conn_without_options.connection_options = None

        host_model = mocker.Mock(name="host_model")
        host_model.name = "sut-1"
        host_model.connections = [conn_with_password, conn_without_options]

        mocker.patch.dict(os.environ, {"AMBER_ENCRYPTION_KEY": "GWXohRLNALUC5zzulG6cZtPtxBKC7VA0mo-ING-_G1c="})
        mock_cipher = mocker.Mock()
        mock_cipher.decrypt.return_value = b"decrypted_pwd"
        mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", return_value=mock_cipher)

        conn_with_password.model_copy = mocker.Mock(return_value=conn_with_password)
        host_model.model_copy = mocker.Mock(return_value=host_model)

        result = _decrypt_host_password(host_model)

        # Verify connection without options is kept as-is (not copied)
        conn_with_password.model_copy.assert_called_once()
        # Verify host was copied with updated connections
        host_model.model_copy.assert_called_once()
        assert result is host_model

    def test__decrypt_host_password_decrypts_password_fields(self, mocker):
        class DummyConnection:
            def __init__(self, options):
                self.connection_options = options

            def model_copy(self, update):
                return DummyConnection(update["connection_options"])

        class DummyHost:
            def __init__(self, name, connections):
                self.name = name
                self.connections = connections

            def model_copy(self, update):
                return DummyHost(self.name, update["connections"])

        host_model = DummyHost(
            name="sut-1",
            connections=[
                DummyConnection(
                    {
                        "password": SecretStr("encrypted_password"),
                        "jump_host_password": SecretStr("encrypted_jump_password"),
                        "timeout": 30,
                    }
                )
            ],
        )

        mocker.patch.dict(os.environ, {"AMBER_ENCRYPTION_KEY": "GWXohRLNALUC5zzulG6cZtPtxBKC7VA0mo-ING-_G1c="})
        mock_cipher = mocker.Mock()
        mock_cipher.decrypt.side_effect = [b"plain_password", b"plain_jump_password"]
        mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", return_value=mock_cipher)

        result = _decrypt_host_password(host_model)

        decrypted_options = result.connections[0].connection_options
        assert decrypted_options["password"].get_secret_value() == "plain_password"
        assert decrypted_options["jump_host_password"].get_secret_value() == "plain_jump_password"
        assert decrypted_options["timeout"] == 30
        assert mock_cipher.decrypt.call_count == 2

    def test__decrypt_host_password_invalid_token_keeps_original(self, mocker):
        class DummyConnection:
            def __init__(self, options):
                self.connection_options = options

            def model_copy(self, update):
                return DummyConnection(update["connection_options"])

        class DummyHost:
            def __init__(self, name, connections):
                self.name = name
                self.connections = connections

            def model_copy(self, update):
                return DummyHost(self.name, update["connections"])

        host_model = DummyHost(
            name="sut-1",
            connections=[DummyConnection({"password": SecretStr("plain_password"), "timeout": 30})],
        )

        mocker.patch.dict(os.environ, {"AMBER_ENCRYPTION_KEY": "GWXohRLNALUC5zzulG6cZtPtxBKC7VA0mo-ING-_G1c="})
        mock_cipher = mocker.Mock()
        mock_cipher.decrypt.side_effect = InvalidToken
        mocker.patch("pytest_mfd_config.fixtures._get_encryption_obj", return_value=mock_cipher)

        result = _decrypt_host_password(host_model)

        decrypted_options = result.connections[0].connection_options
        assert decrypted_options["password"].get_secret_value() == "plain_password"
        assert decrypted_options["timeout"] == 30
        mock_cipher.decrypt.assert_called_once_with(b"plain_password")

    def test_create_host_from_model_basic(self, mocker):
        host_model = mocker.Mock(name="host_model")
        host_model.name = "test_host"
        host_model.connections = []
        host_model.power_mng = None
        host_model.network_interfaces = None

        mock_connection = mocker.Mock()
        mocker.patch("pytest_mfd_config.fixtures._decrypt_host_password", return_value=host_model)
        mocker.patch("pytest_mfd_config.fixtures.create_host_connections_from_model", return_value=[mock_connection])
        mocker.patch("pytest_mfd_config.fixtures.Connections")

        mock_host = mocker.Mock(spec=Host)
        mocker.patch("pytest_mfd_config.fixtures.Host", return_value=mock_host)

        result = create_host_from_model(host_model)

        assert result is mock_host

    def test_create_host_from_model_with_power_mng(self, mocker):
        host_model = mocker.Mock(name="host_model")
        host_model.name = "test_host"
        host_model.connections = []
        host_model.power_mng = mocker.Mock()
        host_model.network_interfaces = None

        mock_connection = mocker.Mock()
        mocker.patch("pytest_mfd_config.fixtures._decrypt_host_password", return_value=host_model)
        mocker.patch("pytest_mfd_config.fixtures.create_host_connections_from_model", return_value=[mock_connection])
        mocker.patch("pytest_mfd_config.fixtures.Connections")
        mock_power_mng = mocker.Mock()
        mocker.patch("pytest_mfd_config.fixtures.create_power_mng_from_model", return_value=mock_power_mng)

        mock_host = mocker.Mock(spec=Host)
        mocker.patch("pytest_mfd_config.fixtures.Host", return_value=mock_host)

        result = create_host_from_model(host_model)

        assert result is mock_host

    def test_create_host_from_model_with_network_interfaces(self, mocker):
        host_model = mocker.Mock(name="host_model")
        host_model.name = "test_host"
        host_model.connections = []
        host_model.power_mng = None
        host_model.network_interfaces = [mocker.Mock()]

        mock_connection = mocker.Mock()
        mocker.patch("pytest_mfd_config.fixtures._decrypt_host_password", return_value=host_model)
        mocker.patch("pytest_mfd_config.fixtures.create_host_connections_from_model", return_value=[mock_connection])
        mocker.patch("pytest_mfd_config.fixtures.Connections")

        mock_host = mocker.Mock(spec=Host)
        mocker.patch("pytest_mfd_config.fixtures.Host", return_value=mock_host)

        result = create_host_from_model(host_model)

        mock_host.refresh_network_interfaces.assert_called_once()
        assert result is mock_host
