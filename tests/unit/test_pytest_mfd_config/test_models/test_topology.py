# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Tests for topology models."""

import re

import pytest
from mfd_typing.data_structures import IPUHostType

from ruamel.yaml import YAML
from pydantic import ValidationError

from pytest_mfd_config.fixtures import create_power_mng_from_model
from mfd_model.config import IPModel, ExtraInfoModel, OSDControllerModel
from pytest_mfd_config.models.topology import (
    TopologyModel,
    NetworkInterfaceModel,
    PowerMngModel,
    ConnectionModel,
    SUTModel,
    ServiceModel,
    SchemaMetadata,
    HostModel,
    SwitchModel,
)
from textwrap import dedent

from pytest_mfd_config.utils.exceptions import NotUniqueHostsNamesError


class TestSwitch:
    SWITCH_OK = dedent(
        """
    metadata:
      version: '2.5'
    switches:
    - name: Dell 123456
      mng_ip_address: 10.1.2.4
      mng_user: foo
      mng_password: bar
      instantiate: true
      switch_type: DellOS9_7000
      device_type: Dell
      connection_type: SSHSwitchConnection
      ssh_key_file:
      use_ssh_key:
      enable_password:
      auth_timeout:
      switch_ports:
      vlans:
    """
    )

    SWITCH_FAIL = dedent(
        """
    metadata:
      version: '2.5'
    switches:
    - name: Dell 123456
      mng_ip_address: 10.1.2.4
      mng_user: foo
      mng_password: bar
      instantiate: true
      switch_type: DUNNO
      device_type: Dell
      connection_type: SSHSwitchConnection
      ssh_key_file:
      use_ssh_key:
      enable_password:
      auth_timeout:
      switch_ports:
      vlans:
    """
    )

    def test_yaml_to_switch_model_success(self):
        topology_dict = YAML(typ="safe", pure=True).load(self.SWITCH_OK)
        model = TopologyModel(**topology_dict)
        assert isinstance(model, TopologyModel)

    def test_yaml_to_switch_model_failure(self):
        topology_dict = YAML(typ="safe", pure=True).load(self.SWITCH_FAIL)
        with pytest.raises(ValueError):
            TopologyModel(**topology_dict)


