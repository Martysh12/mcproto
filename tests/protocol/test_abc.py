import inspect
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcproto.protocol.abc import BaseAsyncReader, BaseAsyncWriter, BaseSyncReader, BaseSyncWriter
from tests.helpers import SynchronizedMixin

# region: Helper classes/functions


class SyncWriter(BaseSyncWriter):
    """Testable concrete implementation of BaseSyncWriter ABC."""

    def __init__(self):
        self.data = bytearray()

    def write(self, data: bytearray) -> None:
        self.data.extend(data)


class SyncReader(BaseSyncReader):
    """Testable concrete implementation of BaseSyncReader ABC."""

    def __init__(self, data: bytearray):
        self.data = data

    def read(self, length: int) -> bytearray:
        data = self.data[:length]
        del self.data[:length]
        return data


class AsyncWriter(BaseAsyncWriter):
    """Testable concrete implementation of BaseAsyncWriter ABC."""

    def __init__(self):
        self.data = bytearray()

    async def write(self, data: bytearray) -> None:
        # There's no actual need for this function to be asynchronous,
        # it is purely here for testing this behavior, where this synchronous
        # buffer-like implementation is sufficient, but it could include async
        # calls in real usage
        self.data.extend(data)


class AsyncReader(BaseAsyncReader):
    """Testable concrete implementation of BaseAsyncReader ABC."""

    def __init__(self, data: bytearray):
        self.data = data

    async def read(self, length: int) -> bytearray:
        # There's no actual need for this function to be asynchronous,
        # it is purely here for testing this behavior, where this synchronous
        # buffer-like implementation is sufficient, but it could include async
        # calls in real usage
        data = self.data[:length]
        del self.data[:length]
        return data


class WrappedAsyncReader(SynchronizedMixin):
    """Wrapped synchronous implementation of asynchronous AsyncReader class."""

    _WRAPPED_ATTRIBUTE = "_reader"

    def __init__(self, data: bytearray):
        self._reader = AsyncReader(data)


class WrappedAsyncWriter(SynchronizedMixin):
    """Wrapped synchronous implementation of asynchronous AsyncWriter class."""

    _WRAPPED_ATTRIBUTE = "_writer"

    def __init__(self):
        self._writer = AsyncWriter()


def _to_two_complement(number: int, bytes: int) -> int:
    """Helper function to convert a number into two's complement format."""
    return number + 2 ** (bytes * 8)


def _from_two_complement(number: int, bytes: int) -> int:
    """Helper function to get the real value from int in two's complement format."""
    return number - 2 ** (bytes * 8) + 1


# endregion
# region: Synchronous test classes


