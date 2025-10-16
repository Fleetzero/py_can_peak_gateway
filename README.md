# Peak Gateway

This repository implements the bus interface of `python-can` for the [PCAN-Ethernet Gateway](https://www.peak-system.com/PCAN-Ethernet-Gateway-DR.330.0.html?&L=1).
It is already implemented in the `pcan` driver, but it requires the [PCAN-Basic API](https://www.peak-system.com/PCAN-Basic.239.0.html?L=1).
The Linux version of the PCAN-Basic API does not support PCAN-Ethernet Gateway.

## Usage

```python
from can import BusABC, Bus

# Use the "peak-gateway" to use the PCAN-Ethernet Gateway.
BusPeakGateway.register()
bus: BusABC = Bus(
    interface="peak-gateway",
    send_host="192.168.10.110",
    send_port=40001,
    recv_host="192.168.10.35",
    recv_port=40000,
)

# You can use the normal bus API on the device.
bus.send(...)
bus.recv()
```

## Development

This Python project is managed by [`uv`](https://docs.astral.sh/uv/).

To install the dependencies in a virtual environment, you need to run this command.

```shell
$ uv sync --dev
```

### Example

The repository includes an example that simulates all 16 PMUs on the bus.

```shell
$ uv run python example/dump.py \
    --send-host="192.168.10.110" \
    --send-port=40001 \
    --recv-host="192.168.10.35" \
    --recv-port=40000
```

### Tools

The tool [`ruff`](https://docs.astral.sh/ruff/) is used for formatting/linting.

```shell
$ uv run ruff format .
$ uv run ruff check .
```