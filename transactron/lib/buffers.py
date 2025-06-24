from amaranth import *
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Component, In, Out

from transactron.utils._typing import MethodStruct
from transactron.utils.transactron_helpers import from_method_layout
from ..core import *
from ..utils import SrcLoc, get_src_loc, MethodLayout

__all__ = ["InputBuffer", "OutputBuffer"]


class BufferBase(Component):
    trigger: Signal
    data: MethodStruct

    def __init__(self, layout: StructLayout, direction: bool, edge: bool, polarity: bool, synchronize: bool):
        if direction:
            super().__init__({"trigger": In(1), "data": Out(layout)})
        else:
            super().__init__({"trigger": In(1), "data": In(layout)})
        self._edge = edge
        self._polarity = polarity
        self._synchronize = synchronize

    def _trigger(self, m: TModule) -> Value:
        if self._synchronize:
            trigger = Signal()
            m.d.sync += trigger.eq(self.trigger)
        else:
            trigger = self.trigger

        if not self._polarity:
            trigger = ~trigger

        if self._edge:
            old_trigger = Signal()
            new_trigger = trigger
            m.d.sync += old_trigger.eq(new_trigger)
            trigger = Signal()
            m.d.comb = trigger.eq(new_trigger & ~old_trigger)

        return trigger


class InputBuffer(BufferBase):
    """Clicked input.

    Useful for interactive simulations or FPGA button/switch interfaces.
    On a rising edge (tested synchronously) of `btn`, the `get` method
    is enabled, which returns the data present on `dat` at the time.
    Inputs are synchronized.

    Attributes
    ----------
    get: Method
        The method for retrieving data from the input. Accepts an empty
        argument, returns a structure.
    btn: Signal, in
        The button input.
    dat: MethodStruct, in
        The data input.
    """

    def __init__(self, layout: MethodLayout, *, edge: bool = True, polarity: bool = True, synchronize: bool = False, src_loc: int | SrcLoc = 0):
        """
        Parameters
        ----------
        layout: method layout
            The data format for the input.
        edge: bool, optional
            Trigger type. If true, edge triggering, otherwise level triggering.
            Edge triggering is the default.
        polarity: bool, optional
            Trigger polarity. If true, positive trigger (rising edge or high
            level), otherwise negative trigger (falling edge or low level).
            Positive trigger is the default.
        src_loc: int | SrcLoc, optional
            How many stack frames deep the source location is taken from.
            Alternatively, the source location to use instead of the default.
        """
        src_loc = get_src_loc(src_loc)
        super().__init__(from_method_layout(layout), False, edge, polarity, synchronize)
        self.get = Method(o=layout, src_loc=src_loc)

    def elaborate(self, platform):
        m = TModule()

        if self._synchronize:
            data = Signal.like(self.data)
            m.d.sync += data.eq(self.data)
        else:
            data = self.data

        @def_method(m, self.get, ready=self._trigger(m))
        def _():
            return data

        return m


class OutputBuffer(BufferBase):
    """Clicked output.

    Useful for interactive simulations or FPGA button/LED interfaces.
    On a rising edge (tested synchronously) of `btn`, the `put` method
    is enabled, which, when called, changes the value of the `dat` signal.

    Attributes
    ----------
    put: Method
        The method for retrieving data from the input. Accepts a structure,
        returns empty result.
    btn: Signal, in
        The button input.
    dat: MethodStruct, out
        The data output.
    """

    def __init__(self, layout: MethodLayout, *, edge: bool = True, polarity: bool = True, synchronize: bool = False, src_loc: int | SrcLoc = 0):
        """
        Parameters
        ----------
        layout: method layout
            The data format for the output.
        src_loc: int | SrcLoc
            How many stack frames deep the source location is taken from.
            Alternatively, the source location to use instead of the default.
        """
        src_loc = get_src_loc(src_loc)
        super().__init__(from_method_layout(layout), False, edge, polarity, synchronize)
        self.put = Method(i=layout, src_loc=src_loc)

    def elaborate(self, platform):
        m = TModule()

        @def_method(m, self.put, ready=self._trigger(m))
        def _(arg):
            m.d.sync += self.data.eq(arg)

        return m
