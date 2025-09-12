from dataclasses import dataclass
import sys
import lz4.block
from io import BytesIO

save_intermediate = True

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

@dataclass
class Size:
    size: int = 0


def parse_token(reader: Reader, type: str, size: Size):
    if type == "Uint32":
        size.size -= 4
        return reader.read_int(4, False)
    if type == "Uint64":
        size.size -= 8
        return reader.read_int(8, False)
    if type == "Int32":
        size.size -= 4
        return reader.read_int(4)
    if type == "Bool":
        size.size -= 1
        return bool(reader.read_int(1))
    if type == "Float":
        size.size -= 4
        return float.fromhex(reader.read(4).hex())
    return


class VariableParser:
    def __init__(self, variable_names=[]):
        self.variable_names = variable_names

    def parse(self, reader: Reader, size: Size):
        magic = self.get_magic(reader)
        if not magic:
            return None

        variable = None
        if magic == "VL":
            reader.read_string(2)
            size.size -= 2
            variable = self.parse_vl_variable(reader, size)

        if magic == "BS":
            reader.read_string(2)
            size.size -= 2
            variable = self.parse_bs_variable(reader, size)

        if magic == "OP":
            reader.read_string(2)
            size.size -= 2
            variable = self.parse_op_variable(reader, size)

        if magic == "SS":
            reader.read_string(2)
            size.size -= 2
            variable = self.parse_ss_variable(reader, size)

        if magic == "SXAP":
            reader.read_string(4)
            size.size -= 4
            variable = self.parse_sxap_variable(reader, size)

        if magic == "BLCK":
            reader.read_string(4)
            size.size -= 4
            variable = self.parse_blck_variable(reader, size)

        if magic == "AVAL":
            reader.read_string(4)
            size.size -= 4
            variable = self.parse_aval_variable(reader, size)

        if magic == "PORP":
            reader.read_string(4)
            size.size -= 4
            variable = self.parse_porp_variable(reader, size)

        variable = magic, "UNKNOWN", reader.read(size.size)

        return variable

    def get_magic(self, reader: Reader) -> str:
        has_magic = False
        magic = ""
        try:
            magic = reader.peek_string(2)
            if magic in {"BS", "OP", "SS", "VL"}:
                has_magic = True
        except UnicodeDecodeError:
            has_magic = False

        if not has_magic:
            try:
                magic = reader.peek_string(4)
                if magic in {"AVAL", "BLCK", "MANU", "PORP", "SXAP"}:
                    has_magic = True
            except UnicodeDecodeError:
                has_magic = False
        return magic

    def parse_op_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int(2, False)
        type_idx = reader.read_int(2, False)
        size.size -= 4
        try:
            name = self.variable_names[name_idx - 1]
        except IndexError:
            name = "Unknown"
        try:
            type = self.variable_names[type_idx - 1]
        except IndexError:
            type = "Unknown"
        value = parse_token(reader, type, size)
        return "OP", name, type, value

    def parse_ss_variable(self, reader: Reader, size: Size):
        size_inner = reader.read_int32()
        size.size -= 4
        assert size.size == size_inner

        variables = []
        last_size = size.size
        while size.size > 0:
            magic = self.get_magic(reader)
            variable = self.parse(reader, size)
            if size.size == last_size:
                print(magic, variable)
                break
            variables.append(variable)
        return "SS", variables

    def parse_vl_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        size.size -= 4

        name = self.variable_names[name_idx - 1]
        type = self.variable_names[type_idx - 1]
        value = parse_token(reader, type, size)
        return "VL", name, type, value

    def parse_bs_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int16()
        size.size -= 2
        name = self.variable_names[name_idx - 1]
        return "BS", name

    def parse_sxap_variable(self, reader: Reader, size: Size):
        type_code_1 = reader.read_int32()
        type_code_2 = reader.read_int32()
        type_code_3 = reader.read_int32()
        size.size -= 3 * 4
        return "SXAP", type_code_1, type_code_2, type_code_3

    def parse_blck_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int(2, False)
        name = self.variable_names[name_idx - 1]
        blck_size = reader.read_int(2, False)
        unknown3 = reader.read_int(2, False)
        size.size -= 2 * 3

        variables = []
        while size.size > 0:
            variable = self.parse(reader, size)
            variables.append(variable)

        return "BLCK", variables

    def parse_aval_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        unknown = reader.read()
        size.size -= 6

        name = self.variable_names[name_idx - 1]
        type = self.variable_names[type_idx - 1]
        value = parse_token(reader, type, size)
        return "AVAL", name, type, value

    def parse_porp_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        size.size -= 4
        value_size = reader.read_int32()
        size.size -= 4

        name = self.variable_names[name_idx - 1]
        type_name = self.variable_names[type_idx - 1]
        read_value_size = Size(value_size)
        value = parse_token(reader, type_name, read_value_size)
        print(name, type_name, value_size, value, read_value_size.size)
        size.size -= value_size
        assert read_value_size.size == 0
        return "PORP", name, type_name, value


