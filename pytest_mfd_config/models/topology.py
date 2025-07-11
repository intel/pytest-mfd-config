# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Topology Config related models."""

from __future__ import annotations

import logging
import re
from typing import Optional, List, Literal

import mfd_connect
import mfd_powermanagement
import mfd_switchmanagement.connections
import mfd_switchmanagement.vendors
from mfd_typing.data_structures import IPUHostType
from pydantic import SecretStr, field_validator, model_validator

from mfd_common_libs import add_logging_level, log_levels
from mfd_powermanagement.base import PowerManagement
from mfd_typing import MACAddress
from mfd_model.config import (
    ConnectionModelBase,
    PowerMngModelBase,
    SwitchModelBase,
    NetworkInterfaceModelBase,
    SUTModelBase,  # noqa: F401
    VMModel,  # noqa: F401
    ContainerModel,  # noqa: F401
    ServiceModel,  # noqa: F401
    TopologyModelBase,
    IPModel,  # noqa: F401
    OSDControllerModel,  # noqa: F401
    MachineModel as MachineModelBase,
    ExtraInfoModel,
)
from mfd_model.config.models import SchemaMetadata  # noqa: F401

from pytest_mfd_config.utils.exceptions import NotUniqueHostsNamesError

logger = logging.getLogger(__name__)
add_logging_level(level_name="MODULE_DEBUG", level_value=log_levels.MODULE_DEBUG)


class ConnectionModel(ConnectionModelBase):
    """RPC Connection model to be used in pytest-mfd-config plugin."""

    @model_validator(mode="after")
    def ip_or_mac_address_is_required(self) -> ConnectionModel:
        """Check if ip address or mac address (with osd details) is passed for any connection except serial."""
        if (
            self.connection_type not in ["SerialConnection"]
            and self.ip_address is None
            and (self.mac_address is None or self.osd_details is None)
        ):
            raise ValueError(f"IP Address or MAC Address (with osd_details) must be passed for {self.connection_type}")
        return self

    @field_validator("mac_address")
    @classmethod
    def check_is_valid_mac_address(cls: ConnectionModel, v: str) -> str | MACAddress | None:
        """Cast and check if mac_address is valid."""
        if v is not None:
            return MACAddress(v)

        return v

    @field_validator("connection_type")
    @classmethod
    def conn_must_be_on_mfd_list(cls: ConnectionModel, v: str) -> str:
        """Check if connection_type is compliant."""
        if v not in [conn for conn in dir(mfd_connect) if "Connection" in conn]:
            raise ValueError(f"RPC Connection Type must be one of available in mfd-connect Classes. Got '{v}'")
        return v

    @field_validator("connection_options")
    @classmethod
    def change_password_field_to_secretstr(cls: ConnectionModel, v: dict) -> dict:
        """Check if there is a password in connection_options and changes it to SecretStr object for security."""
        v.update({key: SecretStr(value) for key, value in v.items() if "password" in key})

        return v


class PowerMngModel(PowerMngModelBase):
    """Power model."""

    connection: ConnectionModel | None = None

    @field_validator("power_mng_type")
    @classmethod
    def power_mng_type_must_be_from_mfd_powermanagement(cls: PowerMngModel, v: str) -> str:
        """Check if mng_type is compliant."""
        requested_type = getattr(mfd_powermanagement, v, None)
        if requested_type is None or not issubclass(requested_type, PowerManagement):
            raise ValueError(f"type: {v} passed to PowerModel is not proper mfd_powermanagement class.")
        return v

    @model_validator(mode="after")
    def ip_must_be_provided_to_pdu_based(self) -> PowerMngModel:
        """Check if ip is provided when mng_type is pdu based."""
        if self.ip is None and issubclass(
            getattr(mfd_powermanagement, self.power_mng_type), mfd_powermanagement.pdu.PDU
        ):
            raise ValueError(f"IP needs to be provided when creating {self.power_mng_type}")
        return self


class SwitchModel(SwitchModelBase):
    """Switch model."""

    @field_validator("switch_type")
    @classmethod
    def type_must_be_on_mfd_list(cls: SwitchModel, v: str) -> str:
        """Check if switch_type is compliant."""
        available_classes = [switch for switch in dir(mfd_switchmanagement.vendors) if switch[0].isupper()]
        if v not in available_classes:
            raise ValueError(
                f"Switch Type must be one of available mfd-switchmanagement Switch classes:\n"
                f"{available_classes}.\nValue read from config: '{v}'"
            )
        return v

    @field_validator("connection_type")
    @classmethod
    def conn_must_be_on_mfd_list(cls: SwitchModel, v: str) -> str:
        """Check if connection_type is compliant."""
        if v not in [conn for conn in dir(mfd_switchmanagement.connections) if conn[0].isupper()]:
            raise ValueError(
                f"Switch Connection Type must be one of available mfd-switchmanagement "
                f"Connection Type Classes. Got '{v}'"
            )
        return v