class TestBaseSyncWriter:
    """Tests for individual write methods implemented in BaseWriter."""

    @classmethod
    def setup_class(cls):
        cls.writer = SyncWriter()

    def setup_method(self):
        self.writer.data.clear()

    def test_write_byte(self):
        """Writing byte int should store an integer in a single byte."""
        self.writer.write_byte(15)
        assert self.writer.data == bytearray([15])

    def test_write_byte_negative(self):
        """Negative number bytes should be stored in two's complement format."""
        self.writer.write_byte(-20)
        assert self.writer.data == bytearray([_to_two_complement(-20, 1)])

    def test_write_byte_out_of_range(self):
        """Signed bytes should only allow writes from -128 to 127."""
        with pytest.raises(ValueError):
            self.writer.write_byte(-129)
        with pytest.raises(ValueError):
            self.writer.write_byte(128)

    def test_write_ubyte(self):
        """Writing unsigned byte int should store an integer in a single byte."""
        self.writer.write_byte(80)
        assert self.writer.data == bytearray([80])

    def test_write_ubyte_out_of_range(self):
        """Unsigned bytes should only allow writes from 0 to 255."""
        with pytest.raises(ValueError):
            self.writer.write_ubyte(256)
        with pytest.raises(ValueError):
            self.writer.write_ubyte(-1)

    # We skip over many similar single type write functions, these are mostly just wrappers around struct.pack,
    # and testing each function would get very repetetive with little benefit, considering struct library itself can be
    # trusted. Specifically, these left out functions are:
    # - write_bool
    # - write_short, write_ushort
    # - write_int, write_uint
    # - write_long, write_ulong
    # - write_float
    # - write_double
    # - write_varshort
    # - write_varlong

    @pytest.mark.parametrize(
        "number,expected_bytes",
        (
            (0, [0]),
            (1, [1]),
            (2, [2]),
            (15, [15]),
            (127, [127]),
            (128, [128, 1]),
            (129, [129, 1]),
            (255, [255, 1]),
            (1000000, [192, 132, 61]),
            (2147483647, [255, 255, 255, 255, 7]),
        ),
    )
    def test__write_varnum(self, number, expected_bytes):
        """Writing varnums results in correct bytes."""
        self.writer._write_varnum(number)
        assert self.writer.data == bytearray(expected_bytes)

    def test__write_varnum_out_of_range(self):
        """Varnums without max size should only work with positive integers."""
        with pytest.raises(ValueError):
            self.writer._write_varnum(-1)

    def test__write_varnum_max_size(self):
        """Varnums should be limitable to n max bytes and work with values in range."""
        self.writer._write_varnum(2**16 - 1, max_size=2)
        assert self.writer.data == bytearray([255, 255, 3])

    def test__write_varnum_max_size_out_of_range(self):
        """Varnums limited to n max bytes should raise ValueErrors for numbers out of this range."""
        with pytest.raises(ValueError):
            self.writer._write_varnum(2**16, max_size=2)

    @pytest.mark.parametrize(
        "varint_value,expected_varnum_call",
        (
            (0, 0),
            (120, 120),
            (2147483647, 2147483647),
            (-1, _to_two_complement(-1, 4)),
            (-2147483648, _to_two_complement(-2147483648, 4)),
        ),
    )
    def test_write_varint(self, varint_value, expected_varnum_call):
        """Writing varint should call _write_varnum with proper values."""
        mock_f = Mock()
        with patch("mcproto.protocol.abc.BaseSyncWriter._write_varnum", mock_f):
            self.writer.write_varint(varint_value)

        mock_f.assert_called_once_with(expected_varnum_call, max_size=4)

    @pytest.mark.parametrize("value", (-2147483649, 2147483648, 10**20, -(10**20)))
    def test_write_varint_out_of_range(self, value):
        """Writing varint outside of signed 32-bit int range should raise ValueError on it's own."""
        mock_f = Mock()
        with patch("mcproto.protocol.abc.BaseSyncWriter._write_varnum", mock_f):
            with pytest.raises(ValueError):
                self.writer.write_varint(value)
        # Range limitation should come from write_varint, not _write_varnum
        mock_f.assert_not_called()

    @pytest.mark.parametrize(
        "string,expected_bytes",
        (
            ("test", [len("test")] + list(map(ord, "test"))),
            ("a" * 100, [len("a" * 100)] + list(map(ord, "a" * 100))),
            ("", [0]),
        ),
    )
    def test_write_utf(self, string, expected_bytes):
        """Writing UTF string results in correct bytes."""
        self.writer.write_utf(string)
        assert self.writer.data == bytearray(expected_bytes)


