"""Small helpers for the staff screens."""

from __future__ import annotations

import socket

from fastapi import APIRouter, Depends

from .deps import current_user

router = APIRouter(prefix="/api/meta", tags=["meta"], dependencies=[Depends(current_user)])


def lan_addresses() -> list[str]:
    """This computer's addresses on the local network, so the share panel can show a link that
    opens on a phone connected to the same Wi-Fi (localhost only works on this computer)."""
    found: list[str] = []
    try:  # the address used to reach the network (no packet is actually sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    unique = []
    for ip in found:
        if not ip.startswith(("127.", "169.254.", "0.")) and ip not in unique:
            unique.append(ip)
    return unique


@router.get("/network")
def network():
    return {"addresses": lan_addresses()}
