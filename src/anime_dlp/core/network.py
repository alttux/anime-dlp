import socket
import sys

_original_socket_cls = socket.socket
_current_interface: str | None = None

# Привязка исходящего трафика к конкретному сетевому интерфейсу по имени
# (SO_BINDTODEVICE) — сокет-опция, специфичная для Linux. На Windows и macOS
# аналога с таким же поведением (по имени интерфейса, а не по IP) в
# стандартной библиотеке нет, поэтому там функция недоступна.
SUPPORTED = hasattr(socket, "SO_BINDTODEVICE")


def list_interfaces() -> list[str]:
    if not SUPPORTED:
        return []
    return sorted(name for _, name in socket.if_nameindex() if name != "lo")


def get_current_interface() -> str | None:
    return _current_interface


def bind_to_interface(interface: str | None) -> None:
    if not SUPPORTED:
        if interface is not None:
            raise RuntimeError(
                "Привязка к сетевому интерфейсу поддерживается только в Linux "
                f"(текущая платформа: {sys.platform})."
            )
        return

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
