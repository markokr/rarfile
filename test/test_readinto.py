"""Read archive entries into buffers with different element sizes and shapes."""

import io
from array import array

import pytest

import rarfile
from rarfile.stream import PipeReader
from rarfile.utils import WritableBuffer


def make_buffer(kind: str) -> WritableBuffer:
    """Create writable buffers with byte and non-byte element counts."""
    if kind == "array":
        return array("I", [0, 0, 0])
    if kind == "typed-view":
        return memoryview(array("I", [0, 0, 0]))
    if kind == "multidimensional":
        return memoryview(bytearray(12)).cast("B", shape=(3, 4))
    return bytearray(12)


@pytest.mark.parametrize("kind", ["bytes", "array", "typed-view", "multidimensional"])
@pytest.mark.parametrize("archive, name", [
    ("test/files/rar5-subdirs.rar", "sub/dir2/file2.txt"),
    ("test/files/seektest.rar", "stest2.txt"),
    ("test/files/seektest.rar", "stest1.txt"),
    ("test/files/rar3-vols.part1.rar", "vols/bigfile.txt"),
    ("test/files/rar5-vols.part1.rar", "vols/bigfile.txt"),
])
def test_readinto_buffers(archive: str, name: str, kind: str) -> None:
    """Read stored, compressed and split entries without crossing their ends."""
    buf = make_buffer(kind)
    view = memoryview(buf).cast("B")
    with rarfile.RarFile(archive) as rf:
        expected = rf.read(name)
        with rf.open(name) as stream:
            offset = 0
            while True:
                view[:] = b"\xff" * len(view)
                count = stream.readinto(buf)
                assert count == min(len(view), len(expected) - offset)
                assert bytes(view[:count]) == expected[offset:offset + count]
                assert bytes(view[count:]) == b"\xff" * (len(view) - count)
                offset += count
                assert stream.tell() == offset
                if not count:
                    break


class ShortReadBuffer(io.BytesIO):
    """Make deterministic short reads, as an unbuffered subprocess pipe can."""

    def readinto(self, buf: WritableBuffer, /) -> int:
        return super().readinto(memoryview(buf).cast("B")[:3])


@pytest.mark.parametrize("kind", ["bytes", "array", "typed-view", "multidimensional"])
def test_readinto_short_pipe_reads(kind: str) -> None:
    """Fill the byte capacity even when each underlying read is short."""
    with rarfile.RarFile("test/files/seektest.rar") as rf:
        expected = rf.read("stest1.txt")
        with rf.open("stest1.txt") as stream:
            assert isinstance(stream, PipeReader)
            stream._fd = ShortReadBuffer(expected)
            buf = make_buffer(kind)
            view = memoryview(buf).cast("B")
            assert stream.readinto(buf) == len(view)
            assert bytes(view) == expected[:len(view)]
            assert stream.tell() == len(view)
            assert stream.read() == expected[len(view):]
