from dataclasses import dataclass
from src.utils import Reader, Size
from uuid import UUID
import logging
import struct

logger = logging.getLogger(__name__)
unknown_types = set()


@dataclass
class Variable:
    variable: any
    size: int
    token_size: int


def parse_token(reader: Reader, type_name: str, size: Size, variable_names: list[str]):
    if type_name == "Uint8":
        size.size -= 1
        return reader.read_int(1, False)

    if type_name == "Uint16":
        size.size -= 2
        return reader.read_int(2, False)

    if type_name == "Uint32":
        size.size -= 4
        return reader.read_int(4, False)

    if type_name == "Uint64":
        size.size -= 8
        return reader.read_int(8, False)

    if type_name == "Int8":
        size.size -= 1
        return reader.read_int(1)

    if type_name == "Int16":
        size.size -= 2
        return reader.read_int(2)

    if type_name == "Int32":
        size.size -= 4
        return reader.read_int(4)

    if type_name == "Int64":
        size.size -= 8
        return reader.read_int(8)

    if type_name == "Bool":
        size.size -= 1
        return bool(reader.read_int(1))

    if type_name == "Float":
        size.size -= 4
        return struct.unpack("<f", reader.read(4))

    if type_name == "Double":
        size.size -= 8
        return struct.unpack("<d", reader.read(8))

    if type_name == "String":
        header_byte = reader.read_int(1)
        size.size -= 1
        string_encoded = (header_byte & 128) > 0
        if string_encoded:
            string_length = header_byte & 127
            size.size -= string_length
            return reader.read_string(string_length)
        return ""

    if type_name == "StringAnsi":
        string_length = reader.read_int(1)
        size.size -= string_length
        return reader.read_string(string_length)

    if type_name == "CName":
        name_idx = reader.read_int16()
        size.size -= 2
        try:
            value = variable_names[name_idx - 1]
        except IndexError:
            value = "Unknown"
        return value

    if type_name == "CGUID":
        guid_data = reader.read(16)
        size.size -= 16
        return UUID(bytes=guid_data)

    if type_name == "EngineTime":
        size.size -= 3
        return reader.read(3)

    if type_name == "GameTime":
        value = reader.read(size.size)
        size.size = 0
        return value

    if type_name == "IdTag":
        value = [reader.read(1)]
        for _ in range(4):
            value.append(reader.read_int32())
        size.size -= 17
        return tuple(value)

    if type_name == "Vector":
        small = size.size % 35 == 0
        unknown_byte = reader.read(1)
        size.size -= 1

        values = []
        for _ in range(4):
            name_idx = reader.read_int16()
            type_idx = reader.read_int16()
            size.size -= 4
            if not small:
                unknown = reader.read_int32()
                size.size -= 4
            name = variable_names[name_idx - 1]
            type_name = variable_names[type_idx - 1]
            value = parse_token(reader, type_name, size, variable_names)
            values.append((name, type_name, value))

        reader.read_int16()
        size.size -= 2
        return values

    if type_name == "Vector3":
        unknown_byte = reader.read(1)
        size.size -= 1
        values = []
        for _ in range(3):
            name_idx = reader.read_int16()
            type_idx = reader.read_int16()
            unknown = reader.read_int32()
            size.size -= 8
            name = variable_names[name_idx - 1]
            type_name = variable_names[type_idx - 1]
            value = parse_token(reader, type_name, size, variable_names)
            values.append((name, type_name, value))

        reader.read_int16()
        size.size -= 2
        return values

    if type_name == "EulerAngles":
        small = size.size % 27 == 0
        unknown = reader.read(1)
        size.size -= 1
        values = []
        for _ in range(3):
            name_idx = reader.read_int16()
            type_idx = reader.read_int16()
            size.size -= 4
            if not small:
                unknown_2 = reader.read_int32()
                size.size -= 4
            name = variable_names[name_idx - 1]
            type_name = variable_names[type_idx - 1]
            value = parse_token(reader, type_name, size, variable_names)
            values.append(value)

        reader.read_int16()
        size.size -= 2
        return values

    if type_name == "EntityHandle":
        unknown1 = reader.read_int(1)
        size.size -= 1
        unknown2 = 0x00
        unknown3 = None
        if unknown1 > 0:
            unknown2 = reader.read(1)
            unknown3 = reader.read(16)
            size.size -= 17
        return unknown1, unknown2, unknown3

    if type_name == "TagList":
        taglist_header = reader.read_int(1)
        size.size -= 1

        taglist_flag = (taglist_header & 128) > 0
        taglist_count = taglist_header & 127

        taglist_entries = []
        for _ in range(taglist_count):
            taglist_entries.append(reader.read_int16())
        size.size -= taglist_count * 2

        return taglist_flag, taglist_entries

    if type_name in {"eGwintFaction", "EJournalStatus", "EZoneName", "EDifficultyMode"}:
        unknown1 = reader.read(1)
        unknown2 = reader.read(1)
        size.size -= 2
        return unknown1, unknown2

    if type_name == "W3EnvironmentManager":
        unknown = reader.read(19)
        size.size -= 19
        return unknown

    if type_name == "array:2,0,SQuestThreadSuspensionData":
        length = reader.read_int32()
        size.size -= 4
        array = []
        if length > 0:
            unknown = reader.read(29)
            size.size -= 29
            for i in range(length):
                array.append(VariableParser(variable_names).parse(reader, size))
                if i < length - 1:
                    reader.read(31)
                    size.size -= 31
                else:
                    reader.read(2)
                    size.size -= 2
        return array

    if type_name == "SActionPointId":
        unknown1 = reader.read(1)
        unknown2 = reader.read_int16()
        size.size -= 3
        unknown3 = 0
        if unknown2 > 0:
            unknown3 = reader.read(40)
            size.size -= 40
        return unknown3

    if type_name in {
        "EAIAttitude",
        "CPlayerInput",
        "EBehaviorGraph",
        "ESignType",
        "EVehicleSlot",
        "SBuffImmunity",
        "SGameplayFact",
        "SGlossaryImageOverride",
        "SRadialSlotDef",
        "SItemUniqueId",
        "SRewardMultiplier",
        "W3AbilityManager",
        "W3EffectManager",
        "W3LevelManager",
        "W3Reputation",
        "W3TutorialManagerUIHandler",
        "WeaponHolster",
    }:
        unknown = reader.read(size.size)
        size.size = 0
        return unknown

    if type_name == "CEntityTemplate":
        header_byte = reader.read_int(1)
        size.size -= 1

        encoded_string = (header_byte & 128) > 0
        if encoded_string:
            string_len = header_byte & 127
            value = reader.read_string(string_len)
            size.size -= string_len
            return value
        else:
            unknown = reader.read(size.size)
            size = 0
            return unknown

    if type_name.startswith("handle:"):
        handle_type = type_name.removeprefix("handle:")
        return parse_token(reader, handle_type, size, variable_names)

    if type_name.startswith("soft:"):
        handle_type = type_name.removeprefix("soft:")
        return parse_token(reader, handle_type, size, variable_names)

    if type_name.startswith("array:2,0,"):
        element_type = type_name.removeprefix("array:2,0,")
        length = reader.read_int32()
        size.size -= 4
        array = []
        for _ in range(length):
            array.append(parse_token(reader, element_type, size, variable_names))
        return array

    unknown_types.add(type_name)
    size.size = 0
    return reader.read(size.size)


