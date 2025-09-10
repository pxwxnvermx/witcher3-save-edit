from dataclasses import dataclass
import sys
import lz4.block
from io import BytesIO


class Reader(BytesIO):
    def __init__(self, initial_bytes=b"") -> None:
        super().__init__(initial_bytes)

    def read_string(self, size) -> str:
        return self.read(size).decode()

    def read_int16(self) -> int:
        return self.read_int(2)

    def read_int32(self) -> int:
        return self.read_int(4)

    def read_int(self, size) -> int:
        return int.from_bytes(self.read(size), "little", signed=True)


@dataclass
class CompressedChunkData:
    compressed_size: int = 0
    uncompressed_size: int = 0
    eof_offset: int = 0


class SaveFile:
    chunk_count = 0
    header_size = 0
    file: Reader = None

    data = bytearray()

    def __init__(self, filepath):
        self.file = Reader(open(filepath, "rb").read())

    def decompress(self):
        snfh, fzlc = self.file.read(4), self.file.read(4)
        assert snfh.decode() == "SNFH"
        assert fzlc.decode() == "FZLC"

        self.chunk_count = self.file.read_int32()
        self.header_size = self.file.read_int32()

        chunk_metadata = []

        for _ in range(self.chunk_count):
            compressed_size = self.file.read_int32()
            uncompressed_size = self.file.read_int32()
            eof_offset = self.file.read_int32()
            chunk_metadata.append(
                CompressedChunkData(compressed_size, uncompressed_size, eof_offset)
            )

        self.file.seek(self.header_size, 0)

        for chunk in chunk_metadata:
            compressed_size = chunk.compressed_size
            uncompressed_size = chunk.uncompressed_size
            raw_data = self.file.read(compressed_size)
            assert chunk.eof_offset == 0 or self.file.tell() == chunk.eof_offset
            if 0 < compressed_size < uncompressed_size:
                chunk_data = lz4.block.decompress(
                    raw_data, uncompressed_size=uncompressed_size
                )
                assert len(chunk_data) == chunk.uncompressed_size
                self.data.extend(chunk_data)

        self.file.close()

    def parse(self):
        reader = Reader(self.data)
        header_start = reader.tell()
        magic = reader.read_string(4)
        assert magic == "SAV3"
        type_code_1 = reader.read_int32()
        type_code_2 = reader.read_int32()
        type_code_3 = reader.read_int32()

        reader.seek(-6, 2)
        variable_table_offset = reader.read_int32() - self.header_size
        string_table_footer_offset = variable_table_offset - 10
        magic = reader.read_string(2)
        assert magic == "SE"

        reader.seek(string_table_footer_offset, 0)
        nm_section_offset = reader.read_int32() - self.header_size
        rb_section_offset = reader.read_int32() - self.header_size

        reader.seek(nm_section_offset, 0)
        magic = reader.read_string(2)
        assert magic == "NM"
        string_table_offset = reader.tell()

        reader.seek(rb_section_offset, 0)
        magic = reader.read_string(2)
        assert magic == "RB"
        count = reader.read_int32()
        rb_entries = []
        for _ in range(count):
            size = reader.read_int16()
            offset = reader.read_int32()
            rb_entries.append((size, offset))
        assert len(rb_entries) == count

        reader.seek(string_table_offset, 0)


if __name__ == "__main__":
    save_file = SaveFile(sys.argv[1])
    save_file.decompress()
    with open("uncompressed_save", "wb") as f:
        f.write(save_file.data)

    save_file.parse()
