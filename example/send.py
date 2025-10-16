import sys
import logging
import time

from typing import Any
from argparse import ArgumentParser

from can import BusABC, Message, Bus

if __name__ == "__main__":
    parser: ArgumentParser = ArgumentParser(description="Dump the CAN bus from a Ethernet gateway")
    parser.add_argument("--send-host", type=str, default="192.168.10.110")
    parser.add_argument("--send-port", type=int, default=40001)
    parser.add_argument("--recv-host", type=str, default="localhost")
    parser.add_argument("--recv-port", type=int, default=40000)
    args: Any = parser.parse_args()

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    bus: BusABC = Bus(
        interface="peak-gateway",
        send_host=args.send_host,
        send_port=args.send_port,
        recv_host=args.recv_host,
        recv_port=args.recv_port,
    )

    try:
        counter: int = 0
        while True:
            counter = (counter + 1) % 256
            message: Message = Message(arbitration_id=69, data=[0x00, counter, 0x11, counter, 0x22])
            bus.send(message)

            print(".", end="", flush=True)
            time.sleep(0.2)
            break
    except KeyboardInterrupt:
        pass

    bus.shutdown()
