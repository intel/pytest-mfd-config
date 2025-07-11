# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
"""Utils exceptions."""


class ObjectCantBeFoundError(Exception):
    """Raised if object you are looking for couldn't be found."""


class NotUniqueHostsNamesError(Exception):
    """Raised if names of hosts defined in topology are not unique what is mandatory."""
