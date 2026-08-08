import socket

_original_socket_cls = socket.socket
_current_interface: str | None = None


def list_interfaces() -> list[str]:
    return sorted(name for _, name in socket.if_nameindex() if name != "lo")


def get_current_interface() -> str | None:
    return _current_interface


def bind_to_interface(interface: str | None) -> None:
    global _current_interface
    _current_interface = interface

    if interface is None:
        socket.socket = _original_socket_cls
        return

    class BoundSocket(_original_socket_cls):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.setsockopt(
                    socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode()
                )
            except OSError:
                pass

    socket.socket = BoundSocket
