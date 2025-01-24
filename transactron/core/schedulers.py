from collections import defaultdict
from amaranth import *
from typing import TYPE_CHECKING
from transactron.utils import *
from .body import TBody
import networkx

if TYPE_CHECKING:
    from .manager import MethodMap, TransactionGraph, TransactionGraphCC, PriorityOrder

__all__ = ["fast_eager_deterministic_cc_scheduler", "eager_deterministic_cc_scheduler", "trivial_roundrobin_cc_scheduler"]


def fast_eager_deterministic_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", porder: "PriorityOrder"
) -> Module:
    m = Module()

    subgr = {t: ts for t, ts in gr.items() if t in cc}
    cliques: list[list[TBody]] = list(networkx.find_cliques(networkx.Graph(subgr)))

    for ts in cliques:
        ts.sort(key=lambda t: porder[t])
    cliques.sort(key=lambda ts: porder[ts[0]])

    previous: set[TBody] = set()
    t_runs: defaultdict[TBody, list[Value]] = defaultdict(list)
    for ts in cliques:
        can_runs = Signal(len(ts))
        for i, t in enumerate(ts):
            conflicts = [pt.run for pt in previous if pt in gr[t] and porder[pt] < porder[t]]
            noconflict = ~Cat(conflicts).any()
            m.d.comb += can_runs[i].eq(t.ready & t.runnable & noconflict)
        runs = Signal(len(can_runs))
        m.d.comb += runs.eq(can_runs & -can_runs)
        for i, t in enumerate(ts):
            t_runs[t].append(runs[i])
    for t, runs in t_runs.items():
        m.d.comb += t.run.eq(Cat(runs).any())
    return m


def eager_deterministic_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", porder: "PriorityOrder"
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
    porder : PriorityOrder
        Linear ordering of transactions which is consistent with priority constraints.
    """
    m = Module()
    ccl = list(cc)
    ccl.sort(key=lambda transaction: porder[transaction])
    for k, transaction in enumerate(ccl):
        conflicts = [ccl[j].run for j in range(k) if ccl[j] in gr[transaction]]
        noconflict = ~Cat(conflicts).any()
        m.d.comb += transaction.run.eq(transaction.ready & transaction.runnable & noconflict)
    return m


def trivial_roundrobin_cc_scheduler(
    method_map: "MethodMap", gr: "TransactionGraph", cc: "TransactionGraphCC", porder: "PriorityOrder"
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
    porder : PriorityOrder
        Linear ordering of transactions which is consistent with priority constraints.
    """
    m = Module()
    sched = Scheduler(len(cc))
    m.submodules.scheduler = sched
    for k, transaction in enumerate(cc):
        m.d.comb += sched.requests[k].eq(transaction.ready & transaction.runnable)
        m.d.comb += transaction.run.eq(sched.grant[k] & sched.valid)
    return m
