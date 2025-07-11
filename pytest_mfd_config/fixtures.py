# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Pytest plugin for handling configuration."""

import copy
import logging
import os
from typing import Any, Optional, List, TYPE_CHECKING, Dict, Tuple

import pytest  # noqa: F401
from _pytest.fixtures import FixtureRequest
from cryptography.fernet import Fernet
from mfd_common_libs import log_levels, add_logging_level
from mfd_host import Host

from pytest_mfd_config.exceptions import PyTestMFDConfigException
from pytest_mfd_config.models.test_config import HostPairConnectionModel, SecretModel
from pytest_mfd_config.models.topology import (
    SwitchModel,
    PowerMngModel,
    ConnectionModel,
    TopologyModel,
)
from pytest_mfd_config.utils.config_utils import (
    load_config,
    load_test_config,
    get_item_by_name,
    Connections,
    _log_config,
)

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)
add_logging_level(level_name="CMD", level_value=log_levels.CMD)
add_logging_level(level_name="OUT", level_value=log_levels.OUT)

if TYPE_CHECKING:
    from mfd_cli_client import CliClient
    from mfd_connect import AsyncConnection
    from mfd_powermanagement.base import PowerManagement
    from mfd_switchmanagement.base import Switch
    from pytest_mfd_config.models.topology import HostModel
    from _pytest.nodes import Item
    from _pytest.python import Metafunc


def pytest_addoption(parser: Any) -> None:
    """
    Create flags for configs.

    :param parser: Pytest parser
    """
    parser.addoption("--test_config", default=None, help="Path to the file with test configuration")
    parser.addoption("--topology_config", default=None, help="Path to the file with topology configuration")
    parser.addoption(
        "--overwrite",
        action="store",
        default={},
        help="Ability to overwrite test parameters without changing test_config.\n"
        "Format: test_name:param1=value1,param2_value2",
    )


"""Topology Config methods."""


@pytest.fixture(scope="session")
def topology_path(request: FixtureRequest) -> str:
    """Get value of --topology_config param.

    File should be in one of supported formats: JSON, YAML.
    See examples for more details.
    """
    assert request.config.getoption(
        "--topology_config"
    ), "If you want to use topology fixture, first you need to pass --topology_config param via cli"
    return request.config.getoption("--topology_config")


@pytest.fixture(scope="session")
def topology_config(topology_path: str) -> dict:
    """Get topology data from file.

    File should be in one of supported formats: JSON, YAML.
    See examples for more details.
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Reading Topology Config data.")

    config = load_config(topology_path)
    _log_config(topology_path, config)
    return config


@pytest.fixture(scope="session")
def topology(topology_config: dict) -> TopologyModel:
    """Create topology model from config file data.

    File should be in one of supported formats: JSON, YAML.
    See examples for more details.
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Creating Topology model.")

    topology_model = TopologyModel(**topology_config)

    return topology_model


