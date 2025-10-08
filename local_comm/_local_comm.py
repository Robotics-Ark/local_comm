# local_comm.py
# Linux-only. Python 3.8+ (uses multiprocessing.shared_memory)
# Standard library only.

import json
import os
import socket
import struct
import time
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Callable, Dict, Optional
import select

# ========== Public exceptions ==========
class LocalCommError(Exception):
    """Base error for local_comm."""

class ServiceUnavailable(LocalCommError):
    """Raised when a service socket cannot be reached within the connect timeout."""

class ServerError(LocalCommError):
    """Raised when the server returns an error payload."""


# --- helper to unregister from resource_tracker (avoid shutdown warnings) ---
try:
    from multiprocessing import resource_tracker as _rt  # private API
    def _rt_unregister(shm_obj: shared_memory.SharedMemory) -> None:
        name = getattr(shm_obj, "_name", None) or shm_obj.name
        try:
            _rt.unregister(name, "shared_memory")
        except Exception:
            pass
except Exception:
    def _rt_unregister(shm_obj):  # no-op fallback
        return


# ---------- framing: length-prefixed JSON (4 bytes, big-endian) ----------
def _send_msg(sock: socket.socket, obj: dict) -> None:
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack("!I", len(data)) + data)

def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)

def _recv_msg(sock: socket.socket) -> Optional[dict]:
    hdr = _recv_exact(sock, 4)
    if not hdr:
        return None
    (n,) = struct.unpack("!I", hdr)
    data = _recv_exact(sock, n)
    if not data:
        return None
    return json.loads(data.decode("utf-8"))

def _sock_path(service_name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in service_name)
    return f"/tmp/local_comm_{safe}.sock"

def _unlink_if_exists(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# ---------- client side ----------
class _ServiceCaller:
    def __init__(self, service_name: str, connect_timeout: float = 2.0):
        self.service_name = service_name
        self.path = _sock_path(service_name)
        self.connect_timeout = connect_timeout

    def call(self, data_in: bytes, timeout: Optional[float] = None) -> bytes:
        """
        Send data_in to the service and get processed bytes back.

        Raises:
            ServiceUnavailable: if the service socket can't be reached within connect_timeout.
            ServerError: if the server replied with an error payload.
            LocalCommError: other client-side errors.
        """
        # 1) CONNECT FIRST (no shm yet) so we avoid leaks/warnings when service is absent.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        deadline = time.time() + self.connect_timeout
        while True:
            try:
                s.connect(self.path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.time() > deadline:
                    s.close()
                    raise ServiceUnavailable(f"service '{self.service_name}' not available")
                time.sleep(0.02)

        if timeout is not None:
            s.settimeout(timeout)

        # 2) Create input shared memory AFTER we are connected.
        in_shm = shared_memory.SharedMemory(create=True, size=len(data_in))
        in_mv = None
        try:
            in_mv = memoryview(in_shm.buf)
            in_mv[:len(data_in)] = data_in
        finally:
            if in_mv is not None:
                try:
                    in_mv.release()
                except Exception:
                    pass
            in_mv = None

        # 3) Do the request/response
        try:
            with s:
                _send_msg(s, {"op": "process", "shm": in_shm.name, "size": len(data_in)})
                resp = _recv_msg(s)
                if not resp or not resp.get("ok", False):
                    err = (resp or {}).get("err", "unknown error")
                    raise ServerError(f"{self.service_name}: {err}")

                out_name = resp["out_shm"]
                out_size = int(resp["out_size"])

                # Attach to server-created output shm and copy bytes
                out_shm = shared_memory.SharedMemory(name=out_name)
                out_mv = None
                try:
                    out_mv = memoryview(out_shm.buf)[:out_size]
                    out_bytes = bytes(out_mv)
                finally:
                    if out_mv is not None:
                        try:
                            out_mv.release()
                        except Exception:
                            pass
                    out_shm.close()
                    # client unlinks server-created output
                    try:
                        out_shm.unlink()
                    except FileNotFoundError:
                        pass

                return out_bytes
        except ServerError:
            # Re-raise cleanly with our type
            raise
        except Exception as e:
            # Other client-side errors
            raise LocalCommError(f"client error: {e}") from e
        finally:
            # client closes + unlinks the input it created
            in_shm.close()
            try:
                in_shm.unlink()
            except FileNotFoundError:
                pass


# ---------- server side ----------
@dataclass
class _Service:
    name: str
    path: str
    sock: socket.socket
    callback: Callable[[bytes], bytes]

class EndPoint:
    def __init__(self):
        self._services: Dict[str, _Service] = {}

    def create_service_caller(self, service_name: str) -> _ServiceCaller:
        return _ServiceCaller(service_name)

    def create_service(self, service_name: str, callback: Callable[[bytes], bytes]) -> None:
        if service_name in self._services:
            raise ValueError(f"service '{service_name}' already exists")
        path = _sock_path(service_name)
        _unlink_if_exists(path)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        srv.bind(path)
        # os.chmod(path, 0o600)  # enable if you want to restrict access
        srv.listen(64)
        self._services[service_name] = _Service(service_name, path, srv, callback)

    def _handle_connection(self, srv: _Service) -> None:
        conn, _ = srv.sock.accept()
        with conn:
            req = _recv_msg(conn)
            if not req or req.get("op") != "process":
                _send_msg(conn, {"ok": False, "err": "bad request"})
                return

            in_name = req.get("shm")
            in_size = int(req.get("size", -1))
            if not in_name or in_size < 0:
                _send_msg(conn, {"ok": False, "err": "bad request"})
                return

            # Attach to client's input shm
            try:
                in_shm = shared_memory.SharedMemory(name=in_name)
            except FileNotFoundError:
                _send_msg(conn, {"ok": False, "err": "input shm not found"})
                return

            in_mv = None
            try:
                in_mv = memoryview(in_shm.buf)[:in_size]
                req_bytes = bytes(in_mv)  # simple callback signature
            finally:
                if in_mv is not None:
                    try:
                        in_mv.release()
                    except Exception:
                        pass
                in_shm.close()
                # server attached; let client unlink. Avoid tracker warning:
                _rt_unregister(in_shm)

            # Run callback
            try:
                out_bytes = srv.callback(req_bytes)
            except Exception as e:
                _send_msg(conn, {"ok": False, "err": f"callback error: {e}"})
                return

            # Create output shm for client to read
            out_shm = shared_memory.SharedMemory(create=True, size=len(out_bytes))
            out_mv = None
            try:
                out_mv = memoryview(out_shm.buf)
                out_mv[:len(out_bytes)] = out_bytes
                try:
                    out_mv.release()
                except Exception:
                    pass
                out_mv = None
                _send_msg(conn, {"ok": True, "out_shm": out_shm.name, "out_size": len(out_bytes)})
            finally:
                out_shm.close()
                # client will unlink output; prevent server tracker from complaining:
                _rt_unregister(out_shm)

    def spin(self) -> None:
        if not self._services:
            raise RuntimeError("no services registered; call create_service(...) first")
        try:
            while True:
                rlist = [s.sock for s in self._services.values()]
                readable, _, _ = select.select(rlist, [], [], 0.5)
                for rs in readable:
                    for svc in self._services.values():
                        if svc.sock is rs:
                            self._handle_connection(svc)
                            break
        except KeyboardInterrupt:
            pass
        finally:
            for svc in self._services.values():
                try:
                    svc.sock.close()
                except Exception:
                    pass
                _unlink_if_exists(svc.path)
            self._services.clear()
