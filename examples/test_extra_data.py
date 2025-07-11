# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import logging

logger = logging.getLogger(__name__)


def test_some_fixtures(extra_data):
    extra_data["tested_adapter"] = {"family": "CVL", "nvm": "10002000", "driver_version": "1.11.2"}
    logger.debug("test_some_fixtures")