def create_switch_from_model(switch_model: SwitchModel) -> "Switch":
    """
    Create IP Switch connection object based on model data.

    :param switch_model: SwitchModel (Pydantic) object
    :return: SwitchConnection object
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Preparing Switch object based on model.")

    import mfd_switchmanagement  # noqa: F401
    from mfd_switchmanagement import SSHSwitchConnection, CiscoAPIConnection

    connection_classes = {"CiscoAPIConnection": CiscoAPIConnection, "SSHSwitchConnection": SSHSwitchConnection}

    connection_type = switch_model.connection_type
    assert any(
        connection_type == con for con in connection_classes
    ), f"Not supported switch connection type, choose one from {connection_classes.keys()}"

    _ssh_key_file = switch_model.ssh_key_file
    switch_details = {
        "ip": switch_model.mng_ip_address,
        "username": switch_model.mng_user if switch_model.mng_user else "",
        "password": switch_model.mng_password.get_secret_value() if switch_model.mng_password else None,
        "connection_type": connection_classes[connection_type],
        "secret": switch_model.enable_password.get_secret_value() if switch_model.enable_password else "",
        "ssh_key_file": str(_ssh_key_file) if _ssh_key_file else None,
        "use_ssh_key": switch_model.use_ssh_key if switch_model.use_ssh_key else bool(_ssh_key_file),
        "device_type": switch_model.device_type if switch_model.device_type else "autodetect",
        "auth_timeout": switch_model.auth_timeout if switch_model.auth_timeout else 30,
        "topology": switch_model,
    }

    switch_type = switch_model.switch_type
    try:
        switch_class = getattr(mfd_switchmanagement, switch_type)
    except AttributeError:
        raise NotImplementedError(f"Switch type: {switch_type} is not supported in mfd-switchmanagement module.")
    logger.log(
        level=log_levels.MODULE_DEBUG,
        msg=f"Trying to connect to {switch_class.__name__} for switch IP: {switch_model.mng_ip_address} "
        f"using {connection_type.upper()}...",
    )

    return switch_class(**switch_details)


@pytest.fixture(scope="session")
def switches(topology: TopologyModel) -> List["Switch"]:
    """
    Get list of Switch (mfd-switchmanagement) objects based on passed topology model.

    Only switches with 'instantiate' flag set to True will be returned.

    :param topology: Fixture returning Topology model
    :return: List of switches
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Preparing Switches.")
    switch_list = []

    if not topology.switches:
        return switch_list

    for switch_model in topology.switches:
        if switch_model.instantiate:
            switch_list.append(create_switch_from_model(switch_model))

    return switch_list


def get_connection_object(
    connection_model: "ConnectionModel",
    connection_list: List["AsyncConnection"] = None,
    relative_connection: "AsyncConnection" = None,
) -> "AsyncConnection":
    """
    Create connection object from ConnectionModel.

    :param connection_model: ConnectionModel object.
    :param relative_connection: Optional object of relative connection, if passed connection_list won't be used
    :param connection_list: List of already established connection, optional, required for connections with relations
    :return: Connection object.
    """
    read_relative_connection = None if not relative_connection else relative_connection
    if read_relative_connection is None and connection_model.relative_connection_id:
        for connection in connection_list:
            if connection.model.connection_id == connection_model.relative_connection_id:
                read_relative_connection = connection
                break
    return _establish_connection(connection_model, read_relative_connection)


def _establish_connection(
    connection_model: "ConnectionModel", relative_connection: "AsyncConnection" = None
) -> "AsyncConnection":
    """
    Establish connection object from ConnectionModel.

    :param connection_model: ConnectionModel object.
    :param relative_connection: Relative connection object if required
    :return: Connection object.
    """
    import mfd_connect

    connection_class = getattr(mfd_connect, connection_model.connection_type)
    options = copy.deepcopy(connection_model.connection_options) if connection_model.connection_options else {}
    if connection_model.ip_address:
        options["ip"] = str(connection_model.ip_address)
    elif connection_model.mac_address:
        from mfd_osd_control import OsdController

        osd_details: Dict[str, Any] = connection_model.osd_details.dict()
        osd_details["password"] = osd_details["password"].get_secret_value() if osd_details.get("password") else None
        osd_controller = OsdController(**osd_details)

        if not osd_controller.does_host_exist(connection_model.mac_address):
            raise PyTestMFDConfigException(f"Passed OSD Host does not exist! {connection_model.osd_details}")
        options["ip"] = str(osd_controller.get_host_ip(connection_model.mac_address))

    if options.get("password") is not None:
        options["password"] = options.get("password").get_secret_value() if options.get("password") else ""
    if "jump_host_password" in options:
        options["jump_host_password"] = (
            options.get("jump_host_password").get_secret_value() if options.get("jump_host_password") else ""
        )

    options["model"] = connection_model
    if relative_connection:
        options["connection"] = relative_connection

    for k, v in options.items():  # "import" mfd connect consts, like mfd_connect.util.EFI_SHELL_PROMPT_REGEX
        if isinstance(v, str) and "mfd_connect" in v:
            options[k] = eval(v)
    return connection_class(**options)


