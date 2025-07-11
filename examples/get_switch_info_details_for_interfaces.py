# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import logging
from typing import TYPE_CHECKING

from mfd_common_libs import log_levels
from mfd_network_adapter.network_interface.data_structures import SwitchInfo
from mfd_switchmanagement.exceptions import SwitchException

if TYPE_CHECKING:
    from mfd_host import Host
    from mfd_switchmanagement.base import Switch

logger = logging.getLogger(__name__)


def update_switch_info(hosts: dict[str, "Host"], switches: list["Switch"]) -> None:  # noqa
    """
    Update SwitchInfo based on provided Topology Switch details in switches fixture.

    :param hosts: Fixture with list of Host objects from pytest-mfd-config plugin
    :param switches: Fixture with list of Switch objects from pytest-mfd-config plugin
    """
    if not switches:
        raise ValueError("There is no info about switches in topology config so we cannot update SwitchInfo.")
    for host in hosts.values():
        for interface in host.network_interfaces:
            if not interface.topology.switch_name:
                continue
            for switch in switches:
                if switch.topology.name == interface.topology.switch_name:
                    if interface.topology.switch_port:
                        interface.switch_info = SwitchInfo(switch=switch, port=interface.topology.switch_port)
                        break
                    try:
                        switch_port = switch.get_port_by_mac(str(interface.mac_address))
                        interface.switch_info = SwitchInfo(switch=switch, port=switch_port)
                        break
                    except SwitchException:
                        continue
            else:
                raise RuntimeError(f"Cannot detect switch port on any of the switches for {interface.name}.")
            logger.log(
                level=log_levels.MODULE_DEBUG,
                msg=f"Found {interface.switch_info} for {interface.name} on {interface.switch_info.switch} switch.",
            )


def test_update_switch_info(hosts, switches):
    update_switch_info(hosts, switches)
