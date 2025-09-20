import json
import logging

import lz4.block

from src.parser import MANUVariableParser, Variable, VariableParser
from src.utils import Reader, Size

logger = logging.getLogger(__name__)


class SaveFile:
    header_size = 0
    filepath: str | None = None
    data = bytearray()

    def __init__(self, filepath):
        self.filepath = filepath

    def decompress(self):
        with Reader(open(self.filepath, "rb").read()) as file:
            # verify SNFHFZLC are the starting magic bytes
            snfhfzlc = file.read_string(8)
            assert snfhfzlc == "SNFHFZLC"

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

            file.seek(0)
            self.data.extend(file.read(self.header_size))

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
        reader.seek(self.header_size)
        _header_start = reader.tell()
        magic = reader.read_string(4)
        assert magic == "SAV3"
        _type_code_1 = reader.read_int32()
        _type_code_2 = reader.read_int32()
        _type_code_3 = reader.read_int32()

        reader.seek(-6, 2)
        variable_table_offset = reader.read_int32()
        string_table_footer_offset = variable_table_offset - 10
        magic = reader.read_string(2)
        assert magic == "SE"

        reader.seek(string_table_footer_offset, 0)
        nm_section_offset = reader.read_int32()
        rb_section_offset = reader.read_int32()

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
        size = Size(string_table_footer_offset - string_table_offset)
        magic = reader.peek_string(4)
        assert magic == "MANU"
        _, self.variable_names = MANUVariableParser([]).parse(reader, size)

        reader.seek(variable_table_offset, 0)
        entry_count = reader.read_int32()
        variable_table_entries = []

        for _ in range(entry_count):
            v_offset = reader.read_int32()
            v_size = reader.read_int32()
            variable_table_entries.append((v_offset, v_size))

        assert len(variable_table_entries) == entry_count
        variable_table_entries.sort(key=lambda item: item[0])

        variables: list[Variable] = []
        variable_parser = VariableParser(variable_names=self.variable_names)

        for i in range(len(variable_table_entries)):
            cur_pos = reader.tell()
            offset, size = variable_table_entries[i]
            token_size = size
            read_token_size = Size(size)

            if i < len(variable_table_entries) - 2:
                token_size = variable_table_entries[i + 1][0] - offset

            if i > 0 and offset < cur_pos:
                continue

            reader.seek(offset)
            variable = variable_parser.parse(reader, read_token_size)

            if variable:
                v = Variable(variable=variable, size=size, token_size=token_size)
                logger.info(f" {cur_pos} {v}")
                variables.append(v)

        variable_groups = []
        idx = 0
        while idx < len(variables):
            group = []
            variable = variables[idx]
            group.append(variable.variable)
            cur_size = variable.size - variable.token_size
            idx += 1

            while cur_size > 0:
                var = variables[idx]
                cur_size -= var.size
                group.append(var.variable)
                idx += 1

            variable_groups.append(group)

        json.dump(variable_groups, open("data/data.json", "w"), indent=4)
