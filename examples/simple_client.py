import sys
import local_comm as lc


def main():

    print("Python version", sys.version)

    # Setup
    ep = lc.EndPoint()
    srv = ep.create_service_caller("example")

    # Send data
    text_in = "hello, whats your name?"
    print(f"[client] sending '{text_in}' ...")
    data_in = text_in.encode("utf-8")
    data_out = srv.call(data_in)

    # Report output
    text_out = data_out.decode("utf-8")
    print(f"[client] recieved '{text_out}'")


if __name__ == "__main__":
    main()