class NetworkInterfaceModel(NetworkInterfaceModelBase):
    """Single interface of NIC."""

    @model_validator(mode="after")
    def validate_network_interface_index(self) -> NetworkInterfaceModel:
        """Check if only one interface index field is provided."""
        if all([self.interface_index is not None, self.interface_indexes]):
            raise ValueError("Only one of interface_index, interface_indexes fields can be specified")
        return self

    @model_validator(mode="after")
    def validate_network_interface_identifier(self) -> NetworkInterfaceModel:
        """Check whether any identifier is provided."""
        if not (
            any(
                [
                    self.pci_address,
                    self.pci_device,
                    self.interface_name,
                    self.interface_index is not None,
                    self.interface_indexes is not None,
                    self.speed,
                    self.family,
                    self.random_interface,
                    self.all_interfaces,
                ]
            )
        ):
            raise ValueError(
                "Please provide NetworkInterface identifier, any value of: "
                "pci_address, pci_device with interface_index or interface_name or speed or family or all_interfaces or"
                " random_interface. For seeing the full list of combinations, go to README.md"
            )

        if self.pci_address and any(
            [
                self.pci_device,
                self.interface_name,
                self.interface_index is not None,
                self.interface_indexes is not None,
                self.speed,
                self.family,
                self.random_interface,
                self.all_interfaces,
            ]
        ):
            raise ValueError(
                f"PCI Address: {self.pci_address} uniquely identifies interface, "
                "please delete other identifiers for this single interface."
            )

        if self.interface_name and any(
            [
                self.pci_device,
                self.interface_index is not None,
                self.interface_indexes is not None,
                self.speed,
                self.family,
                self.random_interface,
                self.all_interfaces,
            ]
        ):
            raise ValueError(
                f"Interface name: {self.interface_name} uniquely identifies interface, "
                f"please delete other identifiers for this single interface."
            )

        if self.pci_device and self.speed and self.family:
            raise ValueError(
                f"Speed: {self.speed} and family: {self.family} fields are not supported "
                f"with pci_device: {self.pci_device} "
                "for single interface identifying."
            )

        if (self.speed or self.family) and not (
            any([self.interface_index is not None, self.interface_indexes, self.random_interface, self.all_interfaces])
        ):
            raise ValueError(
                f"Speed: {self.speed} and/or family: {self.family} fields require additional interface identifiers: "
                "interface_index or random_interface=true or all_interfaces=true."
            )

        self.validate_pci_device_fields(
            self.pci_device, self.interface_index, self.interface_indexes, self.random_interface, self.all_interfaces
        )

        return self

    @staticmethod
    def validate_pci_device_fields(
        pci_device: str | None,
        interface_index: int | None,
        interface_indexes: list[int] | None,
        random_interface: bool | None,
        all_interfaces: bool | None,
    ) -> None:
        """Validate PCI Device combinations."""
        if pci_device is not None and (
            (interface_index is None and interface_indexes is None)
            and random_interface is None
            and all_interfaces is None
        ):
            raise ValueError(
                "PCI Device ID must have additional field for exact interface detection: "
                "interface_index/interface_indexes random_interface=true or all_interfaces=true."
            )

    @field_validator("pci_address")
    @classmethod
    def validate_pci_address(cls: NetworkInterfaceModel, v: str) -> str:
        """Validate PCI Address."""
        from mfd_typing.pci_address import pci_address_without_domain_hex_regex, pci_address_full_hex_regex

        if v:
            match_without_domain = re.search(pci_address_without_domain_hex_regex, v)
            match_full = re.search(pci_address_full_hex_regex, v)
            if match_without_domain is None and match_full is None:
                raise ValueError(
                    "PCI Address must be provided in following formats: "
                    "domain:bus:device.function, e.g. '0000:18:00.01'"
                )

        return v

    @field_validator("pci_device")
    @classmethod
    def validate_pci_device_format(cls: NetworkInterfaceModel, v: str) -> str:
        """Validate PCI Device format."""
        from mfd_typing.pci_device import pci_vendor_device_regex, pci_device_full_regex

        if v:
            match_ven_dev = re.search(pci_vendor_device_regex, v)
            match_full = re.search(pci_device_full_regex, v)
            if match_ven_dev is None and match_full is None:
                raise ValueError("PCI Device ID must be provided in following formats: {vid:did} e.g. '8086:1572'")

        return v

    def _compare_interface_indexes(self, other: "NetworkInterfaceModel") -> bool:
        set1: set = set(self.interface_indexes)
        set2: set = set(other.interface_indexes)
        if len(set1.intersection(set2)) != 0:
            return (
                (self.family and self.family == other.family)
                or (self.speed and self.speed == other.speed)
                or (self.pci_device and self.pci_device == other.pci_device)
            )

        return False

    @model_validator(mode="after")
    def validate_switch_name_not_missing_if_switch_port(self) -> NetworkInterfaceModel:
        """Check whether switch_name is provided togather with switch_port."""
        if self.switch_port and not self.switch_name:
            raise ValueError(f"Switch_port: {self.switch_port} provided without switch_name.")

        return self

    def __eq__(self, other: "NetworkInterfaceModel"):
        """Equality means same family, same speed or same pci_device and checked duplication of interface_indexes."""
        if self.interface_index and other.interface_indexes and self.interface_index in other.interface_indexes:
            return True
        if other.interface_index and self.interface_indexes and other.interface_index in self.interface_indexes:
            return True
        if not self.interface_indexes:
            return False
        return self._compare_interface_indexes(other)