def create_host_connections_from_model(host_model: "HostModel") -> List["AsyncConnection"]:
    """
    Create host connections based on data from model.

    :param host_model: HostModel (Pydantic) object
    :return: list of RPC connections
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Preparing Hosts Connections.")
    connection_list = []
    for conn in host_model.connections:
        connection_list.append(get_connection_object(conn, connection_list))
    return connection_list


def create_power_mng_from_model(power_mng_model: PowerMngModel) -> "PowerManagement":
    """
    Create PowerManagement subclass object based on data from model.

    :param power_mng_model: PowerMngModel object.
    :return: PowerManagement subclass object.
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Preparing power management object.")

    import mfd_powermanagement

    power_mng_class = getattr(mfd_powermanagement, power_mng_model.power_mng_type)

    init_method = power_mng_class.__init__
    if hasattr(init_method, "__wrapped__"):
        init_method = init_method.__wrapped__
    init_args = init_method.__code__.co_varnames

    power_mng_kwargs = {k: v for k, v in power_mng_model.dict().items() if k in init_args and v is not None}
    if power_mng_model.connection is not None and not issubclass(power_mng_class, mfd_powermanagement.pdu.PDU):
        power_mng_kwargs["connection"] = get_connection_object(power_mng_model.connection)
    return power_mng_class(**power_mng_kwargs)


def create_host_from_model(host_model: "HostModel", cli_client: Optional["CliClient"] = None) -> Host:
    """
    Create host from model data.

    :param host_model: Host model object.
    :param cli_client: CliClient used for reading extra VSIInfo in case of IPU hosts.

    CliClient used mostly when creating IPU Hosts manually (out of "hosts" fixture),
    when "instantiate" flag is set to False.
    :return: Host object
    """
    _connections = create_host_connections_from_model(host_model)

    connections = Connections(_connections=_connections)

    power_mng = create_power_mng_from_model(host_model.power_mng) if host_model.power_mng else None
    host = Host(
        connection=_connections[0],
        name=host_model.name,
        cli_client=cli_client,
        connections=connections,
        power_mng=power_mng,
        topology=host_model,
    )

    if host_model.network_interfaces:
        host.refresh_network_interfaces()
    return host


