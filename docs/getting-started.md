% TODO: Later, when a Transactron guide is written, add links to Transactron concepts (e.g. method, transaction, transaction manager...)

# Getting started

This tutorial serves to gently introduce basics of developing hardware using Transactron.

## Installing Transactron

To install the latest release of Transactron, run:

```
$ pip install --upgrade transactron
```

For the purpose of this tutorial, the [amaranth-boards](https://github.com/amaranth-lang/amaranth-boards) package is suggested to interact with your favorite FPGA dev board.
As `amaranth-boards` is not regularly released to `pypi`, it is recommended to install the latest development snapshot:

```
$ pip install "amaranth-boards@git+https://github.com/amaranth-lang/amaranth-boards.git"
```

## Controlling LEDs and switches

The following example demonstrates the use of Transactron for interacting with basic inputs/outputs on FPGA development boards.
It defines a circuit which allows to control a LED using a switch.
Please bear with the triviality for now: things will get more interesting later.

```{literalinclude} _code/ledcontrol1.py
```

Transactron components are standard Amaranth [elaboratables](inv:#lang-elaboration).
The main difference is that in the `elaborate` method, {py:class}`~transactron.core.tmodule.TModule` should be used instead of `Module`.

To expose an input to Transactron code, the {py:class}`~transactron.lib.basicio.InputSampler` component is added as a submodule.
To use it, a method layout must be specified, which here is an instance of {py:class}`~amaranth.lib.data.StructLayout`.
The `data` attribute then needs to be combinationally connected to the input to be exposed.
The {py:attr}`~transactron.lib.basicio.InputSampler.get` method then allows to access the input from Transactron code using a method call.
The {py:class}`~transactron.lib.basicio.OutputBuffer` component exposes an output instead.
It provides a {py:attr}`~transactron.lib.basicio.OutputBuffer.put` method.

:::{note}
The `synchronize=True` constructor parameter for {py:class}`~transactron.lib.basicio.InputSampler` and {py:class}`~transactron.lib.basicio.OutputBuffer` is used because FPGA dev board I/O is not synchronous to the global clock.
It is not needed for synchronous signals.
:::

Transactron methods can only be called from within transaction (or method) definitions.
Here, we define a simple transaction by constructing a {py:class}`~transactron.core.transaction.Transaction` object and immediately calling {py:meth}`~transactron.core.transaction.Transaction.body`.
Inside the body, the {py:attr}`~transactron.lib.basicio.OutputBuffer.put` method is called to set the LED value to the one received from the switch using the {py:attr}`~transactron.lib.basicio.InputSampler.get` method.
Because of the layout definition `layout`, both the `put` parameter and the field of the structure returned from `get` are named `val`.
The transaction defined here will run in every cycle, ensuring that the LED always shows the value of the switch.

The example component can be synthesized and programmed to your FPGA dev board using the following code.
The code uses the Digilent Arty A7 board.
For it to work, Vivado and `xc3sprog` need to be installed.
To use it with a different dev board, an appropriate platform needs to be imported instead and the correct toolchain for the board needs to be installed.
```python
from transactron import TransactionModule
from amaranth_boards.arty_a7 import ArtyA7_35Platform

ArtyA7_35Platform().build(TransactionModule(LedControl()), do_program=True)
```
Please notice {py:class}`~transactron.core.manager.TransactronModule`, which is used to wrap the `LedControl` elaboratable.
It provides the context required by Transactron code, including the transaction manager.
Without the wrapper, synthesis will fail.
Typically, there should be only one {py:class}`~transactron.core.manager.TransactronModule` for the entire project.
