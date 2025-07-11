# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
def test_secrets(secrets):
    """
    This function is used to test the secrets.
    test_config_with_secrets.yaml is used to test the secrets.

    :param secrets: Fixture with secrets
    """
    # iterate over secrets
    for _, secret in secrets.items():
        print(secret.name)
        print(secret.value)
        print(secret.value.get_secret_value())

    # access by name of secret
    print(secrets["first"].value.get_secret_value())