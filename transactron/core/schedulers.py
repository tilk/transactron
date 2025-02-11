from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from amaranth import *
from typing import TYPE_CHECKING, Generic, TypeAlias, TypeVar
from transactron.utils import *
from .body import TBody

import networkx

if TYPE_CHECKING:
    from .manager import MethodMap, TransactionGraph, TransactionGraphCC, PriorityOrder

__all__ = ["_priority_order", "fast_eager_deterministic_cc_scheduler", "eager_deterministic_cc_scheduler", "trivial_roundrobin_cc_scheduler"]


_T = TypeVar("_T")


def _priority_order(pgr: Graph[_T], key: Callable[[_T], int]):
    psorted = list(
        networkx.lexicographical_topological_sort(networkx.DiGraph(pgr).reverse(), key=key)
    )
    return {transaction: k for k, transaction in enumerate(psorted)}


@dataclass(eq=False)
class Box(Generic[_T]):
    item: _T


BGroup: TypeAlias = Box[set[_T]]


def trailing_one(data: Value):
    return Cat(b & ~Cat(data[:i]).any() for i, b in enumerate(iter(data)))


def induced_group_graph(gr: Graph[_T], groups: Iterable[set[_T]]) -> Graph[BGroup[_T]]:
    b_groups = list(map(Box, groups))

    cliques_for: defaultdict[_T, set[BGroup[_T]]] = defaultdict(set)
    for clique in b_groups:
        for t in clique.item:
            cliques_for[t].add(clique)

    cpgr: Graph[BGroup[_T]] = Graph()
    for clique in b_groups:
        cpgr[clique] = set()
        for t in clique.item:
            for t2 in gr[t]:
                for clique2 in cliques_for[t2]:
                    if clique != clique2:
                        cpgr[clique].add(clique2)

    return cpgr


def fast_eager_deterministic_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", pgr: "TransactionGraph"
) -> Module:
    m = Module()

    subgr = {t: ts for t, ts in gr.items() if t in cc}
    cliques: list[set[TBody]] = list(map(set, networkx.find_cliques(networkx.Graph(subgr))))
    cpgr = induced_group_graph(pgr, cliques)

    cpgr_sccs: list[set[BGroup[TBody]]] = list(networkx.strongly_connected_components(networkx.DiGraph(cpgr)))
    cspgr = induced_group_graph(cpgr, cpgr_sccs)

    porder = _priority_order(pgr, key=lambda t: len(gr[t]))
    sccporder = _priority_order(cspgr, key=lambda t: 0)  # TODO

    sorted_sccs = list(cspgr.keys())
    sorted_sccs.sort(key=lambda ts: sccporder[ts])

    previous: set[TBody] = set()
    for scc in sorted_sccs:
        ts = set.union(*(set(c.item) for c in scc.item))
        ts = [t for t in ts if t not in previous]
        ts.sort(key=lambda t: porder[t])
        if len(scc.item) != 1:
            print("BAD SCC")
            for transaction in ts:
                conflicts = [tr.run for tr in gr[transaction] & previous]
                noconflict = ~Cat(conflicts).any()
                m.d.comb += transaction.run.eq(transaction.ready & transaction.runnable & noconflict)
                previous.add(transaction)
            continue
        can_runs = Signal(len(ts))
        for i, t in enumerate(ts):
            conflicts = [pt.run for pt in gr[t] & previous]
            noconflict = ~Cat(conflicts).any()
            m.d.comb += can_runs[i].eq(t.ready & t.runnable & noconflict)
        runs = Signal(len(can_runs))
        m.d.comb += runs.eq(trailing_one(can_runs))
        m.d.comb += Cat(t.run for t in ts).eq(runs)
        previous.update(ts)
    return m


def eager_deterministic_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", pgr: "TransactionGraph"
) -> Module:
    """eager_deterministic_cc_scheduler

    This function generates an eager scheduler for the transaction
    subsystem. It isn't fair, because it starts transactions using
    transaction index in `cc` as a priority. Transaction with the lowest
    index has the highest priority.

    If there are two different transactions which have no conflicts then
    they will be started concurrently.

    Parameters
    ----------
    manager : TransactionManager
        TransactionManager which uses this instance of scheduler for
        arbitrating which agent should get a grant signal.
    gr : TransactionGraph
        Graph of conflicts between transactions, where vertices are transactions and edges are conflicts.
    cc : Set[Transaction]
        Connected components of the graph `gr` for which scheduler
        should be generated.
    pgr : TranasctionGraph
        Directed graph of transaction priorities.
    """
    m = Module()
    ccl = list(cc)
    porder = _priority_order(pgr, key=lambda t: len(gr[t]))
    ccl.sort(key=lambda transaction: porder[transaction])
    for k, transaction in enumerate(ccl):
        conflicts = [ccl[j].run for j in range(k) if ccl[j] in gr[transaction]]
        noconflict = ~Cat(conflicts).any()
        m.d.comb += transaction.run.eq(transaction.ready & transaction.runnable & noconflict)
    return m


def trivial_roundrobin_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", pgr: "TransactionGraph"
) -> Module:
    """trivial_roundrobin_cc_scheduler

    This function generates a simple round-robin scheduler for the transaction
    subsystem. In a one cycle there will be at most one transaction granted
    (in a given connected component of the conflict graph), even if there is
    another ready, non-conflicting, transaction. It is mainly for testing
    purposes.

    Parameters
    ----------
    manager : TransactionManager
        TransactionManager which uses this instance of scheduler for
        arbitrating which agent should get grant signal.
    gr : TransactionGraph
        Graph of conflicts between transactions, where vertices are transactions and edges are conflicts.
    cc : Set[Transaction]
        Connected components of the graph `gr` for which scheduler
        should be generated.
    pgr : TransactionGraph
        Directed graph of transaction priorities.
    """
    m = Module()
    sched = Scheduler(len(cc))
    m.submodules.scheduler = sched
    for k, transaction in enumerate(cc):
        m.d.comb += sched.requests[k].eq(transaction.ready & transaction.runnable)
        m.d.comb += transaction.run.eq(sched.grant[k] & sched.valid)
    return m
