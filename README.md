> [!IMPORTANT]
> This project is under development. All source code and features on the main branch are for the purpose of testing or evaluation and not production ready.

# Pytest MFD Config

Pytest Plugin that handles test and topology configs and all their belongings like helper fixtures.


[How to install](#how-to-install)

[Available features](#available-features)
* [CLI options](#cli-options)
* [Pytest fixtures](#pytest-fixtures)
* [Host object](#host-object)
* [Connections dataclass](#connections-dataclass)
* [Extra_data](#extra_data)
* [RQM ID](#rqm-id)
* [Topology configuration](#topology-configuration)
* [Secrets](#secrets)

[Topology Models](#topology-models)
* [Metadata](#metadata)
* [Pydantic models](#pydantic-models)
* [Base MachineModel](#base-machinemodel)
* [IPvAnyAddress](#ipvanyaddress)
* [PowerMngModel](#powermngmodel)
* [OSDControllerModel](#osdcontrollermodel)
* [Secrets](#secrets)
* [SwitchModel](#switchmodel)
* [ServiceModel](#servicemodel)
* [HostModel](#hostmodel)
* [NetworkInterfaceModel](#networkinterfacemodel)
* [VMs](#vms)
* [Containers](#containers)

[Test-config creation](#test-config-creation)

[Test-config-params passthrough to test methods](#test-config-params-passthrough-to-test-methods)

[Overwrite any test input parameter from command line](#Overwrite-any-test-input-parameter-from-command-line)

[OS supported](#os-supported)

[Issue reporting](#issue-reporting)


# Available features
After installing this plugin new CLI options, pytest fixtures and mechanisms will be available in pytest framework.


## CLI options:
After successful installation when you invoke `pytest --help` you should see new options in the output:

![](docs/img/custom_options.png)

## Pytest fixtures:
After successful installation of the plugin when you invoke `pytest --fixtures` you should see new fixtures available in the output:

- `hosts`: (dict[str, Host]) : Get dictionary of Host (mfd-host) objects with associated RPC(mfd-connect) connections based on passed Topology model where key is `name` of host.
- `switches` : (list[Switch]) : Get list of Switch (mfd-switchmanagement) objects based on passed topology model.
- `connected_hosts`: (list[Tuple[Host, Host]]) : Get list of the tuples of connected host pairs 
- `test_config_path` : (str) : Get path of --test_config file.
- `test_config` : (dict) : Get test config data from file.
- `topology_path` : (str) : Get path of --topology_config file.
- `topology_config` : (dict) : Get topology data from file.
- `topology` : (TopologyModel) : Create topology model from config file data.
- `extra_data` : (dict) : Place for extra information to report in test (reported as metadata single test)
![](docs/img/custom_fixtures.png)

### Host object

Fixture `hosts` delivers dictionary with `name` of host as key and `Host` object as value. Using some [getters methods](#methods) you can get single host.
`Host` object is created depending on `instantiate` flag in topology. Some of its attributes allow us to access MFDs objects instantiated at a moment of Host object creation:

- `name` - which is name of host from topology
- `connections` - which is [dataclass](#connections-dataclass) for connections 
- `network_interfaces` - which is list of NetworkInterface objects bases on `network_interfaces` information in topology
- `topology` - which is Pydantic model for Host
- `connection` - which is first object of mfd-connect connection, for better accessing if just single connection established
- `power_mng` - which is `mfd-powermanagement`'s object. Which of `mfd-powermanagement`'s class it should use and all 
   params needed for its `init` you can pass in topology - please check [MachineModel](#machinemodel) for more details.

For more info please check [mfd-host](https://github.com/intel/mfd-host) repository.
#### Host methods:
- `refresh_network_interfaces(self) -> None` - Create new NetworkInterface objects and overwrite current ones.

#### Host-related methods: 
These are the methods user might find useful when instantiating Host objects or its parts (e.g. when `instantiate` flag is set to `False`):

All of them can be find in `pytest_mfd_config.fixtures.py` file.
- `create_host_from_model(host_model: HostModel) -> Host` - Prepare Host object from Host model data.
- `create_host_connections_from_model(host_model: HostModel) -> List[AsyncConnection]` - Prepare list of mfd-connect connections from model data.
- `create_switch_from_model(switch_model: SwitchModel) -> Switch` - Prepare Switch object from model data.
- `create_power_mng_from_model(power_mng_model: PowerMngModel) -> PowerManagement` - Prepare PowerManagement object from model data.
- `get_connection_object(connection_model: "ConnectionModel", connection_list: List["AsyncConnection"] = None, relative_connection: "AsyncConnection" = None,) -> "AsyncConnection"` - Prepare connection object from model data, relative connection is used for `SerialConnection`, connection_list or relative_connection must be passed in case of `SerialConnection`  

#### How to instantiate Host / How to update `hosts` fixture dictionary? 

```python
import pytest

from pytest_mfd_config.fixtures import create_host_from_model

@pytest.fixture()
def updated_hosts(topology, hosts):
    host_model = next(host for host in topology.hosts if host.name == "name")
    host = create_host_from_model(host_model=host_model)
    hosts[host.name] = hosts
    return hosts
```


### Connections dataclass
In Host object `connections` dataclass is available. It's a structure with mfd-connect connections basing on topology details.
It allows us to access connections objects by type of connection:
`host.connections.rpyc`, `host.connections.ssh`, etc. If connection was not defined in topology, value will be `None`.

Full information about "supported" connections variables for each connection type:
 - `local` for LocalConnection
 - `rpyc` for RPyCConnection
 - `serial` for SerialConnection
 - `sol` for SolConnection
 - `ssh` for SSHConnection
 - `tunneled_rpyc` for TunneledRPyCConnection
 - `tunneled_ssh` for TunneledSSHConnection
 - `telnet` for TelnetConnection

Example usages: 
- [`test_connections_and_gathers.py`](./examples/test_connections_and_gathers.py)

### Extra_data
Thanks to defined fixture `extra_data` we are able to pass some extra information to test result:
```python
def test_some_fixtures(extra_data):
    extra_data['tested_adapter'] = {"family": "CVL", "nvm": "80008812", "driver_version": "1.11.2"}
    logger.debug("test_some_fixtures")
    assert True
```
Pytest will log `extra_data` dictionary in the end of test:
```shell

tests/test_example.py::test_some_fixtures 
-------------------------------------------------------------------------------------------------------------------------- live log call -------------------------------------------------------------------------------------------------------------------------- 
2023-02-28 18:21:21     tests.test_example:test_some_fixtures DEBUG         test_some_fixtures
2023-02-28 18:21:21 pytest_mfd_config.fixt:log_extra_data_aft DEBUG         Extra data from test: {'tested_adapter': {'family': 'CVL', 'nvm': '10002000', 'driver_version': '1.11.2'}}
PASSED                                        
```
Example test script with extra_data used: [test_extra_data.py](examples%2Ftest_extra_data.py)


### RQM ID
Using `extra_data` fixture you are able to report RQM ID for each test case. This is useful when you want to link test case with test results.

To report RQM ID you need to use `extra_data` fixture in your test case and provide `rqm_id` key with value of your RQM ID.

e.g.
```python
def test_example(extra_data):
    extra_data["rqm_id"] = "12345"
```

It is important to use `rqm_id` key as it is used by wrapper to report RQM ID. Later, RQM ID will be visible in logs and JSON report, and in a test scheduler in corresponding columns.

### Secrets
Test config can handle secrets. Using `secrets` key in test config file you can pass secrets to test. Secrets will be hidden in logs.
```yaml
secrets:
  - name: vault_password
    value: secret_value1
  - name: faceless
    value: sadas
```

In test, you can access secrets using `secrets` fixture:
```python
def test_secrets(secrets):
    """
    This function is used to test the secrets.
    test_config_with_secrets.yaml is used to test the secrets.

    :param secrets: Fixture with secrets
    """
    # iterate over secrets
    for _, secret in secrets.items():
        print(secret.name)
        print(secret.value.get_secret_value())
        
    # access by name of secret
    print(secrets["first"].value.get_secret_value())
```

Using substitution mechanism, you can use secrets in your test config:
```yaml
secrets:
  - name: vault_password
    value: secret_value1
  - name: faceless
    value: sadas
  - name: your_secret_name
    value: {{secret_name}}
```

`your_secret_name` will be available in `secrets` fixture in test.

Substituted secret values are encrypted (generated encryption key into AMBER_ENCRYPTION_KEY variable and encrypted using cryptography.Fernet) during substitution and decrypted during accessing via secrets.

Fernet guarantees that a message encrypted using it cannot be manipulated or read without the key. Fernet is an implementation of symmetric (also known as “secret key”) authenticated cryptography.

### Topology configuration

HW related configuration can be read from `--topology_config` param. 
For validating input data we use `Pydantic` library which allows us to create Python objects based on passed YAML
or JSON config files.

- See example of `ConnectionModel`:

```python

class ConnectionModel(BaseModel):
    """RPC Connection model."""

    connection_id: int = 0
    ip_address: Optional[IPvAnyAddress]
    mac_address: str | None = None
    connection_type: str
    connection_options: Optional[dict] = None
    relative_connection_id: int | None = None
    osd_details: OSDControllerModel | None = None

    class Config:
        """Pydantic model config overwrite."""

        extra = Extra.forbid
```
`connection_type` is mandatory field. As well as one of the fields `ip_address` or `mac_address`.
When passing MAC instead of IP please remember that you also need to provide OSD details [OSDControllerModel](#OSDControllerModel).
`connection_options` is optional and such model won't accept
any extra keys and will throw `ValidationError` on runtime if passed data won't meet the criteria , e.g.:

```shell
E   pydantic.error_wrappers.ValidationError: 1 validation error for TopologyModel
E   hosts -> 0 -> connections -> 0 -> dunno
E     extra fields not permitted (type=value_error.extra)
```
#### Relative connection
Introduced `connection_id` and `relative_connection_id`. That fields are required for connections which uses connection as connection_option, e.g. SerialConnection.Connection

`connection_id` means just identification number of connection. `relative_connection_id` means plugin will search for equal `connection_id` in ConnectionModel and basing on that model will create connection object and pass to `SerialConnection`.

Depending on test specifics, different Validation Domains may use different Topology configs, e.g. switch-oriented testing will require
providing more details in `switches` section or 2-host setups will use only `hosts` part of Topology and so on.. 

- See another example of valid Topology file for 2 hosts:
```yaml
---
metadata:
  version: '2.5'
hosts:
- name: Marilyn
  instantiate: true                 # Determines whether Host object shall be created or not
  role: sut
  network_interfaces:               # optional
  - speed: 100G                     # determines all interface from the machine host which support provided speed
    interface_index: 0              # determines first interface from the group above (speed support)
  connections:
  - ip_address: 10.10.10.10         # IP address of MGMT connection
    connection_type: RPyCConnection
  power_mng:
    power_mng_type: Ipmi
    host: host
    username: root
    password: pass
    connection:
      ip_address: 10.10.10.11
      connection_type: RPyCConnection
- name: Marilyn-Client
  instantiate: true                 # determines whether Host object shall be created or not
  role: client
  network_interfaces:               # optional
  - interface_name: ens192          # determines which exactly interface should be chosen
  connections:
  - ip_address: 10.10.10.12         # IP address of MGMT connection
    connection_type: RPyCConnection
  power_mng:
    power_mng_type: Raritan
    ip: 1.1.1.1
    community_string: private
```

More JSON/YAML samples could be found in [examples](./examples) dir.

To see full TopologyModel go to [topology.py](./pytest_mfd_config/models/topology.py).

See how supported format of Topology in `schema v2.5` looks like:

# Topology Models

```python
class TopologyModel(BaseModel):
    """Topology model.

    Part of the infrastructure used for sake of test execution.
    One shall assume test framework has exclusive access to all the assets - meaning they should be reserved
    in Resource Manager prior to test execution
    """
    metadata: SchemaMetadata
    switches: Optional[List[SwitchModel]] = None
    services: Optional[List[ServiceModel]] = None
    hosts: Optional[List[HostModel]] = None
    vms: Optional[List[VMModel]] = None
    containers: Optional[List[ContainerModel]] = None

    class Config:
        """Pydantic model config overwrite."""
        extra = Extra.forbid
```
As you may notice at this level of `TopologyModel` all keys (except `metadata`) are optional. 
Config setting - `Extra.forbid` forbids passing any extra keys at this level

Corresponding YAML config file will look like: 
```yaml
---
metadata:
  version: '2.5'
switches: <...>
services: <...>
hosts: <...>
vms: <...>
containers: <...>
```

At different levels of topology, config rules determining what is mandatory, what is optional will be different depending on context.

## Metadata:

Mandatory key to let pydantic-validator know whether object sent is same type as one expected within framework. Validator is checking if `major` parts of given and supported versions match.

- Current version supported: `2.5`

- YAML view:
```yaml
metadata:
  version: '2.5'
```

## Pydantic Models

### InstantiateBaseModel
```python
class InstantiateBaseModel(BaseModel):
    """Instantiate Base Model."""

    instantiate: bool = Field(True, description="Determines whether fixture shall instantiate object or skip it")

    class Config:
        """Pydantic model config overwrite."""

        extra = Extra.forbid
```
Model for models that need instantiate attribute.

### Base MachineModel

- Base model with fields:
```Python
class MachineModel(InstantiateBaseModel):
    """Machine model."""

    name: str = None
    mng_ip_address: Optional[IPvAnyAddress] = None  # BMC MNG Address or Switch IP address
    mng_user: Optional[str] = None
    mng_password: Optional[SecretStr] = None
    power_mng: Optional[PowerMngModel] = None
```
- Models like `Switch`, `Host`, `SUT`, ... - they all inherit from this, so all those fields are available also for them
- Next to simple python types, fields from MachineModel are able to have custom types like: `IPvAnyAddress`, `SecretStr` or `PowerMngModel`.

#### IPvAnyAddress

This is pydantic build-in field type, more you will find on official pydantic page: [link](https://docs.pydantic.dev/usage/types/)

#### PowerMngModel

`power_mng` field visible in example above refers to `mfd-powermanagement`'s classes. All fields, that can be set for `power_mng` are the same fields 
   that `init` methods of mentioned classes are able to parse:
```Python
class PowerMngModel(BaseModel):
    """Power model."""

    power_mng_type: str
    connection: Optional[ConnectionModel] = None
    host: Optional[str] = None
    ip: Optional[str] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    udp_port: Optional[int] = None
    community_string: Optional[str] = None
    outlet_number: Optional[int] = None
```  
#### Secrets
Topology supports hiding secrets from logs. E.g. every model that inherits from MachineModel class has `mng_password` field, which is of type SecretStr.
If printed, this field would be visible as `SecretStr("********")`, to get value use `get_secret_value()`
```python
model.mng_password.get_secret_value()
```

#### OSDControllerModel

Model to be used in `ConnectionModel`, when we want to use MAC instead of IP.
All fields are matching `OsdController` init fields. That's how MAC is translated to IP.
```Python
class OSDControllerModel(BaseModel):
    """OSD Controller model."""

    base_url: str
    username: str | None = None
    password: str | None = None
    secured: bool | None = True
    proxies: Dict[str, str] | None = None
```

### SwitchModel

- List of Network Switch connections
- `switch_type` relates to `mfd-switchmanagement`'s Vendor Classes - [full list](https://github.com/intel/mfd-switchmanagement/blob/master/mfd_switchmanagement/vendors/__init__.py)
- `connection_type` relates to `mfd-switchmanagement`'s Connection Classes - [full list](https://github.com/intel/mfd-switchmanagement/blob/master/mfd_switchmanagement/connections/__init__.py)
- YAML View:
```yaml
switches:                                 # switches details needed for mfd-switchmanagement object creation
- name: Dell 123456
  mng_ip_address: 10.10.10.10
  mng_user: foo
  mng_password: bar
  instantiate: true                       # flag for decision-making whether switch object should be created or only details passed to test
  switch_type: DellOS9_7000
  device_type: Dell
  connection_type: SSHSwitchConnection
  ssh_key_file: keyfile
  use_ssh_key: true
  enable_password: bar2
  auth_timeout: 30
  switch_ports: ['eth1/1', 'eth1/2']
  vlans: ['111', '112', '113']
- (...)
```

### ServiceModel
- List of services like DHCP, NSX test automation may want to use during tests
- YAML View:
```yaml
services:
- type: nsx
  label: my_label
  username: foo
  password: bar
  ip_address: 1.2.3.4
- (...)
```

### HostModel
- Systems Under Tests,
- Management or RPC connections details, 
- NIC interfaces plugged in details
- `network_interfaces`'`connection_type` relates to `mfd-connect`'s Connection Types - [full list](https://github.com/intel/mfd-connect/blob/master/mfd_connect/__init__.py)
- Can reflect connection between Switch' ports and NIC' ports
- Contains extra_info like datastore or suffix for VMs
- Details about type of machine - `regular | ipu`
- IPU host type from mfd-typing as `IPUHostType` entry.
- Example of concrete host is SUTModel visible below:

```Python
class SUTModel(MachineModel):
    """SUT model."""

    role: Literal["sut", "client"]
    network_interfaces: Optional[List[NetworkInterfaceModel]] = None
    connections: Optional[List[ConnectionModel]] = None
    machine_type: Literal["regular", "ipu"] = "regular"
    ipu_host_type: Optional[IPUHostType] = None
```
- YAML View:
```yaml
hosts:                              # each of the element of the topology_configs file is optional, but once provided we validate whether mandatory params are provided
- name: Catherine                   # mandatory
  mng_ip_address: 10.1.2.3          # optional
  mng_user: foo                     # optional
  mng_password: bar                 # optional
  instantiate: false                # mandatory - determines whether Host object should be instantiated when using fixture
  role: sut                         # mandatory
  network_interfaces:               # optional
  - interface_name: eth1
  - pci_address: 0000:ff:ff.1a
  - pci_device: 8086:1572:0000:0001
    interface_index: 1
    ips:
     - value: 1.1.1.3
       mask: 8
  extra_info:
    datastore:
      - "datastore1"
      - "datastore2"
    suffix: "blabla" 
- name: Catherine-Client
  instantiate: false
  role: client
  network_interfaces:               # optional
  - speed: 40G                      # Choose any interface from the machine host which supports 40G speed
    random_interface: true          # Choose any interface from the group above (speed support)
  - family: CPK                     # Choose any interface from the machine host which supports CPK family
    interface_index: 0              # Determines interface index from list of interfaces which meet family condition
- (...)
```

- YAML View:
```yaml
hosts:                              # each of the element of the topology_configs file is optional, but once provided we validate whether mandatory params are provided
- name: Catherine                   # mandatory
  machine_type: ipu
  ipu_host_type: IMC
  instantiate: false                # mandatory - determines whether Host object should be instantiated when using fixture
  role: sut                         # mandatory
  network_interfaces:               # optional
  - interface_name: eth1
  - pci_address: 0000:ff:ff.1a
- name: Catherine-Client
  instantiate: false
  role: client
  network_interfaces:               # optional
  - speed: 40G                      # Choose any interface from the machine host which supports 40G speed
    random_interface: true          # Choose any interface from the group above (speed support)
  - family: CPK                     # Choose any interface from the machine host which supports CPK family
    interface_index: 0              # Determines interface index from list of interfaces which meet family condition
- (...)
```
For `hosts` the `name` is mandatory field and must be unique. Such model won't accept name duplication
and will throw `NotUniqueHostsNamesError` on runtime if passed data won't meet the criteria , e.g.:

```shell
>  raise NotUniqueHostsNamesError("Hosts 'name' field must be unique in YAML topology, stopping...")
E  pytest_mfd_config.utils.exceptions.NotUniqueHostsNamesError: Hosts 'name' field must be unique in YAML topology, stopping...
```

For `machine_type` as `ipu`, `ipu_host_type` field is mandatory field and must be a value from `IPUHostType`.

Default for `machine_type` is `regular`.


### ExtraInfoModel
- This is representation of extra information about Host
- Contains suffix as string - optional
- Contains datastore as list of strings - optional
- Accepts new fields (not defined in the model) so any key=value pair can be passed
```python
class ExtraInfoModel(BaseModel):

    suffix: Optional[str] = None  # suffix to avoid duplication across different systems
    datastore: Optional[List[str]] = None  # list of available datastore names to be used for VMs
```

### NetworkInterfaceModel

- This is representation of Network Interface which gather all possible option how interface or list of interfaces can be indicated in Yaml `topology` file.
- `network_interfaces` reflect to object of `mfd-network-adapter`: `NetworkInterface`.
- In Pydantic model we have defined many possible fields how to determine which interfaces should be chosen.
- Index of interface cannot be duplicated for the same card(same pci_device, family, or speed), e.g. interface_index: 1, interface_indexed: [1, 2, 3]
```Python
class NetworkInterfaceModel(InstantiateBaseModel):
    """Single interface of NIC."""
    pci_address: str | None = Field(
        None,
        description="PCI Address (hexadecimal or integer) provided in format either {domain:bus:device:function} or "
        "{bus:device:function}, e.g. '0000:18:00.0', '18:00.0'",
    )
    interface_name: str | None = Field(None, description="Name of interface, e.g. 'eth3', 'Ethernet 5'")

    pci_device: str = Field(
        None,
        description="PCI Device (hexadecimal) provided in format {vid:did} or {vid:did:subvid:subdid}, "
        "e.g. '8086:1563', '8086:1563:0000:001A'",
    )
    interface_index: str = Field(
        None, description="Interface index - list index value."
    )
    interface_indexes: list[int] | None = Field(None, description="Interface indexes - list of index value.")
    family: str = Field(None, description="Family of network interfaces. Allow list is in DEVICE_IDS (mfd-consts).")
    speed: str = Field(None, description="Speed of network interfaces. Allow list is in SPEED_IDS (mfd-consts).")

    random_interface: str = Field(
        None,
        description="Return random interface for provided identifier: pci_device, interface_index, family or speed.",
    )
    all_interfaces: str = Field(
        None, description="Return all interface for provided identifier: pci_device, interface_index, family or speed."
    )
    ips: list[IPModel] | None = None
    switch_name: str | None = Field(
        None,
        description="Name of the switch which should be same as in switches section for getting all switch connection "
                    "details.",
    )
    switch_port: str | None = Field(
        None,
        description="Name of the switch port to which the interface is connected on the switch (switch_name).",
    )
    vlan: str | None = Field(None, description="VLAN configured on Switch port") 
```
Possible combination of how to identify `NetworkInterface` are shown below:

 Allowed combinations:
* pci_address:
```yaml
(...)
  network_interfaces:                # optional
  - pci_address: 0000:ff:ff.1        # determines interface by unique long PCI Address
(...)
  network_interfaces:                # optional
  - pci_address: ff:ff.1             # determines interface by unique short PCI Address (default `domain` is used: `0000`)
```
* interface_name:
```yaml
  network_interfaces:                # optional
  - interface_name: eth1
```
* pci_device + interface_index/interface_indexes:
```yaml
  network_interfaces:                # optional
  - pci_device: 8086:1572            # short PCIDevice: vid:did
    interface_index: 0               # list index
(...)
  network_interfaces:                # optional
  - pci_device: 8086:1572:0000:0001a # long PCIDevice: vid:did:subvid:subdid
    interface_index: 2               # list index
```
* pci_device + random_interface:
```yaml
  network_interfaces:                # optional
  - pci_device: 8086:1572            # short PCIDevice: vid:did
    random_interface: true           # determines random interface from list of interfaces when pci_device is as above
```
* pci_device + all_interfaces:
```yaml
  network_interfaces:                # optional
  - pci_device: 8086:1572            # short PCIDevice: vid:did
    all_interfaces: true             # determines all interfaces for NIC `1572`
```
* speed + interface_index/interface_indexes:
```yaml
  network_interfaces:                # optional
  - speed: 40G                       # determines all interface IDs supporting 40G speed provided in SPEED_IDS (mfd-const)
    interface_index: 0               # list index
(...)
  network_interfaces:                # optional
  - speed: 100G                      # possible formats: 100G, 100g, 100, 100G, 100g, 100giga, 100Giga, 100GIGA, 100Gb
    interface_index: 3               # list index
```
* speed + all_interfaces:
```yaml
  network_interfaces:                # optional
  - speed: 40G                       # determines all interface IDs supporting 40G speed provided in SPEED_IDS (mfd-const)
    all_interfaces: true             # determines all interfaces supported provided speed from SPEED_IDS (mfd-const)
  network_interfaces:                # optional
  - speed: 100G                      # possible formats: 100G, 100g, 100, 100G, 100g, 100giga, 100Giga, 100GIGA, 100Gb
    interface_index: -1              # list index
```
* speed + random_interface:
```yaml
  network_interfaces:                # optional
  - speed: 40G                       # determines all interface IDs supporting 40G speed provided in SPEED_IDS (mfd-const)
    random_interface: true           # determines random interface
```
* speed + family + random_interface:
```yaml
  network_interfaces:                # optional
  - speed: 40G                       # determines all interface IDs supporting 40G speed provided in SPEED_IDS (mfd-const)
    family: SGVL                     # determines all interfaces from provided family (full list accessible in DEVICE_IDS (mfd-const))
    random_interface: true           # determines random interface
```
* speed + family + all_interfaces:
```yaml
  network_interfaces:                # optional
  - speed: 40G                       # determines all interface IDs supporting 40G speed provided in SPEED_IDS (mfd-const)
    family: CVL                      # determines all interfaces from provided family (full list accessible in DEVICE_IDS (mfd-const))
    all_interfaces: true             # determines all interfaces from `speed` and `family` groups above
```
* family + interface_index/interface_indexes:
```yaml
  network_interfaces:                # optional
  - family: SGVL                     # determines all interfaces from provided family (full list accessible in DEVICE_IDS (mfd-const))
    interface_index: 1               # determines index of interfaces which should be chosen from list determines by `family`
```
* family + random_interface:
```yaml
  network_interfaces:                # optional
  - family: NNT                     # determines all interfaces from provided family (full list accessible in DEVICE_IDS (mfd-const))
    random_interface: true             # determines all interfaces from `speed` and `family` groups above
```
* family + all_interfaces:
```yaml
  network_interfaces:                # optional
  - family: CNV                      # determines all interfaces from provided family (full list accessible in DEVICE_IDS (mfd-const))
    all_interfaces: true             # determines all interfaces from `speed` and `family` groups above
```

All gathered from topology network interfaces are accessible by fixture `hosts`:
```Python
def test_ping(hosts) -> None:
    sut_interfaces = hosts["sut"].network_interfaces
```
To skip initialization of network interface set `instantiate` parameter to `false` in `network_interfaces` configuration in topology config.
```yaml
  network_interfaces:
  - interface_name: eth1
    instantiate: false
```

### VMs:
- Placeholder for keeping data about VMs used in tests. 

- YAML View:
```yaml
<TBD>
```


### Containers:
- Placeholder for keeping data about containers used in tests. (inherits from )

- YAML View:
```yaml
<TBD>
```


# Test-config creation

Test configs are rendered by Jinja2.\
This is why it's possible to just pass filename of one test config to another one to include its content, like so:

```yaml
# test_config.yaml
param1: value1
{% include 'another_test_config.yaml' %}
```

```yaml
# another_test_config.yaml
param2: value2
```

```yaml
# when you pass test_config.yaml to the test it will be rendered as:
param1: value1
param2: value2
```

> [!IMPORTANT]  
> When you want included file to be indented, you need to pass `indent content` keyword

```yaml
# test_config.yaml
param1: value1
params:
  - some: thing
    another: thing
    {% include 'another_test_config.yaml' indent content %}
```

```yaml
# another_test_config.yaml
param2: value2
param3: value3
```

```yaml
# when you pass test_config.yaml to the test it will be rendered as:
param1: value1
params:
  - some: thing
    another: thing
    param2: value2
    param3: value3
```


# Test-config-params passthrough to test methods

Thanks to pytest built-in mechanisms (`metafunc.parametrize` & `pytest_generate_tests`) we are able to extract data from config file and convert it into test method parameter
without any extra declaration, so if you pass test config data by using `--test_config` param: 
```shell
--test_config=configs\examples\test_config_example.yaml
```

`test_config_example.yaml` file content:
```yaml
interval: 1.0
count: 3
direction: both
```

you might use these values as method parameters without any additional assignments, e.g.: 
```python

def test_ping_parametrize(interval, count, direction):
    print(interval)  # 1.0
    print(count)  # 3
    print(direction)  # 'both'
    pass # write some nice stuff here

```

Alternative to passing test configuration parameters to test interior is usage of `pytest.mark.parametrize`. 
This is not the part of this plugin so it is mentioned only. More details about that you will see in official pytest [documentation](https://docs.pytest.org/en/7.2.x/how-to/parametrize.html).

# Overwrite any test input parameter from command line
By using extra commandline flag `--overwrite` you are able to overwrite any test parameter without changing `test_config` data.
This is option for ad-hoc testing.

## Usage
- Pass `--overwrite` flag to commandline and provide needed value changes in acceptable format:

**For single test replacement**
`<test_case_name>:parameter_1=new_value_1,parameter_2=new_value_2`

**For multiple test replacement (separated by semicolon)**
`<test_case_name>:parameter_1=new_value_1,parameter_2=new_value_2;<test_case_name_2>:parameter_1=new_value_1`

Changes provided in this way are local and affect only input parameter values for pointed out tests. Any changes in `test_config` fixture or in other places won't be done.
You will still see there original values read from `--test_config` Yaml file.

- For passing config changes to more tests need to separate them by `"`;", e.g.
## Examples
```python
pytest tests/bat/test_ping.py --test_config tests/bat/bat_config.yaml --topology_config configs/topology.yaml --overwrite "test_ping_connectivity:count=4"

pytest test_bat.py --overwrite "mev_system_tests_rxtx:sem_rules=lem,used_cp=dcpc;mev_system_tests_platform:platform=xeon" (...)
```

## OS supported:

All OSes where pytest is supported.

## Issue reporting

If you encounter any bugs or have suggestions for improvements, you're welcome to contribute directly or open an issue [here](https://github.com/intel/pytest-mfd-config/issues).