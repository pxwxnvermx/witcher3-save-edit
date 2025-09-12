from src.utils import Reader, Size
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
unknown_types = set()

def parse_token(reader: Reader, type: str, size: Size, variable_names: list[str]):
    if type == "Uint8":
        size.size -= 1
        return reader.read_int(1, False)

    if type == "Uint16":
        size.size -= 1
        return reader.read_int(1, False)

    if type == "Uint32":
        size.size -= 4
        return reader.read_int(4, False)

    if type == "Uint64":
        size.size -= 8
        return reader.read_int(8, False)

    if type == "Int8":
        size.size -= 1
        return reader.read_int(1)

    if type == "Int16":
        size.size -= 1
        return reader.read_int(1)

    if type == "Int32":
        size.size -= 4
        return reader.read_int(4)

    if type == "Int64":
        size.size -= 8
        return reader.read_int(8)

    if type == "Bool":
        size.size -= 1
        return bool(reader.read_int(1))

    if type == "Float":
        size.size -= 4
        return float.fromhex(reader.read(4).hex())

    if type == "Double":
        size.size -= 8
        return float.fromhex(reader.read(8).hex())

    if type.startswith("array:2,0,"):
        element_type = type.removeprefix("array:2,0,")
        length = reader.read_int32()
        size.size -= 4
        array = []
        for _ in range(length):
            array.append(parse_token(reader, element_type, size, variable_names))
        return array

    if type == "String":
        header_byte = reader.read_int(1)
        size.size -= 1
        string_encoded = (header_byte & 128) > 0
        if string_encoded:
            string_length = header_byte & 127
            size.size -= string_length
            return reader.read_string(string_length)
        return ""

    if type == "StringAnsi":
        string_length = reader.read_int(1)
        size.size -= string_length
        return reader.read_string(string_length)

    if type == "CName":
        name_idx = reader.read_int16()
        size.size -= 2
        try:
            value = variable_names[name_idx - 1]
        except IndexError:
            value = "Unknown"
        return value

    if type == "CGUID":
        guid_data = reader.read(16)
        size.size -= 16
        return UUID(bytes=guid_data)

    if type == "EngineTime":
        size.size -= 3
        return reader.read(3)

    if type == "GameTime":
        size.size -= 11
        return reader.read(11)

    if type == "IdTag":
        value = [reader.read(1)]
        for _ in range(4):
            value.append(reader.read_int32())
        size.size -= 17
        return tuple(value)

    if type.startswith("handle:"):
        handle_type = type.removeprefix("handle:")
        return parse_token(reader, handle_type, size, variable_names)

    if type.startswith("soft:"):
        handle_type = type.removeprefix("soft:")
        return parse_token(reader, handle_type, size, variable_names)

    logger.info(f"{reader.tell()}, {type}")
    unknown_types.add(type)
    return


class VariableParser:
    def __init__(self, variable_names=[]):
        self.variable_names = variable_names

    def parse(self, reader: Reader, size: Size):
        magic = self.get_magic(reader)

        if magic == "VL":
            reader.read_string(2)
            size.size -= 2
            return self.parse_vl_variable(reader, size)

        if magic == "BS":
            reader.read_string(2)
            size.size -= 2
            return self.parse_bs_variable(reader, size)

        if magic == "OP":
            reader.read_string(2)
            size.size -= 2
            return self.parse_op_variable(reader, size)

        if magic == "SS":
            reader.read_string(2)
            size.size -= 2
            return self.parse_ss_variable(reader, size)

        if magic == "SXAP":
            reader.read_string(4)
            size.size -= 4
            return self.parse_sxap_variable(reader, size)

        if magic == "BLCK":
            reader.read_string(4)
            size.size -= 4
            return self.parse_blck_variable(reader, size)

        if magic == "AVAL":
            reader.read_string(4)
            size.size -= 4
            return self.parse_aval_variable(reader, size)

        if magic == "PORP":
            reader.read_string(4)
            size.size -= 4
            return self.parse_porp_variable(reader, size)

        if magic == "MANU":
            reader.read_string(4)
            size.size -= 4
            return self.parse_manu_variable(reader, size)

        variable = magic, "UNKNOWN", reader.read(size.size)
        size.size = 0
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
        value = parse_token(reader, type, size, self.variable_names)
        return "OP", name, type, value

    def parse_ss_variable(self, reader: Reader, size: Size):
        size_inner = reader.read_int32()
        size.size -= 4
        assert size.size == size_inner

        variables = []
        while size.size > 0:
            variable = self.parse(reader, size)
            variables.append(variable)
        return "SS", variables

    def parse_vl_variable(self, reader: Reader, size: Size):
        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        size.size -= 4

        name = self.variable_names[name_idx - 1]
        type = self.variable_names[type_idx - 1]
        value = parse_token(reader, type, size, self.variable_names)
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
        value = parse_token(reader, type, size, self.variable_names)
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
        value = parse_token(reader, type_name, read_value_size, self.variable_names)
        size.size -= value_size
        assert read_value_size.size == 0
        return "PORP", name, type_name, value


    def parse_manu_variable(self, reader: Reader, size: Size):
        string_count = reader.read_int32()
        reader.read_int32()
        size.size -= 4 * 2

        variable_names = []
        for i in range(string_count):
            s_len = reader.read_int(1)
            try:
                s = reader.read_string(s_len)
            except UnicodeDecodeError:
                reader.seek(-s_len, 1)
                s = reader.read(s_len).decode(errors="ignore")
            variable_names.append(s)
            size.size -= 1 + s_len

        assert len(variable_names) == string_count

        reader.read_int32()
        magic = reader.read_string(4)
        size.size -= 4 + 4
        assert magic == "ENOD"
        return "MANU", variable_names
