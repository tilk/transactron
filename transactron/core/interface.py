import inspect
from collections.abc import Iterable, Sequence, Mapping
from typing import Any, Self, final, overload
from dataclasses import dataclass
from .method import Method, Methods, MethodDir


__all__ = ["Interface", "InterfaceMember", "InterfaceMembers", "InterfacePart", "interface_members"]


@final
@dataclass
class InterfaceMember:
    mdir: MethodDir
    iface: "InterfacePart"


# TODO: when frozendicts are introduced in Python, use here
@final
class InterfaceMembers(Mapping[str, "InterfaceMember"]):
    def __init__(self, members: Iterable[tuple[str, "InterfaceMember"]]):
        self._dict = dict(members)

    def __len__(self):
        return len(self._dict)

    def __getitem__(self, name: str):
        return self._dict[name]

    def __iter__(self):
        return iter(self._dict)


type InterfacePart = Method | InterfaceMembers | Sequence["InterfacePart"] | Mapping[str, "InterfacePart"]


def interface_members(obj) -> InterfaceMembers:
    hints: dict[str, Any] = {}
    for cls in reversed(obj.__class__.__mro__):
        hints.update(inspect.get_annotations(cls, eval_str=True))

    ret: dict[str, InterfaceMember] = {}

    for name, attr in vars(obj).items():
        if name in hints and hasattr(hints[name], "__metadata__"):
            dirs = [dir for dir in hints[name].__metadata__ if isinstance(dir, MethodDir)]
            if len(dirs) != 1:
                continue
            ret[name] = InterfaceMember(dirs[0], interface_part(attr))
        elif isinstance(attr, (Method, Methods)):
            ret[name] = InterfaceMember(MethodDir.PROVIDED, interface_part(attr))

    return InterfaceMembers(ret.items())


@overload
def interface_part(obj: Method) -> Method: ...


@overload
def interface_part(obj: Sequence) -> Sequence[InterfacePart]: ...


@overload
def interface_part(obj: Mapping) -> Mapping[str, InterfacePart]: ...


def interface_part(obj) -> InterfacePart:
    if isinstance(obj, Method):
        return obj
    elif isinstance(obj, Sequence):
        return tuple(interface_part(elem) for elem in obj)
    elif isinstance(obj, Mapping):
        assert all(isinstance(key, str) for key in obj.keys())
        return {key: interface_part(elem) for (key, elem) in obj.items()}
    else:
        return interface_members(obj)


def part_provide(lhs: InterfacePart, rhs: InterfacePart):
    if isinstance(lhs, Method) and isinstance(rhs, Method):
        lhs.provide(rhs)
    elif isinstance(lhs, InterfaceMembers) and isinstance(rhs, InterfaceMembers):
        assert lhs.keys() == rhs.keys()
        for key in lhs.keys():
            lhs_member = lhs[key]
            rhs_member = rhs[key]
            if lhs_member.mdir != rhs_member.mdir:
                raise ValueError(f'Interface members "{key}" have different directions')
            elif lhs_member.mdir == MethodDir.PROVIDED:
                part_provide(lhs_member.iface, rhs_member.iface)
            else:
                part_provide(rhs_member.iface, lhs_member.iface)
    elif isinstance(lhs, Sequence) and isinstance(rhs, Sequence):
        for lhs_item, rhs_item in zip(lhs, rhs, strict=True):
            part_provide(lhs_item, rhs_item)
    elif (
        isinstance(lhs, Mapping)
        and isinstance(rhs, Mapping)
        and not isinstance(lhs, InterfaceMembers)
        and not isinstance(rhs, InterfaceMembers)
    ):
        assert lhs.keys() == rhs.keys()
        for key in lhs.keys():
            part_provide(lhs[key], rhs[key])


def provide(lhs, rhs):
    part_provide(interface_part(lhs), interface_part(rhs))


class Interface:
    def members(self) -> InterfaceMembers:
        return interface_members(self)

    def provide(self, interface: Self):
        part_provide(self.members(), interface.members())