@pytest.fixture(scope="session")
def hosts(topology: TopologyModel) -> Dict[str, Host]:
    """
    Get dictionary of Host objects with associated RPC(mfd-connect) connections based on passed Topology model.

    As a key `name` of host is considered.
    ONLY Hosts with instantiate value set to True will be created.

    :param topology: Topology model object
    :return: Dictionary with hosts when 'name' is key
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Preparing Hosts based on unique names.")
    hosts_dict = dict()

    for host_model in topology.hosts:
        if host_model.instantiate:
            host = create_host_from_model(host_model=host_model)
            hosts_dict[host.name] = host
    return hosts_dict


"""Test Config methods."""


@pytest.fixture(scope="session")
def test_config_path(request: FixtureRequest) -> str:
    """Get value of --test_config param.

    File should be in one of supported formats: JSON, YAML.
    See examples for more details.
    """
    assert request.config.getoption("--test_config"), "You need to pass --test_config to pytest"
    return request.config.getoption("--test_config")


@pytest.fixture(scope="session", autouse=True)
def log_configs(request: FixtureRequest) -> None:
    """Log topology and test config on the beginning of the execution."""
    if request.config.getoption("--test_config"):
        request.getfixturevalue("test_config")
    if request.config.getoption("--topology_config"):
        request.getfixturevalue("topology_config")


@pytest.fixture(scope="session")
def test_config(test_config_path: str) -> dict:
    """Get test config data.

    File should be in one of supported formats: JSON, YAML.
    See examples for more details.
    """
    logger.log(level=log_levels.MODULE_DEBUG, msg="Reading test config data.")

    config = load_test_config(test_config_path)
    _log_config(test_config_path, config)
    return config


def read_test_config_file(metafunc: "Metafunc") -> dict[str, Any]:
    """Get config file content if available."""
    test_config = {}
    test_config_path = metafunc.config.getoption("--test_config")
    if test_config_path:
        test_config = load_test_config(test_config_path)
    return test_config


def _get_connected_pairs(test_config: Dict) -> List[HostPairConnectionModel]:
    connections_dict = test_config.get("connections", None)
    if connections_dict:
        logger.log(level=log_levels.MODULE_DEBUG, msg="Getting connected host pairs")
        return [HostPairConnectionModel(**conn) for conn in connections_dict]
    else:
        logger.log(level=log_levels.MODULE_DEBUG, msg="There is no 'connections' key in test config file.")
        return []


@pytest.fixture(scope="session")
def connected_pairs(test_config: dict) -> List[HostPairConnectionModel]:
    """Get list of host pairs."""
    return _get_connected_pairs(test_config)


@pytest.fixture(scope="session")
def connected_hosts(connected_pairs: list[HostPairConnectionModel], hosts: Dict[str, Host]) -> List[Tuple[Host, Host]]:
    """
    Get list of tuples of connected host pairs.

    :param connected_pairs: Pair of hosts
    :param hosts: Dictionary with Host objects where 'name' is key
    """
    connected_hosts = list()
    for pair in connected_pairs:
        left = get_item_by_name(name=pair.hosts[0], list_of_objects=list(hosts.values()))
        right = get_item_by_name(name=pair.hosts[1], list_of_objects=list(hosts.values()))
        connected_hosts.append((left, right))
        if pair.bidirectional:
            connected_hosts.append((right, left))
    return connected_hosts


def pass_parameters_from_config_file(metafunc: "Metafunc") -> None:
    """Parametrize test using expected parameters from config file."""
    if metafunc.definition.own_markers:
        for marker in metafunc.definition.own_markers:
            if marker.name == "parametrize":  # skip parametrize if test contains of decorator for parametrize
                return
    test_config = read_test_config_file(metafunc)
    if not test_config:
        return
    test_parameters_from_file = test_config.keys()
    test_parameters_to_pass = [param for param in metafunc.fixturenames if param in test_parameters_from_file]
    overwrite = parse_overwrite(metafunc)

    _tc = metafunc.definition.originalname
    for test_param in test_parameters_to_pass:
        if "secrets" == test_param:  # skip parametrization of secrets, it is handled in separate fixture
            continue
        org_argvalue = test_config.get(test_param)
        type_of = type(org_argvalue)
        if overwrite and _tc in overwrite and test_param in overwrite[_tc]:
            argvalue = [type_of(overwrite[_tc][test_param])]
        else:
            argvalue = org_argvalue
        if not isinstance(argvalue, list):
            argvalue = [argvalue]
        try:
            metafunc.parametrize(test_param, argvalue, scope="session")
        except ValueError:
            pass


def pytest_generate_tests(metafunc: "Metafunc") -> None:
    """Parametrize test using expected parameters from config file."""
    pass_parameters_from_config_file(metafunc)


def parse_overwrite(metafunc: "Metafunc") -> Dict[str, Any]:
    """Parse overwrite command options to dictionary: {test_name: {key: value}}.

    return: Dictionary with parsed tst case names and their parameters and new values for overwriting:
            {'test_case_name': {'param1': 'new_value1', 'param2': 'new_value2'}}
    raised ValuesError: in case when wrong format for --overwrite flag was provided.
    """
    tc_params = {}
    flag = "--overwrite"
    overwrite_input = metafunc.config.getoption(flag)
    if not overwrite_input:
        return {}
    else:
        logger.debug(f"Values for overwriting provided from: {flag} - {overwrite_input}.")

    for t in overwrite_input.split(";"):
        params = {}
        try:
            tc = t.split(":")[0]
            config_pairs = t.split(":")[1].split(",")
        except (ValueError, IndexError) as e:
            raise ValueError(
                f'Cannot parse TestCase name from {flag} flag. Acceptable format:\n"<test_case_name>:param1=new_value1"'
            ) from e
        for pair in config_pairs:
            try:
                key, value = pair.split("=")
            except ValueError as e:
                raise ValueError(
                    "Cannot split parameters by '=' character. "
                    f"Make sure there are no extra whitespaces in {flag} - {overwrite_input}"
                ) from e
            value = value.strip("'")  # in case user wrapped config value with single-quotes already
            params[key] = value
        tc_params[tc] = params
    return tc_params


# copy-paste from pytest-json-report plugin and fixture json_metadata
# added just getattr instead of accessing variable by .
# copied because we don't want pytest-json-report as requirement for that repository
# pytest-json-report is requirement in test project
@pytest.fixture()
def extra_data(request):  # noqa:ANN001,ANN201
    """Fixture to add metadata to the current test item."""
    try:
        return request.node._json_report_extra.setdefault("metadata", {})
    except AttributeError:
        if not getattr(request.config.option, "json_report", False):
            # The user didn't request a JSON report, so the plugin didn't
            # prepare a metadata context. We return a dummy dict, so the
            # fixture can be used as expected without causing internal errors.
            return {}
        raise


@pytest.hookimpl(trylast=True)
def pytest_runtest_call(item: "Item") -> None:
    """
    Call to run the test for test item (the call phase).

    The default implementation calls ``item.runtest()``.

    Log stuff from extra data defined in test.
    :param item: A basic test invocation item of pytest
    """
    log_extra_data_after_test(item)


def log_extra_data_after_test(item: "Item") -> None:
    """Add log with extra_data after test if data exists."""
    data_to_log = getattr(item, "funcargs", {}).get("extra_data", {})
    if data_to_log:
        logger.debug(f"Extra data from test: {data_to_log}")


def _get_secrets(test_config: dict) -> dict[str, SecretModel]:
    """
    Get list of secrets from test config file.

    :param test_config: Test config file
    :return: List of secrets
    """
    secrets_dict = test_config.get("secrets", [])
    if secrets_dict:
        logger.log(level=log_levels.MODULE_DEBUG, msg="Getting secrets")
        return _decrypt_secrets(secrets_dict)
    else:
        logger.log(level=log_levels.MODULE_DEBUG, msg="There is no 'secrets' key in test config file.")
        return {}


def _get_encryption_obj() -> Fernet:
    """
    Get encryption object.

    Create cryptography.Fernet object based on encryption key from environment variable.

    Fernet guarantees that a message encrypted using it cannot be manipulated or read without the key.
    Fernet is an implementation of symmetric (also known as “secret key”) authenticated cryptography.
    :return: Fernet object
    """
    encryption_key = os.environ.get("AMBER_ENCRYPTION_KEY")
    if not encryption_key:
        raise PyTestMFDConfigException("AMBER_ENCRYPTION_KEY environment variable is not set.")
    return Fernet(encryption_key)


def _decrypt_secrets(secrets_dict: list[dict[str, str]]) -> dict[str, SecretModel]:
    """
    Decrypt secrets from secrets_dict.

    :param secrets_dict: List of secrets
    :return: Decrypted secrets
    """
    secrets = {}
    cipher = _get_encryption_obj()
    for secret in secrets_dict:
        secret_name = secret.get("name")
        secret_value = secret.get("value").encode("utf-8")
        # Decrypt string back to plaintext
        secret_value = cipher.decrypt(secret_value).decode()
        secrets[secret_name] = SecretModel(name=secret_name, value=secret_value)
    return secrets


@pytest.fixture(scope="session")
def secrets(test_config: dict) -> dict[str, SecretModel]:
    """Get list of secrets."""
    return _get_secrets(test_config)
