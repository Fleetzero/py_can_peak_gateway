import logging
import time

from socket import socket, AF_INET, SOCK_DGRAM
from typing import final, override, Tuple, Final, List
from ctypes import BigEndianStructure, c_uint16, c_uint64, c_uint32, c_uint8, sizeof
from enum import IntEnum
from can import BusABC, Message


class MessageType(IntEnum):
    CAN_FRAME = 0x80
    CAN_FRAME_CRC = 0x81
    CAN_FD_FRAME = 0x90
    CAN_FD_FRAME_CRC = 0x91


FLAG_REMOTE_REQUEST: Final[int] = 0x01
FLAG_EXTENDED_IDENTIFIER: Final[int] = 0x02
FLAG_EXTENDED_DATA_LENGTH: Final[int] = 0x10
FLAG_BITRATE_SWITCH: Final[int] = 0x30
FLAG_ERROR_STATE: Final[int] = 0x40

MASK_CAN_ID: Final[int] = (1 << 28) - 1
MASK_CAN_ID_REMOTE_REQUEST: Final[int] = 1 << 30
MASK_CAN_ID_EXTENDED_FRAME: Final[int] = 1 << 31

FETCH_SIZE_STANDARD_FRAME: Final[int] = 8
FETCH_SIZE_OPTIONAL_CRC: Final[int] = 4


class MessageHeader(BigEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("packet_size", c_uint16),
        ("frame_kind", c_uint16),
        ("unused_tag", c_uint64),
        ("timestamp_low", c_uint32),
        ("timestamp_high", c_uint32),
        ("channel", c_uint8),
        ("frame_size", c_uint8),
        ("frame_flags", c_uint16),
        ("frame_id_raw", c_uint32),
    ]

    @property
    def flag_remote_request_frame(self) -> bool:
        return bool(self.frame_flags & FLAG_REMOTE_REQUEST)

    @property
    def flag_extended_data_length(self) -> bool:
        return bool(self.frame_flags & FLAG_BITRATE_SWITCH)

    @property
    def flag_activated_bitrate_switch(self) -> bool:
        return bool(self.frame_flags & FLAG_BITRATE_SWITCH)

    @property
    def flag_error_state_indicator(self) -> bool:
        return bool(self.frame_flags & FLAG_ERROR_STATE)

    @property
    def frame_extended_id(self) -> bool:
        return bool(self.frame_id_raw & MASK_CAN_ID_EXTENDED_FRAME)

    @property
    def frame_id(self) -> int:
        return self.frame_id_raw & MASK_CAN_ID

    def __repr__(self) -> str:
        components: List[str] = [
            f"ID={hex(self.frame_id)}",
            f"DLC={self.frame_size}",
        ]

        if self.frame_extended_id:
            components.append("EXTENDED")

        return " ".join(components)


class SocketReader:
    def __init__(self, sock: socket) -> None:
        self._socket: socket = sock
        self._buffer: bytearray = bytearray()

    def read(self, size: int, timeout: float | None) -> bytes:
        if len(self._buffer) < size:
            self._socket.settimeout(timeout)
            data: bytes = self._socket.recv(1024)
            self._buffer.extend(data)

        data = self._buffer[:size]
        self._buffer = self._buffer[size:]

        return data


@final
class BusPeakGateway(BusABC):
    def __init__(
        self,
        send_host: str,
        send_port: int = 40001,
        recv_host: str = "0.0.0.0",
        recv_port: int = 40000,
    ) -> None:
        self._send_socket: socket = socket(AF_INET, SOCK_DGRAM)
        self._send_socket.connect((send_host, send_port))
        self._recv_socket: socket = socket(AF_INET, SOCK_DGRAM)
        self._recv_socket.bind((recv_host, recv_port))
        self._recv_buffer: SocketReader = SocketReader(self._recv_socket)

        super().__init__(channel=f"{send_host}:{send_port}")

    @override
    def send(self, msg: Message, timeout: float | None = None) -> None:
        _ = timeout
        header: MessageHeader = MessageHeader(
            packet_size=sizeof(MessageHeader),
            unused_tag=0,
            timestamp_low=0,
            timestamp_high=0,
            channel=0,
            frame_size=msg.dlc,
            frame_id_raw=msg.arbitration_id,
        )

        if msg.is_fd:
            header.packet_size += msg.dlc
            header.frame_kind = MessageType.CAN_FD_FRAME
        else:
            header.packet_size += FETCH_SIZE_STANDARD_FRAME
            header.frame_kind = MessageType.CAN_FRAME
            if msg.is_remote_frame:
                header.frame_flags |= FLAG_REMOTE_REQUEST
                header.frame_id_raw |= MASK_CAN_ID_REMOTE_REQUEST

        if msg.is_extended_id:
            header.frame_flags |= FLAG_EXTENDED_IDENTIFIER

        if msg.is_error_frame:
            header.frame_flags |= FLAG_ERROR_STATE

        if msg.bitrate_switch:
            header.frame_flags |= FLAG_BITRATE_SWITCH

        frame: bytearray = bytearray(header)
        if msg.is_fd:
            frame.extend(msg.data)
        else:
            data: bytearray = bytearray([0] * FETCH_SIZE_STANDARD_FRAME)
            data[: len(msg.data)] = msg.data
            frame.extend(data)

        self._send_socket.send(frame)

    @override
    def _recv_internal(self, timeout: float | None = None) -> Tuple[Message | None, bool]:
        message: Message = Message()

        try:
            header_data: bytes = self._recv_buffer.read(sizeof(MessageHeader), timeout)
            header: MessageHeader = MessageHeader.from_buffer_copy(header_data)
        except TimeoutError:
            return (None, False)

        fetch_crc: bool = header.frame_kind in {MessageType.CAN_FRAME_CRC | MessageType.CAN_FD_FRAME_CRC}
        fetch_size: int = FETCH_SIZE_STANDARD_FRAME
        frame_size: int = header.frame_size
        match header.frame_kind:
            case MessageType.CAN_FRAME | MessageType.CAN_FRAME_CRC:
                message.is_remote_frame = header.flag_remote_request_frame
            case MessageType.CAN_FD_FRAME | MessageType.CAN_FD_FRAME_CRC:
                message.is_fd = True
                message.is_error_frame = header.flag_error_state_indicator
                message.bitrate_switch = header.flag_activated_bitrate_switch
                fetch_size = header.frame_size
            case frame:
                logging.warning(f"unknown frame type received: {hex(frame)}")
                return (None, False)

        payload_data: bytes = self._recv_buffer.read(fetch_size, timeout)
        if fetch_crc:
            crc_data: bytes = self._recv_buffer.read(FETCH_SIZE_OPTIONAL_CRC, timeout)
            # TODO: check CRC data
            _ = crc_data

        message.timestamp = time.time()
        message.arbitration_id = header.frame_id
        message.is_extended_id = header.frame_extended_id
        message.dlc = frame_size
        message.data = bytearray(payload_data[:frame_size])

        return (message, False)