class TestBaseSyncReader:
    """Tests for individual write methods implemented in BaseWriter."""

    @classmethod
    def setup_class(cls):
        cls.reader = SyncReader(bytearray())

    def setup_method(self):
        self.reader.data.clear()

    @pytest.mark.parametrize(
        "read_bytes,expected_value",
        (
            ([10], 10),
            ([255], 255),
            ([0], 0),
        ),
    )
    def test_read_ubyte(self, read_bytes, expected_value):
        """Reading byte int should return an integer in a single unsigned byte."""
        self.reader.data = bytearray(read_bytes)
        assert self.reader.read_ubyte() == expected_value

    @pytest.mark.parametrize(
        "read_bytes,expected_value",
        (
            ([_to_two_complement(-20, 1)], -20),
            ([_to_two_complement(-128, 1)], -128),
            ([20], 20),
            ([127], 127),
        ),
    )
    def test_read_byte(self, read_bytes, expected_value):
        """Negative number bytes should be read from two's complement format."""
        self.reader.data = bytearray(read_bytes)
        assert self.reader.read_byte() == expected_value

    # We skip over many similar single type write functions, these are mostly just wrappers around struct.pack,
    # and testing each function would get very repetetive with little benefit, considering struct library itself can be
    # trusted. Specifically, these left out functions are:
    # - read_bool
    # - read_short, read_ushort
    # - read_int, read_uint
    # - read_long, read_ulong
    # - read_float
    # - read_double
    # - read_varshort
    # - read_varlong

    @pytest.mark.parametrize(
        "read_bytes,expected_value",
        (
            ([0], 0),
            ([1], 1),
            ([2], 2),
            ([15], 15),
            ([127], 127),
            ([128, 1], 128),
            ([129, 1], 129),
            ([255, 1], 255),
            ([192, 132, 61], 1000000),
            ([255, 255, 255, 255, 7], 2147483647),
        ),
    )
    def test__read_varnum(self, read_bytes, expected_value):
        """Reading varnums bytes results in correct values."""
        self.reader.data = bytearray(read_bytes)
        assert self.reader._read_varnum() == expected_value

    def test__read_varnum_max_size(self):
        """Varnum reading should be limitable to n max bytes and work with values in range."""
        self.reader.data = bytearray([255, 255, 3])
        assert self.reader._read_varnum(max_size=2) == 2**16 - 1

    def test__read_varnum_max_size_out_of_range(self):
        """Varnum reading limited to n max bytes should raise an IOError for numbers out of this range."""
        self.reader.data = bytearray([128, 128, 4])
        with pytest.raises(IOError):
            self.reader._read_varnum(max_size=2)

    @pytest.mark.parametrize(
        "varnum_return_value,expected_varint_value",
        (
            (0, 0),
            (120, 120),
            (2147483647, 2147483647),
            (_to_two_complement(-1, 4), -1),
            (_to_two_complement(-2147483648, 4), -2147483648),
        ),
    )
    def test_read_varint(self, varnum_return_value, expected_varint_value):
        """Reading varint should convert result from _read_varnum into signed value."""
        # We need to support both sync and async calls here, so patch and mock both
        mock_f = Mock()
        mock_f.return_value = varnum_return_value
        async_mock_f = AsyncMock()
        async_mock_f.return_value = varnum_return_value
        with patch("mcproto.protocol.abc.BaseSyncReader._read_varnum", mock_f):
            with patch("mcproto.protocol.abc.BaseAsyncReader._read_varnum", async_mock_f):
                assert self.reader.read_varint() == expected_varint_value

        try:
            mock_f.assert_called_once_with(max_size=4)
        except AssertionError as exc:
            try:
                async_mock_f.assert_called_once_with(max_size=4)
            except TypeError:
                raise exc

    @pytest.mark.parametrize(
        "read_bytes,expected_string",
        (
            ([len("test")] + list(map(ord, "test")), "test"),
            ([len("a" * 100)] + list(map(ord, "a" * 100)), "a" * 100),
            ([0], ""),
        ),
    )
    def test_read_utf(self, read_bytes, expected_string):
        """Reading UTF string results in correct values."""
        self.reader.data = bytearray(read_bytes)
        assert self.reader.read_utf() == expected_string


# endregion
# region: Asynchronous test classes