class MachineModel(MachineModelBase):
    """Machine model."""

    power_mng: PowerMngModel | None = None


class SUTModel(MachineModel, extra="forbid"):
    """SUT model."""

    role: Literal["sut", "client"]  # noqa: F821
    network_interfaces: list[NetworkInterfaceModelBase] | None = None
    connections: list[ConnectionModel] | None = None
    machine_type: Literal["regular", "ipu"] = "regular"  # noqa: F821
    ipu_host_type: IPUHostType | None = None

    @staticmethod
    def sort_function(v: ConnectionModelBase) -> int:
        """
        Sort connection model.

        Connections with relative model id should be placed in further position than normal connections.

        :param v: Connection model
        :return: Value for sort process
        """
        calculations = 0 if not v.relative_connection_id else v.relative_connection_id * 100
        calculations += v.connection_id
        return calculations

    @model_validator(mode="after")
    def sort_connections(self) -> SUTModel:
        """
        Sort connections using relative_connection_id.

        Connections with relative model id should be placed in further position than normal connections.
        """
        if self.connections:
            self.connections.sort(key=self.sort_function)

        return self

    @model_validator(mode="after")
    def verify_interfaces_duplications(self) -> SUTModel:
        """Check if indexes are not duplicated in the same card."""
        if self.network_interfaces:
            duplication_list = [m for m in self.network_interfaces if self.network_interfaces.count(m) >= 2]
            if duplication_list:
                raise ValueError(f"Found duplicated interface_indexes in network interface models {duplication_list}")

        return self

    @model_validator(mode="after")
    def verify_ipu_host_type_requirement(self) -> SUTModel:
        """Check if ipu_host_type is passed when machine type is ipu."""
        if self.machine_type == "ipu" and self.ipu_host_type is None:
            raise ValueError("IPU host type is required for IPU machine type.")

        return self


class HostModel(SUTModel):
    """Host Model."""

    extra_info: ExtraInfoModel | None = None


class TopologyModel(TopologyModelBase, extra="forbid"):
    """Topology model.

    Part of the infrastructure used for sake of test execution.
    One shall assume test framework has exclusive access to all the assets - meaning they should be reserved
    in Resource Manager prior to test execution
    """

    switches: Optional[List[SwitchModel]] = None
    hosts: Optional[List[HostModel]] = None

    @field_validator("hosts")
    @classmethod
    def check_unique_names_for_hosts(cls: TopologyModel, v: tuple["HostModel", ...]) -> tuple["HostModel", ...]:
        """Check if there are unique names for hosts."""
        names = [h.name for h in v]
        if len(names) != len(set(names)):
            raise NotUniqueHostsNamesError("Hosts 'name' field must be unique in YAML topology, stopping...")

        return v

    @model_validator(mode="after")
    def switch_name_defined_in_switches(self) -> TopologyModel:
        """Check if switch_name from network interfaces is defined in switches section."""
        if not self.hosts:
            return self

        if isinstance(self.hosts[0], dict):
            switch_names = [
                i.get("switch_name")
                for h in self.hosts
                if h.get("network_interfaces")
                for i in h.get("network_interfaces")
                if i.get("switch_name")
            ]
        else:
            switch_names = [
                i.switch_name for h in self.hosts if h.network_interfaces for i in h.network_interfaces if i.switch_name
            ]

        if not switch_names:
            return self

        if switch_names and not self.switches:
            raise ValueError(
                f"There are switch names in network interfaces: {switch_names} which are not detailed described in"
                " switches YAML section."
            )

        for switch_name in switch_names:
            for switch in self.switches:
                if (switch.get("name") if isinstance(switch, dict) else switch.name) == switch_name:
                    break
            else:
                raise ValueError(
                    f"Defined switch name: {switch_name} for network interfaces has missing connection details in"
                    " switches YAML section."
                )

        return self
