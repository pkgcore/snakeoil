from unittest.mock import patch

from snakeoil.process import CommandNotFound, find_binary

def hide_binary(*binaries: str):
    def mock_find_binary(name):
        if name in binaries:
            raise CommandNotFound(name)
        return find_binary(name)

    return patch('snakeoil.process.find_binary', side_effect=mock_find_binary)
