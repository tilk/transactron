from collections.abc import Iterable, Mapping
from typing import Any
from amaranth import *
from amaranth import ShapeCastable
from amaranth_types import ShapeLike
import hypothesis.strategies as st
import enum as py_enum
from amaranth.lib import data
from hypothesis.strategies import DrawFn, SearchStrategy


__all__ = [
    "shrinkable_lists",
    "amaranth_consts",
    "amaranth_structs",
    "intersperse",
    "intersperse_many",
    "intersperse_range",
    "generate_process_input",
]


@st.composite
def shrinkable_lists[T](draw: DrawFn, size: int, elements: SearchStrategy[T]) -> list[T]:
    """Returns a strategy which generates lists of given size, but shrinkable.

    This differs from Hypothesis ``lists`` strategy in that it will generate
    lists of constant size for the main test run, but reduce them in size
    when shrinking. This is useful for generating inputs for long test runs,
    but with the ability to produce short counterexamples.

    Parameters
    ----------
    size : int
        Size of the generated lists.
    elements : SearchStrategy[T]
        The strategy for list elements.

    Returns
    -------
    SearchStrategy[list[T]]
        The constructed strategy.

    Notes
    -----
    Trick based on https://github.com/HypothesisWorks/hypothesis/blob/
    6867da71beae0e4ed004b54b92ef7c74d0722815/hypothesis-python/src/hypothesis/stateful.py#L143
    """
    hp_data = draw(st.data())
    lst = []
    while True:
        force_val = True if len(lst) >= size else None
        b = hp_data.conjecture_data.draw_boolean(p=2**-16, forced=force_val)
        if b:
            break
        lst.append(draw(elements))
    return lst


@st.composite
def sized_lists[T](draw: DrawFn, size: SearchStrategy[int], elements: SearchStrategy[T]) -> list[T]:
    size_val = draw(size)
    return draw(st.lists(elements, min_size=size_val, max_size=size_val))


@st.composite
def amaranth_consts(draw: DrawFn, shape: ShapeLike) -> Any:
    """Returns a strategy which generates valid constants for a given shape.

    Parameters
    ----------
    shape : ShapeLike
        Shape for which constants are generated.

    Returns
    -------
    SearchStrategy
        The constructed strategy.
    """
    if isinstance(shape, int):
        return draw(st.integers(min_value=0, max_value=2**shape - 1))
    elif isinstance(shape, Shape):
        if shape.signed:
            return draw(st.integers(min_value=-(2 ** (shape.width - 1)), max_value=2 ** (shape.width - 1) - 1))
        else:
            return draw(st.integers(min_value=0, max_value=2**shape.width - 1))
    elif isinstance(shape, range):
        return draw(st.integers(min_value=shape.start, max_value=shape.stop - 1))
    elif isinstance(shape, py_enum.EnumType):
        return draw(st.sampled_from(shape))
    elif isinstance(shape, data.ArrayLayout):
        return draw(st.lists(amaranth_consts(shape.elem_shape)))
    elif isinstance(shape, data.StructLayout):
        return draw(st.fixed_dictionaries({key: amaranth_consts(sh.shape) for key, sh in shape}))
    elif isinstance(shape, data.UnionLayout):
        return draw(st.one_of(*(st.fixed_dictionaries({key: amaranth_consts(sh.shape)}) for key, sh in shape)))
    elif isinstance(shape, ShapeCastable):
        raise ValueError("Unsupported ShapeCastable")


@st.composite
def amaranth_structs(
    draw: DrawFn, layout: data.StructLayout, *, override: Mapping[str, SearchStrategy] | None
) -> dict[str, Any]:
    """Returns a strategy which generates valid constants for structs.

    This differs from ``amaranth_consts`` in that the default strategy can
    be overridden for selected fields.

    Parameters
    ----------
    layout : data.StructLayout

    Returns
    -------
    SearchStrategy[dict[str, Any]]
        The constructed strategy.
    """
    if override is None:
        override = {}
    for key in override:
        if key not in layout.members:
            raise ValueError(f"Overridden key {key} not present in layout {layout}")
    strategies = {key: amaranth_consts(sh.shape) for key, sh in layout if key not in override}
    strategies.update(override)
    return draw(st.fixed_dictionaries(strategies))


@st.composite
def intersperse[T, U](draw: DrawFn, seq: SearchStrategy[Iterable[T]], sep: SearchStrategy[Iterable[U]]) -> list[T | U]:
    ret: list[T | U] = []
    for elem in draw(seq):
        ret.extend(draw(sep))
        ret.append(elem)
    ret.extend(draw(sep))
    return ret


@st.composite
def intersperse_many[
    T, U
](draw: DrawFn, seq: SearchStrategy[Iterable[T]], sep: SearchStrategy[U], count: SearchStrategy[int]) -> list[T | U]:
    return draw(intersperse(seq, sized_lists(count, sep)))


def intersperse_range[
    T, U
](
    seq: SearchStrategy[Iterable[T]], sep: SearchStrategy[U], *, min_count: int = 0, max_count: int | None = None
) -> SearchStrategy[list[T | U]]:
    return intersperse(seq, st.lists(sep, min_size=min_count, max_size=max_count))


@st.composite
def generate_process_input(
    draw: DrawFn, count: int, max_nones: int, /, **strategies: SearchStrategy
) -> list[dict[str, Any] | None]:
    return draw(
        intersperse_range(
            shrinkable_lists(count, st.fixed_dictionaries(strategies)), st.just(None), max_count=max_nones
        )
    )
