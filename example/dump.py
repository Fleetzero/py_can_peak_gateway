import sys
import logging

from typing import Any
from argparse import ArgumentParser

from can import BusABC, Bus

if __name__ == "__main__":
    parser: ArgumentParser = ArgumentParser(description="Dump the CAN bus from a Ethernet gateway")
    parser.add_argument("--send-host", type=str, default="192.168.10.110")
    parser.add_argument("--send-port", type=int, default=40001)
    parser.add_argument("--recv-host", type=str, default="192.168.10.35")
    parser.add_argument("--recv-port", type=int, default=40000)
    args: Any = parser.parse_args()

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    bus: BusABC = Bus(
        interface="peak-gatewasy",
        send_host=args.send_host,
        send_port=args.send_port,
        recv_host=args.recv_host,
        recv_port=args.recv_port,
    )

    try:
        while True:
            print(bus.recv())
    except KeyboardInterrupt:
        pass

    bus.shutdown()
