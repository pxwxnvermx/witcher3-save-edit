import sys
import logging

from src.parser import VariableParser, unknown_types
from src.savefile import SaveFile


logging.basicConfig(filename="data/debug.log", level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    save_file = SaveFile(sys.argv[1])
    save_file.decompress()

    with open("data/uncompressed_save.bin", "wb") as f:
        f.write(save_file.data)
    save_file.parse()
    print(unknown_types)
