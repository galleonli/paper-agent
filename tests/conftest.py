"""Tests must explicitly mock HTTP/IMAP clients instead of using real services."""

import socket

import pytest


@pytest.fixture(autouse=True)
def block_unmocked_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise OSError("Network access is disabled in the test suite")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