class TestTopology:
    TOPOLOGY_OK = dedent(
        """
    {
      "metadata": {
        "version": "2.5"
      },
      "switches": [
        {
          "name": "Dell 123456",
          "mng_ip_address": "10.1.2.4",
          "mng_user": "foo",
          "mng_password": "bar",
          "instantiate": true,
          "switch_type": "DellOS9_7000",
          "device_type": "Dell",
          "connection_type": "SSHSwitchConnection",
          "ssh_key_file": null,
          "use_ssh_key": null,
          "enable_password": null,
          "auth_timeout": null,
          "switch_ports": null,
          "vlans": null
        },
        {
          "name": "Mellanox_ABC",
          "mng_ip_address": "10.1.2.3",
          "mng_user": "foo",
          "mng_password": "bar",
          "instantiate": true,
          "switch_type": "Mellanox25G",
          "device_type": "Mellanox",
          "connection_type": "SSHSwitchConnection",
          "ssh_key_file": null,
          "use_ssh_key": null,
          "enable_password": null,
          "auth_timeout": null,
          "switch_ports": null,
          "vlans": null
        }
      ],
      "services": [
        {
          "type": "nsx",
          "username": "foo",
          "password": "bar",
          "ip_address": "1.2.3.4"
        }
      ],
      "hosts": [
        {
          "name": "Zen",
          "instantiate": true,
          "role": "sut",
          "network_interfaces": [
            {
              "interface_name": "eth2",
              "ips": [
                {
                  "value": "1.2.1.1",
                  "mask": 8
                }
              ],
              "switch_name": "Dell 123456",
              "switch_port": "Eth1/1",
              "vlan": "100"
            }
          ],
          "connections": [
            {
              "ip_address": "10.10.10.10",
              "connection_type": "RPyCConnection",
              "connection_options": {
                "port": 18813
              }
            }
          ],
          "extra_info":
              {
              "suffix": "suff",
              "datastore": [
              "datastore1",
              "datastore2"
              ]
          }
        },
        {
          "name": "Ken",
          "instantiate": true,
          "role": "client",
          "network_interfaces": [
            {
              "interface_name": "eth2",
              "ips": [
                {
                  "value": "1.1.1.1",
                  "mask": 8
                }
              ],
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            },
            {
              "interface_name": "eth3",
              "ips": [
                {
                  "value": "1.1.1.1",
                  "mask": 8
                }
              ],
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            },
            {
              "interface_name": "eth4",
              "ips": null,
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            }
          ],
          "connections": [
            {
              "ip_address": "10.10.10.11",
              "connection_type": "RPyCConnection",
              "connection_options": {
                "port": 18814
              }
            }
          ]
        }
      ],
      "vms": null,
      "containers": null
    }
    """
    )

    TOPOLOGY_FAILURE = dedent(
        """
      {
      "metadata": {
        "version": "2.5"
      },
      "switches": [
        {
          "name": "Dell 123456",
          "mng_ip_address": "10.1.2.4",
          "mng_user": "foo",
          "mng_password": "bar",
          "instantiate": true,
          "switch_type": "DellOS9_7000",
          "device_type": "Dell",
          "connection_type": "SSHSwitchConnection",
          "ssh_key_file": null,
          "use_ssh_key": null,
          "enable_password": null,
          "auth_timeout": null,
          "switch_ports": null,
          "vlans": null
        },
        {
          "name": "Mellanox_ABC",
          "mng_ip_address": "10.1.2.3",
          "mng_user": "foo",
          "mng_password": "bar",
          "instantiate": true,
          "switch_type": "Mellanox25G",
          "device_type": "Mellanox",
          "connection_type": "SSHSwitchConnection",
          "ssh_key_file": null,
          "use_ssh_key": null,
          "enable_password": null,
          "auth_timeout": null,
          "switch_ports": null,
          "vlans": null
        }
      ],
      "services": [
        {
          "type": "dunno",
          "username": "foo",
          "password": "bar",
          "ip_address": "1.2.3.4"
        }
      ],
      "hosts": [
        {
          "name": "Zen",
          "instantiate": true,
          "role": "sut",
          "network_interfaces": [
            {
              "interface_name": "eth2",
              "ips": [
                {
                  "value": "1.2.1.1",
                  "mask": 8
                }
              ],
              "switch_name": "Dell 123456",
              "switch_port": "Eth1/1",
              "vlan": "100"
            }
          ],
          "connections": [
            {
              "ip_address": "10.10.10.10",
              "connection_type": "RPyCConnection",
              "connection_options": {
                "port": 18813
              }
            }
          ],
          "power_mng": {
            "power_mng_type": "Raritan",
            "ip": "1.1.1.1",
            "community_string": "private"
          }
        },
        {
          "name": "Ken",
          "instantiate": true,
          "role": "client",
          "network_interfaces": [
            {
              "interface_name": "eth2",
              "ips": [
                {
                  "value": "1.1.1.1",
                  "mask": 8
                }
              ],
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            },
            {
              "interface_name": "eth3",
              "ips": [
                {
                  "value": "1.1.1.1",
                  "mask": 8
                }
              ],
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            },
            {
              "interface_name": "eth4",
              "ips": null,
              "switch_name": null,
              "switch_port": null,
              "vlan": null
            }
          ],
          "connections": [
            {
              "ip_address": "10.10.10.11",
              "connection_type": "RPyCConnection",
              "connection_options": {
                "port": 18814
              }
            }
          ],
          "power_mng": {
              "power_mng_type": "Raritan",
              "ip": "1.1.1.1",
              "community_string": "private"
          }
        }
      ],
      "vms": null,
      "containers": null
    }
    """
    )

    TOPOLOGY_EXTRA_FIELDS = dedent(
        """
    {
      "metadata": {
        "version": "2.5"
      },
      "switches": [],
      "foo": "bar"
    }
    """
    )

    TOPOLOGY_REPEATED_NAMES = dedent(
        """
    {
      "metadata": {
        "version": "2.5"
      },
      "hosts": [
        {
          "name": "Ken",
          "instantiate": true,
          "role": "client"
        },
        {
          "name": "Ken",
          "instantiate": true,
          "role": "client"
        }
      ]
    }
    """
    )

    TOPOLOGY_SWITCH_NAME_MISSING_SWITCHES = dedent(
        """
    {
        "metadata": {
            "version": "2.5"
        },
        "hosts": [
            {
                "name": "Ken",
                "instantiate": true,
                "role": "client",
                "network_interfaces": [
                    {
                        "interface_name": "eth2",
                        "switch_name": "Mellanox 25G",
                        "switch_port": null,
                        "vlan": null
                    }
                ]
            }
        ]
    }
    """
    )

    TOPOLOGY_SWITCH_DETAILS_MISSING_FOR_SWITCH_NAME = dedent(
        """
    {
        "metadata": {
            "version": "2.5"
        },
        "switches": [
            {
                "name": "Dell X",
                "mng_ip_address": "10.1.2.4",
                "mng_user": "foo",
                "mng_password": "bar",
                "instantiate": true,
                "switch_type": "DellOS9_7000",
                "device_type": "Dell",
                "connection_type": "SSHSwitchConnection",
                "ssh_key_file": null,
                "use_ssh_key": null,
                "enable_password": null,
                "auth_timeout": null,
                "switch_ports": null,
                "vlans": null
            },
            {
                "name": "Mellanox_ABC",
                "mng_ip_address": "10.1.2.3",
                "mng_user": "foo",
                "mng_password": "bar",
                "instantiate": true,
                "switch_type": "Mellanox25G",
                "device_type": "Mellanox",
                "connection_type": "SSHSwitchConnection",
                "ssh_key_file": null,
                "use_ssh_key": null,
                "enable_password": null,
                "auth_timeout": null,
                "switch_ports": null,
                "vlans": null
            }
        ],
        "hosts": [
            {
                "name": "Zen",
                "instantiate": true,
                "role": "sut",
                "network_interfaces": [
                    {
                        "interface_name": "eth2",
                        "ips": [
                            {
                                "value": "1.2.1.1",
                                "mask": 8
                            }
                        ],
                        "switch_name": "Dell 123456",
                        "switch_port": "Eth1/1",
                        "vlan": "100"
                    }
                ],
                "connections": [
                    {
                        "ip_address": "10.10.10.10",
                        "connection_type": "RPyCConnection",
                        "connection_options": {
                            "port": 18813
                        }
                    }
                ],
                "power_mng": {
                    "power_mng_type": "Raritan",
                    "ip": "1.1.1.1",
                    "community_string": "private"
                }
            },
            {
                "name": "Ken",
                "instantiate": true,
                "role": "client",
                "network_interfaces": [
                    {
                        "interface_name": "eth2",
                        "ips": [
                            {
                                "value": "1.1.1.1",
                                "mask": 8
                            }
                        ],
                        "switch_name": null,
                        "switch_port": null,
                        "vlan": null
                    },
                    {
                        "interface_name": "eth4",
                        "ips": null,
                        "switch_name": null,
                        "switch_port": null,
                        "vlan": null
                    }
                ],
                "connections": [
                    {
                        "ip_address": "10.10.10.11",
                        "connection_type": "RPyCConnection",
                        "connection_options": {
                            "port": 18814
                        }
                    }
                ]
            }
        ],
        "vms": null,
        "containers": null
    }
    """
    )

    TOPOLOGY_SWITCH_NAME_SWITCH_DETAILS = dedent(
        """
    {
    "metadata": {
        "version": "2.5"
    },
    "switches": [
        {
            "name": "Dell X",
            "mng_ip_address": "10.1.2.4",
            "mng_user": "foo",
            "mng_password": "bar",
            "instantiate": true,
            "switch_type": "DellOS9_7000",
            "device_type": "Dell",
            "connection_type": "SSHSwitchConnection",
            "ssh_key_file": null,
            "use_ssh_key": null,
            "enable_password": null,
            "auth_timeout": null,
            "switch_ports": null,
            "vlans": null
        },
        {
            "name": "Mellanox_ABC",
            "mng_ip_address": "10.1.2.3",
            "mng_user": "foo",
            "mng_password": "bar",
            "instantiate": true,
            "switch_type": "Mellanox25G",
            "device_type": "Mellanox",
            "connection_type": "SSHSwitchConnection",
            "ssh_key_file": null,
            "use_ssh_key": null,
            "enable_password": null,
            "auth_timeout": null,
            "switch_ports": null,
            "vlans": null
        }
    ],
    "hosts": [
        {
            "name": "Zen",
            "instantiate": true,
            "role": "sut",
            "network_interfaces": [
                {
                    "interface_name": "eth2",
                    "ips": [
                        {
                            "value": "1.2.1.1",
                            "mask": 8
                        }
                    ],
                    "switch_name": "Mellanox_ABC",
                    "switch_port": "Eth1/1",
                    "vlan": "100"
                }
            ],
            "connections": [
                {
                    "ip_address": "10.10.10.10",
                    "connection_type": "RPyCConnection",
                    "connection_options": {
                        "port": 18813
                    }
                }
            ],
            "power_mng": {
                "power_mng_type": "Raritan",
                "ip": "1.1.1.1",
                "community_string": "private"
            }
        },
        {
            "name": "Ken",
            "instantiate": true,
            "role": "client",
            "network_interfaces": [
                {
                    "interface_name": "eth2",
                    "ips": [
                        {
                            "value": "1.1.1.1",
                            "mask": 8
                        }
                    ],
                    "switch_name": "Mellanox_ABC",
                    "switch_port": null,
                    "vlan": null
                },
                {
                    "interface_name": "eth4"
                }
            ],
            "connections": [
                {
                    "ip_address": "10.10.10.11",
                    "connection_type": "RPyCConnection",
                    "connection_options": {
                        "port": 18814
                    }
                }
            ]
        }
    ],
    "vms": null,
    "containers": null
    }
    """
    )

    def test_json_to_models_success(self):
        topology_from_json = TopologyModel.parse_raw(self.TOPOLOGY_OK)
        assert isinstance(topology_from_json, TopologyModel)

    def test_json_to_models_failure_wrong_service_value(self):
        e = "Input should be 'vcsa', 'nsx' or 'dhcp' [type=literal_error, input_value='dunno', input_type=str]"
        with pytest.raises(ValidationError, match=re.escape(e)):
            TopologyModel.parse_raw(self.TOPOLOGY_FAILURE)

    def test_json_no_extra_fields(self):
        e = "Extra inputs are not permitted [type=extra_forbidden, input_value='bar', input_type=str]"
        with pytest.raises(ValidationError, match=re.escape(e)):
            TopologyModel.parse_raw(self.TOPOLOGY_EXTRA_FIELDS)

    def test_json_not_unique_host_names(self):
        e = "Hosts 'name' field must be unique in YAML topology, stopping..."
        with pytest.raises(NotUniqueHostsNamesError, match=re.escape(e)):
            TopologyModel.parse_raw(self.TOPOLOGY_REPEATED_NAMES)

    def test_create_power_mng_from_model(self):
        """Test if getter for power management basing on model correctly call constructor with defaults."""
        model = PowerMngModel(power_mng_type="Raritan", ip="10.10.10.10")
        pdu = create_power_mng_from_model(model)
        assert pdu._udp_port is not None
        model = PowerMngModel(power_mng_type="Raritan", ip="10.10.10.10", udp_port=111)
        pdu = create_power_mng_from_model(model)
        assert pdu._udp_port == 111

    def test_version_must_fit_failure(self):
        with pytest.raises(ValueError, match="Wrong schema version"):
            SchemaMetadata.version_must_fit("1.3")

    def test_switch_name_added_only_to_interface(self):
        e = (
            "There are switch names in network interfaces: ['Mellanox 25G'] which are not detailed described in "
            "switches YAML section."
        )
        with pytest.raises(ValueError, match=re.escape(e)):
            TopologyModel.parse_raw(self.TOPOLOGY_SWITCH_NAME_MISSING_SWITCHES)

    def test_switch_name_missing_in_switches(self):
        e = (
            "Defined switch name: Dell 123456 for network interfaces has missing connection details in switches"
            " YAML section."
        )
        with pytest.raises(ValueError, match=re.escape(e)):
            TopologyModel.parse_raw(self.TOPOLOGY_SWITCH_DETAILS_MISSING_FOR_SWITCH_NAME)

    def test_switch_name_in_second_switch(self):
        model = TopologyModel.parse_raw(self.TOPOLOGY_SWITCH_NAME_SWITCH_DETAILS)
        assert model.hosts[0].network_interfaces[0].switch_name == "Mellanox_ABC"
        assert model.switches[1].name == "Mellanox_ABC"

    def test_topology_validator_with_ipu_hosts_models(self):
        topology = TopologyModel(
            metadata=SchemaMetadata(version="2.5"),
            hosts=[
                HostModel(
                    name="machine_2130",
                    role="sut",
                    machine_type="ipu",
                    ipu_host_type="imc",
                    connections=[
                        ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.10")
                    ],
                ),
                HostModel(
                    name="machine_2131",
                    role="sut",
                    machine_type="ipu",
                    ipu_host_type="acc",
                    connections=[
                        ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.11")
                    ],
                ),
            ],
        )
        assert isinstance(topology, TopologyModel)

    def test_topology_validator_with_switch_models(self):
        topology = TopologyModel(
            metadata=SchemaMetadata(version="2.5"),
            hosts=[
                HostModel(
                    name="machine_2130",
                    role="sut",
                    connections=[
                        ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.10")
                    ],
                    network_interfaces=[NetworkInterfaceModel(interface_name="eth2", switch_name="Dell 123456")],
                ),
                HostModel(
                    name="machine_2131",
                    role="sut",
                    machine_type="ipu",
                    ipu_host_type="acc",
                    connections=[
                        ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.11")
                    ],
                ),
            ],
            switches=[
                SwitchModel(
                    name="Dell 123456",
                    mng_ip_address="10.10.10.10",
                    switch_type="DellOS9",
                    connection_type="SSHSwitchConnection",
                )
            ],
        )
        assert topology.hosts[0].network_interfaces[0].switch_name == "Dell 123456"

    class TestNetworkInterfaceModel:
        """NetworkInterfaceModel Test class."""

        def test_no_id(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(ips=[IPModel(value="10.10.10.10")])

        def test_pci_address_wrong_format(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_address="foo")

        def test_pci_address_other_fields(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_address="18:00.1", pci_device="8086:1572", interface_index=0)

            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_address="18:00.1", interface_name="foo")

        def test_interface_name_other_fields(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_device="8086:1572", interface_name=0)

        def test_speed_family_missing_fields(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(speed="40g")

            with pytest.raises(ValueError):
                NetworkInterfaceModel(family="NNT")

            with pytest.raises(ValueError):
                NetworkInterfaceModel(family="NNT", speed="10G")

        def test_speed_family_pass(self):
            assert isinstance(NetworkInterfaceModel(speed="40g", interface_index=-1), NetworkInterfaceModel)
            assert isinstance(NetworkInterfaceModel(speed="100G", random_interface=True), NetworkInterfaceModel)
            assert isinstance(NetworkInterfaceModel(speed="18:00.1", interface_index=-1), NetworkInterfaceModel)

        def test_pci_address_pass(self):
            assert isinstance(NetworkInterfaceModel(pci_address="18:00.1"), NetworkInterfaceModel)

        def test_pci_device_short_pass(self):
            assert isinstance(NetworkInterfaceModel(pci_device="8086:1572", interface_index=2), NetworkInterfaceModel)

        def test_pci_device_long_pass(self):
            assert isinstance(
                NetworkInterfaceModel(pci_device="8086:1572:0000:001a", interface_index="2"), NetworkInterfaceModel
            )
            assert isinstance(
                NetworkInterfaceModel(pci_device="8086:1572:0000:001A", interface_index=0), NetworkInterfaceModel
            )

        def test_pci_device_wrong_format(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_device="8086:1572:0000:001h", interface_index="2")

        def test_pci_device_missing_index(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_device="8086:1572")

        def test_index_and_indexes_passed_together(self):
            with pytest.raises(ValueError):
                NetworkInterfaceModel(pci_device="8086:1572", interface_index="2", interface_indexes=["1", "2"])

        def test_index_and_indexes_passed_normally(self):
            assert isinstance(NetworkInterfaceModel(pci_device="8086:1572", interface_index="2"), NetworkInterfaceModel)
            assert isinstance(
                NetworkInterfaceModel(pci_device="8086:1572", interface_indexes=["1", "2"]), NetworkInterfaceModel
            )

        def test_switch_port_and_switch_name(self):
            assert isinstance(
                NetworkInterfaceModel(speed="40g", interface_index=-1, switch_port="Eth1/1", switch_name="Dell 123456"),
                NetworkInterfaceModel,
            )
            assert isinstance(
                NetworkInterfaceModel(speed="40g", interface_index=-1, switch_name="Dell 123456"),
                NetworkInterfaceModel,
            )

        def test_switch_port_missing_switch_name(self):
            with pytest.raises(ValueError, match=re.escape("Switch_port: Eth1/1 provided without switch_name.")):
                NetworkInterfaceModel(speed="40g", interface_index=-1, switch_port="Eth1/1")

        @pytest.mark.parametrize(
            "first_interfaces_indexes, second_interfaces_indexes", [(["2"], ["2"]), (["1", "2"], ["2", "3"])]
        )
        def test_eq(self, first_interfaces_indexes, second_interfaces_indexes):
            assert NetworkInterfaceModel(
                pci_device="8086:1572", interface_indexes=first_interfaces_indexes
            ) == NetworkInterfaceModel(pci_device="8086:1572", interface_indexes=second_interfaces_indexes)
            assert NetworkInterfaceModel(
                family="CNV", interface_indexes=first_interfaces_indexes
            ) == NetworkInterfaceModel(family="CNV", interface_indexes=second_interfaces_indexes)
            assert NetworkInterfaceModel(
                speed="@2G", interface_indexes=first_interfaces_indexes
            ) == NetworkInterfaceModel(speed="@2G", interface_indexes=second_interfaces_indexes)
            assert NetworkInterfaceModel(
                speed="@2G", interface_indexes=first_interfaces_indexes
            ) != NetworkInterfaceModel(speed="@1G", interface_indexes=second_interfaces_indexes)

        def test_eq_index_and_indexes(self):
            assert NetworkInterfaceModel(speed="@1G", interface_index="1") == NetworkInterfaceModel(
                speed="@1G", interface_indexes=["1", "2"]
            )
            assert NetworkInterfaceModel(speed="@1G", interface_indexes=["1", "2"]) == NetworkInterfaceModel(
                speed="@1G", interface_index="1"
            )

    class TestConnectionModel:
        """ConnectionModel Test class."""

        def test_ip_address_is_required(self):
            with pytest.raises(ValueError):
                ConnectionModel(connection_type="RPyCConnection")

            ConnectionModel(
                connection_type="RPyCConnection",
                mac_address="aa:bb:cc:dd:ee:ff",
                osd_details=OSDControllerModel(base_url="some_url.com"),
            )
            ConnectionModel(connection_type="RPyCConnection", ip_address="10.0.0.1")
            ConnectionModel(connection_type="SerialConnection")

            with pytest.raises(ValueError):
                # missing osd_details
                ConnectionModel(connection_type="RPyCConnection", mac_address="aa:bb:cc:dd:ee:ff")

    class TestSUTModel:
        """SUTModel Test class."""

        def test_sort_connections(self):
            connections = [
                ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.10"),
                ConnectionModel(connection_type="SerialConnection", relative_connection_id=1),
                ConnectionModel(connection_id=2, connection_type="RPyCConnection", ip_address="10.10.10.10"),
            ]
            model = SUTModel(role="sut", connections=connections)
            assert model.connections == [
                ConnectionModel(connection_id=1, connection_type="RPyCConnection", ip_address="10.10.10.10"),
                ConnectionModel(connection_id=2, connection_type="RPyCConnection", ip_address="10.10.10.10"),
                ConnectionModel(connection_type="SerialConnection", relative_connection_id=1),
            ]

        def test_duplication_of_interfaces(self):
            with pytest.raises(ValueError):
                SUTModel(
                    network_interfaces=[
                        NetworkInterfaceModel(pci_device="8086:1572", interface_indexes=["1", "2"]),
                        NetworkInterfaceModel(pci_device="8086:1572", interface_indexes=["2", "3"]),
                    ]
                )

        def test_ipu_missing_host_type(self):
            with pytest.raises(ValueError, match="IPU host type is required for IPU machine type."):
                SUTModel(role="sut", machine_type="ipu")

        def test_ipu_host_type(self):
            model = SUTModel(role="sut", machine_type="ipu", ipu_host_type="imc")
            assert model.ipu_host_type is IPUHostType.IMC
            assert model.machine_type == "ipu"

        def test_ipu_host_type_incorrect_type(self):
            with pytest.raises(ValidationError, match="ipu_host_type"):
                SUTModel(role="sut", machine_type="ipu", ipu_host_type="unknown_type")

        def test_machine_type(self):
            model = SUTModel(role="sut")
            assert model.machine_type == "regular"
            assert model.ipu_host_type is None

    class TestExtraInfoModel:
        """Extra Info model test class."""

        def test_non_strings(self):
            with pytest.raises(ValueError):
                ExtraInfoModel(suffix=1)
            with pytest.raises(ValueError):
                ExtraInfoModel(datastore=["a", 1])

        def test_model(self):
            model = ExtraInfoModel(suffix="suff", datastore=["datastore1", "datastore2"])
            assert model.suffix == "suff"
            assert model.datastore == ["datastore1", "datastore2"]

    class TestServiceModel:
        """Service model test class."""

        def test_model(self):
            model = ServiceModel(type="nsx", label="MyLabel")
            model2 = ServiceModel(type="nsx")
            assert model.type == "nsx"
            assert model.label == "MyLabel"
            assert model2.label is None
