from dataclasses import dataclass
from io import BytesIO


@dataclass
class Size:
    size: int = 0


class Reader(BytesIO):
    def __init__(self, initial_bytes=b"") -> None:
        super().__init__(initial_bytes)

    def read_string(self, size) -> str:
        return self.read(size).decode()

    def read_int16(self) -> int:
        return self.read_int(2)

    def read_int32(self) -> int:
        return self.read_int(4)

    def read_int(self, size, signed=True) -> int:
        return int.from_bytes(self.read(size), "little", signed=signed)

    def peek_string(self, size) -> str:
        s = self.read(size).decode()
        self.seek(-size, 1)
        return s

    def peek(self, size) -> str:
        s = self.read(size)
        self.seek(-size, 1)
        return s
