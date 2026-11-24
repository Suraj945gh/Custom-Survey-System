"""The share panel's 'open on a phone' addresses."""


def test_network_addresses_need_login(client):
    assert client.get("/api/meta/network").status_code == 401


def test_network_addresses_are_local_ipv4(client, researcher_headers):
    addresses = client.get("/api/meta/network", headers=researcher_headers).json()["addresses"]
    assert isinstance(addresses, list)
    for ip in addresses:
        assert ip.count(".") == 3 and not ip.startswith("127.")