class TestBaseAsyncWriter(TestBaseSyncWriter):
    @classmethod
    def setup_class(cls):
        cls.writer = WrappedAsyncWriter()

    @pytest.mark.parametrize(
        "async_function_name",
        (
            "write",
            "write_bool",
            "write_byte",
            "write_ubyte",
            "write_short",
            "write_ushort",
            "write_int",
            "write_uint",
            "write_long",
            "write_ulong",
            "write_float",
            "write_double",
            "_write_varnum",
            "write_varshort",
            "write_varint",
            "write_varlong",
            "write_utf",
            "write_optional",
        ),
    )
    def test_methods_are_async(self, async_function_name):
        """Because of the nature of this test class, we should ensure that all wrapped functions are actually async.

        This is because we're wrapping all of the async functions and converting them into synchronous ones, however
        if they already were synchronous for some reason and shouldn't have been, we wouldn't detect it.
        """
        expected_async_func = getattr(self.writer._writer, async_function_name)
        assert inspect.iscoroutinefunction(expected_async_func)

    # Overwrite some test methods with patches, since they were design to patch
    # synchronous function, and the path to patch is pointing to the synchronous ABC class.

    @pytest.mark.parametrize(
        "varint_value,expected_varnum_call",
        (
            (0, 0),
            (120, 120),
            (2147483647, 2147483647),
            (-1, _to_two_complement(-1, 4)),
            (-2147483648, _to_two_complement(-2147483648, 4)),
        ),
    )
    def test_write_varint(self, varint_value, expected_varnum_call):
        """Writing varint should call _write_varnum with proper values."""
        mock_f = AsyncMock()
        with patch("mcproto.protocol.abc.BaseAsyncWriter._write_varnum", mock_f):
            self.writer.write_varint(varint_value)

        mock_f.assert_called_once_with(expected_varnum_call, max_size=4)

    @pytest.mark.parametrize("value", (-2147483649, 2147483648, 10**20, -(10**20)))
    def test_write_varint_out_of_range(self, value):
        """Writing varint outside of signed 32-bit int range should raise ValueError on it's own."""
        mock_f = AsyncMock()
        with patch("mcproto.protocol.abc.BaseAsyncWriter._write_varnum", mock_f):
            with pytest.raises(ValueError):
                self.writer.write_varint(value)
        # Range limitation should come from write_varint, not _write_varnum
        mock_f.assert_not_called()


class TestBaseAsyncReader(TestBaseSyncReader):
    @classmethod
    def setup_class(cls):
        cls.reader = WrappedAsyncReader(bytearray())

    @pytest.mark.parametrize(
        "async_function_name",
        (
            "read",
            "read_bool",
            "read_byte",
            "read_ubyte",
            "read_short",
            "read_ushort",
            "read_int",
            "read_uint",
            "read_long",
            "read_ulong",
            "read_float",
            "read_double",
            "_read_varnum",
            "read_varshort",
            "read_varint",
            "read_varlong",
            "read_utf",
            "read_optional",
        ),
    )
    def test_methods_are_async(self, async_function_name):
        """Because of the nature of this test class, we should ensure that all wrapped functions are actually async.

        This is because we're wrapping all of the async functions and converting them into synchronous ones, however
        if they already were synchronous for some reason and shouldn't have been, we wouldn't detect it.
        """
        expected_async_func = getattr(self.reader._reader, async_function_name)
        assert inspect.iscoroutinefunction(expected_async_func)

    # Overwrite some test methods with patches, since they were design to patch
    # synchronous function, and the path to patch is pointing to the synchronous ABC class.

    @pytest.mark.parametrize(
        "varnum_return_value,expected_varint_value",
        (
            (0, 0),
            (120, 120),
            (2147483647, 2147483647),
            (_to_two_complement(-1, 4), -1),
            (_to_two_complement(-2147483648, 4), -2147483648),
        ),
    )
    def test_read_varint(self, varnum_return_value, expected_varint_value):
        """Reading varint should convert result from _read_varnum into signed value."""
        # We need to support both sync and async calls here, so patch and mock both
        mock_f = AsyncMock()
        mock_f.return_value = varnum_return_value
        with patch("mcproto.protocol.abc.BaseAsyncReader._read_varnum", mock_f):
            assert self.reader.read_varint() == expected_varint_value

        mock_f.assert_called_once_with(max_size=4)


# endregion