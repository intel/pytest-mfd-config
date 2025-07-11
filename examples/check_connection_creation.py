# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
from pathlib import Path

from ruamel.yaml import YAML

from pytest_mfd_config.fixtures import create_host_connections_from_model, get_connection_object
from pytest_mfd_config.models.topology import ConnectionModel, HostModel, TopologyModel


topology_dict = YAML(typ="safe", pure=True).load(Path(r"./serial_connection.yaml"))
model = TopologyModel(**topology_dict)

# manually creation of connections from connections models
serial_controller_connection = get_connection_object(model.hosts[0].connections[0])
get_connection_object(model.hosts[0].connections[1], relative_connection=serial_controller_connection)

# creation of connections from host model without specifying object of relative connection
create_host_connections_from_model(model.hosts[0])