class SaveFile:
    header_size = 0
    filepath: str = None

    data = bytearray()

    def __init__(self, filepath):
        self.filepath = filepath

    def decompress(self):
        with Reader(open(self.filepath, "rb").read()) as file:
            # verify SNFHFZLC are the starting magic bytes
            snfh = file.read_string(4)
            fzlc = file.read_string(4)
            assert snfh == "SNFH"
            assert fzlc == "FZLC"

            # chunk_count, header_size
            chunk_count = file.read_int32()
            self.header_size = file.read_int32()

            chunk_metadata = []

            # get chunk metadata, need to do this here before seeking
            # forward by header_size
            for _ in range(chunk_count):
                compressed_size = file.read_int32()
                uncompressed_size = file.read_int32()
                eof_offset = file.read_int32()
                chunk_metadata.append((compressed_size, uncompressed_size, eof_offset))

            file.seek(self.header_size, 0)

            # uncompress chunks
            for compressed_size, uncompressed_size, eof_offset in chunk_metadata:
                raw_data = file.read(compressed_size)
                assert eof_offset == 0 or file.tell() == eof_offset
                if 0 < compressed_size < uncompressed_size:
                    chunk_data = lz4.block.decompress(
                        raw_data, uncompressed_size=uncompressed_size
                    )
                    assert len(chunk_data) == uncompressed_size
                    self.data.extend(chunk_data)

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
        size = string_table_footer_offset - string_table_offset
        magic = reader.read_string(4)
        assert magic == "MANU"
        size -= 4

        string_count = reader.read_int32()
        reader.read_int32()
        size -= 4 * 2

        self.variable_names = []
        for i in range(string_count):
            s_len = reader.read_int(1)
            try:
                s = reader.read_string(s_len)
            except UnicodeDecodeError:
                reader.seek(-s_len, 1)
                s = reader.read(s_len).decode(errors="ignore")
            self.variable_names.append(s)
            size -= 1 + s_len

        assert len(self.variable_names) == string_count

        reader.read_int32()
        magic = reader.read_string(4)
        size -= 4 + 4
        assert magic == "ENOD"

        if save_intermediate:
            with open("data/strings", "w") as f:
                for s in self.variable_names:
                    f.write(f"{s}\n")

        reader.seek(variable_table_offset, 0)
        entry_count = reader.read_int32()
        variable_table_entries = []

        for _ in range(entry_count):
            v_offset = reader.read_int32()
            v_size = reader.read_int32()
            variable_table_entries.append((v_offset - self.header_size, v_size))

        assert len(variable_table_entries) == entry_count
        variable_table_entries.sort(key=lambda item: item[0])

        variables = []
        variable_parser = VariableParser(variable_names=self.variable_names)

        for i in range(len(variable_table_entries)):
            token_size = Size(variable_table_entries[i][1])

            if (i < len(variable_table_entries) - 2):
                token_size = Size(variable_table_entries[i+1][0] - variable_table_entries[i][0])

            reader.seek(variable_table_entries[i][0])

            variable = variable_parser.parse(reader, token_size)

            if variable:
                variables.append(variable)

        if save_intermediate:
            with open("data/parsed_variables", "w") as f:
                for i, variable in enumerate(variables):
                    f.write(f"{i} {variable}\n")


if __name__ == "__main__":
    save_file = SaveFile(sys.argv[1])
    save_file.decompress()

    if save_intermediate:
        with open("data/uncompressed_save.bin", "wb") as f:
            f.write(save_file.data)

    save_file.parse()
