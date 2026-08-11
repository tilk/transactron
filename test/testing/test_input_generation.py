from typing import Any
from amaranth import Shape
from amaranth_types import ShapeLike
from amaranth.lib import data
from transactron.testing.input_generation import *
from hypothesis import given, settings, strategies as st
import pytest
import enum as py_enum


@pytest.mark.parametrize("size", [5, 20])
def test_shrinkable_lists(size: int):
    sizes: list[int] = []

    @settings(max_examples=200)
    @given(shrinkable_lists(size, st.integers()))
    def f(elems: list[int]):
        sizes.append(len(elems))
        assert len(elems) <= size
        assert all(isinstance(i, int) for i in elems)

    f()

    # mostly generates the full size
    assert sizes.count(size) / len(sizes) >= 0.8


@pytest.mark.parametrize("size_range", [(0, 5), (0, 20), (5, 20)])
def test_sized_lists(size_range: tuple[int, int]):
    sizes: list[int] = []
    strategy = st.integers(min_value=size_range[0], max_value=size_range[1])

    @settings(max_examples=250)
    @given(sized_lists(strategy, st.integers()))
    def f(elems: list[int]):
        sizes.append(len(elems))
        assert len(elems) <= size_range[1]
        assert all(isinstance(i, int) for i in elems)

    f()

    # average of list sizes in the right ballpark
    avg = sum(sizes) / len(sizes)
    assert 0.2 * size_range[0] + 0.8 * size_range[1] >= avg
    assert 0.2 * size_range[1] + 0.8 * size_range[0] <= avg


def validate_const(shape: ShapeLike, v: Any):
    if isinstance(shape, int):
        assert isinstance(v, int)
        assert v >= 0 and v < 2**shape
    elif isinstance(shape, Shape):
        assert isinstance(v, int)
        if shape.signed:
            assert v >= -(2 ** (shape.width - 1)) and v < 2 ** (shape.width - 1)
        else:
            assert v >= -0 and v < 2**shape.width
    elif isinstance(shape, range):
        assert isinstance(v, int)
        assert v >= shape.start and v < 2**shape.stop
    elif isinstance(shape, py_enum.EnumType):
        assert isinstance(v, shape)
        assert v in shape
    elif isinstance(shape, data.ArrayLayout):
        assert isinstance(v, list)
        assert len(v) == shape.length
        for e in v:
            validate_const(shape.elem_shape, e)
    elif isinstance(shape, data.StructLayout):
        assert isinstance(v, dict)
        for key in v:
            assert key in shape.members
        for key, fld in shape:
            assert key in v
            validate_const(fld.shape, v[key])
    elif isinstance(shape, data.UnionLayout):
        assert isinstance(v, dict)
        assert len(v) == 1
        (key,) = tuple(v)
        assert key in shape.members
        validate_const(shape[key].shape, v[key])
    else:
        raise ValueError("Unsupported ShapeLike")


class FooEnum(py_enum.Enum):
    FOO = 0
    BAR = 1
    BAZ = 2


class BarEnum(py_enum.Enum):
    FOO = 2
    BAR = 7
    BAZ = 42


@pytest.mark.parametrize(
    "shape",
    [0, 1, 8, 32]
    + [range(0, 1), range(0, 2), range(0, 8), range(-12, 35), range(-1234, 56)]
    + [FooEnum, BarEnum]
    + [data.StructLayout({}), data.StructLayout({"a": 5, "b": FooEnum})]
    + [data.ArrayLayout(5, 0), data.ArrayLayout(BarEnum, 5)]
    + [data.UnionLayout({"a": 5, "b": FooEnum})],
)
def test_amaranth_consts(shape: ShapeLike):
    @given(amaranth_consts(shape))
    def f(v):
        validate_const(shape, v)

    f()


def test_amaranth_structs():
    pass  # TODO


def test_intersperse():
    pass  # TODO


def test_intersperse_many():
    pass  # TODO


def test_intersperse_range():
    pass  # TODO
