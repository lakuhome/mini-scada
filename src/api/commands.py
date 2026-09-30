from __future__ import annotations

import asyncio
import logging
import struct
from typing import Final


logger = logging.getLogger(__name__)


MODBUS_PROTOCOL_ID: Final = 0
FC_WRITE_SINGLE_REGISTER: Final = 6
MODBUS_EXCEPTION_BIT: Final = 0x80
MAX_MODBUS_ADU_LENGTH: Final = 253


MODBUS_EXCEPTION_CODES: Final[dict[int, str]] = {
    1: "ILLEGAL FUNCTION",
    2: "ILLEGAL DATA ADDRESS",
    3: "ILLEGAL DATA VALUE",
    4: "SLAVE DEVICE FAILURE",
    5: "ACKNOWLEDGE",
    6: "SLAVE DEVICE BUSY",
    8: "MEMORY PARITY ERROR",
    10: "GATEWAY PATH UNAVAILABLE",
    11: "GATEWAY TARGET DEVICE FAILED TO RESPOND",
}


class PLCCommandError(RuntimeError):
    """Raised when a Modbus control command cannot be completed."""


class PLCCommandService:
    """
    Async Modbus TCP client for PLC control commands.

    All commands are serialized with a lock because writes to industrial
    devices should be predictable and sequential.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5020,
        timeout: float = 3.0,
        unit_id: int = 1,
    ) -> None:
        if not 0 <= unit_id <= 255:
            raise ValueError("unit_id must be between 0 and 255")

        self.host = host
        self.port = port
        self.timeout = timeout
        self.unit_id = unit_id

        self._transaction_id = 1
        self._lock = asyncio.Lock()

    async def write_register(
        self,
        register: int,
        value: int,
    ) -> None:
        if not 0 <= register <= 0xFFFF:
            raise ValueError("register must be between 0 and 65535")

        if not 0 <= value <= 0xFFFF:
            raise ValueError("value must be between 0 and 65535")

        async with self._lock:
            transaction_id = self._next_transaction_id()

            reader, writer = await self._open_connection()

            try:
                # Modbus TCP FC06 request:
                #
                # MBAP Header:
                #   Transaction ID : 2 bytes
                #   Protocol ID    : 2 bytes
                #   Length         : 2 bytes
                #   Unit ID        : 1 byte
                #
                # PDU:
                #   Function Code  : 1 byte
                #   Register       : 2 bytes
                #   Value          : 2 bytes
                #
                # Length = Unit ID + Function + Register + Value
                #        = 1 + 1 + 2 + 2 = 6
                request = struct.pack(
                    ">HHHBBHH",
                    transaction_id,
                    MODBUS_PROTOCOL_ID,
                    6,
                    self.unit_id,
                    FC_WRITE_SINGLE_REGISTER,
                    register,
                    value,
                )

                writer.write(request)

                await asyncio.wait_for(
                    writer.drain(),
                    timeout=self.timeout,
                )

                response_register, response_value = await self._read_fc06_response(
                    reader=reader,
                    transaction_id=transaction_id,
                )

                if response_register != register:
                    raise PLCCommandError("PLC returned another register")

                if response_value != value:
                    raise PLCCommandError("PLC returned another value")

                logger.info(
                    "Modbus FC06 success: unit=%s register=%s value=%s",
                    self.unit_id,
                    register,
                    value,
                )

            except (
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
                ConnectionError,
                OSError,
                struct.error,
            ) as exc:
                raise PLCCommandError(
                    "PLC command timed out or connection was lost"
                ) from exc

            finally:
                writer.close()

                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    def _next_transaction_id(self) -> int:
        """
        Must be called while holding self._lock.
        """
        transaction_id = self._transaction_id

        if transaction_id == 0xFFFF:
            self._transaction_id = 1
        else:
            self._transaction_id += 1

        return transaction_id

    async def _open_connection(
        self,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(
                    self.host,
                    self.port,
                ),
                timeout=self.timeout,
            )

        except (OSError, asyncio.TimeoutError) as exc:
            logger.warning(
                "Cannot connect to PLC at %s:%s",
                self.host,
                self.port,
            )

            raise PLCCommandError("Cannot connect to PLC") from exc

    async def _read_fc06_response(
        self,
        reader: asyncio.StreamReader,
        transaction_id: int,
    ) -> tuple[int, int]:
        """
        Read a Modbus TCP response dynamically.

        Normal FC06 response:
            MBAP header: 7 bytes
            PDU: function + register + value = 5 bytes
            Total: 12 bytes

        Exception response:
            MBAP header: 7 bytes
            PDU: function with 0x80 bit + exception code = 2 bytes
            Total: 9 bytes
        """

        header = await asyncio.wait_for(
            reader.readexactly(7),
            timeout=self.timeout,
        )

        (
            response_transaction,
            response_protocol,
            response_length,
            response_unit,
        ) = struct.unpack(
            ">HHHB",
            header,
        )

        if response_transaction != transaction_id:
            raise PLCCommandError("Invalid Modbus transaction ID")

        if response_protocol != MODBUS_PROTOCOL_ID:
            raise PLCCommandError("Invalid Modbus protocol ID")

        if response_unit != self.unit_id:
            raise PLCCommandError("Invalid Modbus unit ID")

        # Length includes Unit ID + PDU.
        # Minimum valid exception response:
        # unit + function + exception_code = 3
        if (
            response_length < 3
            or response_length > MAX_MODBUS_ADU_LENGTH
        ):
            raise PLCCommandError("Invalid Modbus response length")

        pdu_length = response_length - 1

        pdu = await asyncio.wait_for(
            reader.readexactly(pdu_length),
            timeout=self.timeout,
        )

        function = pdu[0]

        if function & MODBUS_EXCEPTION_BIT:
            if len(pdu) < 2:
                raise PLCCommandError("Truncated Modbus exception response")

            exception_code = pdu[1]
            exception_name = MODBUS_EXCEPTION_CODES.get(
                exception_code,
                "UNKNOWN EXCEPTION",
            )

            raise PLCCommandError(
                f"Modbus exception: {exception_name} "
                f"(function=0x{function:02X}, code={exception_code})"
            )

        if function != FC_WRITE_SINGLE_REGISTER:
            raise PLCCommandError("PLC returned an invalid function code")

        # Successful FC06 PDU:
        # function + register + value = 1 + 2 + 2 = 5 bytes
        if len(pdu) != 5:
            raise PLCCommandError("Invalid FC06 response payload size")

        response_register, response_value = struct.unpack(
            ">HH",
            pdu[1:5],
        )

        return response_register, response_value