class VariableParserBase:
    def __init__(self, variable_names=[]):
        self.variable_names = variable_names

    def parse(self, reader: Reader, size: Size):
        raise NotImplementedError


class VLVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(2)
        size.size -= 2

        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        size.size -= 4

        name = self.variable_names[name_idx - 1]
        type_name = self.variable_names[type_idx - 1]
        value = parse_token(reader, type_name, size, self.variable_names)
        return "VL", name, type_name, value


class BSVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(2)
        size.size -= 2

        name_idx = reader.read_int16()
        size.size -= 2
        name = self.variable_names[name_idx - 1]
        return "BS", name


class OPVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(2)
        size.size -= 2

        name_idx = reader.read_int(2, False)
        type_idx = reader.read_int(2, False)
        size.size -= 4
        try:
            name = self.variable_names[name_idx - 1]
        except IndexError:
            name = "Unknown"
        try:
            type_name = self.variable_names[type_idx - 1]
        except IndexError:
            type_name = "Unknown"
        value = parse_token(reader, type_name, size, self.variable_names)
        return "OP", name, type_name, value


class SSVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(2)
        size.size -= 2

        size_inner = reader.read_int32()
        size.size -= 4
        assert size.size == size_inner

        variables = []
        while size.size > 0:
            variable = VariableParser(self.variable_names).parse(reader, size)
            variables.append(variable)
        return "SS", variables


class SXAPVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        type_code_1 = reader.read_int32()
        type_code_2 = reader.read_int32()
        type_code_3 = reader.read_int32()
        size.size -= 3 * 4
        return "SXAP", type_code_1, type_code_2, type_code_3


class BLCKVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        name_idx = reader.read_int(2, False)
        name = self.variable_names[name_idx - 1]
        blck_size = reader.read_int(2, False)
        unknown3 = reader.read_int(2, False)
        size.size -= 2 * 3

        read_value_size = Size(blck_size)
        variables = []
        while read_value_size.size > 0:
            variable = VariableParser(self.variable_names).parse(
                reader, read_value_size
            )
            variables.append(variable)

        size.size -= blck_size
        return "BLCK", name, blck_size, unknown3, variables


class AVALVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        name_idx = reader.read_int16()
        type_idx = reader.read_int16()
        unknown = reader.read_int32()
        size.size -= 8

        name = self.variable_names[name_idx - 1]
        type_name = self.variable_names[type_idx - 1]
        value = parse_token(reader, type_name, size, self.variable_names)
        return "AVAL", name, type_name, value


class PORPVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

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


class MANUVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        string_count = reader.read_int32()
        reader.read_int32()
        size.size -= 4 * 2

        variable_names = []
        for _ in range(string_count):
            s_len = reader.read_int(1)
            s = reader.read(s_len).decode(errors="ignore")
            variable_names.append(s)
            size.size -= 1 + s_len

        assert len(variable_names) == string_count

        reader.read_int32()
        magic = reader.read_string(4)
        size.size -= 4 + 4
        assert magic == "ENOD"
        return "MANU", variable_names


class SBDFVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        string_count = reader.read_int32()
        size.size -= 4

        variables = []
        for i in range(string_count):
            cur_pos = reader.tell()
            s_len = reader.read_int(1) & 127
            size.size -= s_len
            check = reader.peek(1) == b"\x01"
            if check:
                reader.read(1)
                size.size -= 1
            try:
                s = reader.read_string(s_len)
            except UnicodeDecodeError:
                reader.seek(-s_len, 1)
                s = reader.read(s_len).decode(errors="ignore")

            reader.read_int16()
            count = reader.read_int16()
            value = []
            for _ in range(count):
                unknown = reader.read_int16()
                value.append(reader.read_int(8))
            # logger.info(f"{cur_pos}, {check}, {s}")
            variables.append((s, value))

        assert len(variables) == string_count
        magic = reader.read_string(4)
        size.size -= 4 + 4
        assert magic == "EBDF"
        return "SBDF", variables


class ROTSVariableParser(VariableParserBase):
    def parse(self, reader: Reader, size: Size):
        reader.read_string(4)
        size.size -= 4

        unknown = reader.read_int32()
        size.size -= 4
        return "ROTS", unknown


class VariableParser(VariableParserBase):
    def __init__(self, variable_names=[]):
        self.parsers = {
            "VL": VLVariableParser(variable_names),
            "BS": BSVariableParser(variable_names),
            "OP": OPVariableParser(variable_names),
            "SS": SSVariableParser(variable_names),
            "SXAP": SXAPVariableParser(variable_names),
            "BLCK": BLCKVariableParser(variable_names),
            "AVAL": AVALVariableParser(variable_names),
            "MANU": MANUVariableParser(variable_names),
            "PORP": PORPVariableParser(variable_names),
            # "SBDF": SBDFVariableParser(variable_names),
            "ROTS": ROTSVariableParser(variable_names),
        }
        super().__init__(variable_names)

    def parse(self, reader: Reader, size: Size):
        magic = self.get_magic(reader)
        parser = self.parsers.get(magic)
        if parser is not None:
            return parser.parse(reader, size)

        variable = magic, "UNKNOWN", reader.read(size.size)
        size.size = 0
        return variable

    def get_magic(self, reader: Reader) -> str:
        has_magic = False
        magic = ""
        try:
            magic = reader.peek_string(2)
            if magic in self.parsers.keys():
                has_magic = True
        except UnicodeDecodeError:
            has_magic = False

        if not has_magic:
            try:
                magic = reader.peek_string(4)
                if magic in self.parsers.keys():
                    has_magic = True
            except UnicodeDecodeError:
                has_magic = False
        return magic
