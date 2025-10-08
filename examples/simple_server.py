import sys
import local_comm as lc


def callback(data_in: bytes) -> bytes:
    text_in = data_in.decode("utf-8")
    text_out = "chris"

    print(f"[server] recieved request '{text_in}'")
    print(f"[server] sending response '{text_out}'")

    data_out = text_out.encode("utf-8")

    return data_out


def main():

    print("Python version", sys.version)
    ep = lc.EndPoint()
    n = "example"
    ep.create_service(n, callback)
    print(f"[server] ready on service '{n}' (Ctrl+C to stop)")
    ep.spin()


if __name__ == "__main__":
    main()
