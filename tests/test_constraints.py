import pytest

from snakeoil.constraints import Problem


def any_of(**kwargs):
    return any(kwargs.values())


def all_of(**kwargs):
    return all(kwargs.values())


def test_readd_variables():
    p = Problem()
    p.add_variable((True, False), "x", "y")
    with pytest.raises(AssertionError, match="variable 'y' was already added"):
        p.add_variable((True, False), "y", "z")


def test_constraint_unknown_variable():
    p = Problem()
    p.add_variable((True, False), "x", "y")
    with pytest.raises(AssertionError, match="unknown variable 'z'"):
        p.add_constraint(any_of, ("y", "z"))


def test_empty_problem():
    p = Problem()
    assert tuple(p) == ({},)


def test_empty_constraints():
    p = Problem()
    p.add_variable((True, False), "x", "y")
    p.add_variable((True,), "z")
    assert len(tuple(p)) == 4


def test_domain_prefer_later():
    p = Problem()
    p.add_variable((False, True), "x", "y")
    p.add_constraint(any_of, ("x", "y"))
    assert next(iter(p)) == {"x": True, "y": True}


def test_constraint_single_variable():
    p = Problem()
    p.add_variable((True, False), "x", "y")
    p.add_constraint(lambda x: x, ("x",))
    p.add_constraint(lambda y: not y, ("y",))
    assert tuple(p) == ({"x": True, "y": False},)


def test_no_solution():
    p = Problem()
    p.add_variable((True,), "x")
    p.add_variable((True, False), "y", "z")
    p.add_constraint(lambda x, y: not x or y, ("x", "y"))
    p.add_constraint(lambda y, z: not y or not z, ("y", "z"))
    p.add_constraint(lambda x, z: not x or z, ("x", "z"))
    assert not tuple(p)


def test_no_solution_after_unary_pruned_domain():
    p = Problem()
    p.add_variable((True, False), "a")
    p.add_variable((True, False), "c")
    p.add_variable((True,), "systemd")
    p.add_constraint(lambda a: a, ("a",))
    p.add_constraint(lambda a, c: a == c, ("a", "c"))
    p.add_constraint(lambda systemd: not systemd, ("systemd",))
    assert not tuple(p)


def test_empty_domain_after_unary_skips_the_search():
    """An empty domain settles the problem without exploring anything"""
    calls = []

    p = Problem()
    p.add_variable((False,), "needed")
    p.add_constraint(lambda needed: needed, ("needed",))

    free = [f"f{i}" for i in range(8)]
    p.add_variable((True, False), *free)

    def counted(**kwargs):
        calls.append(kwargs)
        return any(kwargs.values())

    p.add_constraint(counted, frozenset(free))

    assert tuple(p) == ()
    assert calls == []


def test_unary_constraints_all_applied():
    p = Problem()
    p.add_variable((1, 2, 3), "a", "b", "c", "d")
    p.add_constraint(lambda a: a == 1, ("a",))
    p.add_constraint(lambda b: b == 2, ("b",))
    p.add_constraint(lambda c: c == 3, ("c",))
    p.add_constraint(lambda d: d == 1, ("d",))
    next(iter(p), None)
    assert p.constraints == []
    assert p.variables["a"] == [1]
    assert p.variables["b"] == [2]
    assert p.variables["c"] == [3]
    assert p.variables["d"] == [1]


def test_forward_check():
    p = Problem()
    p.add_variable(range(2, 10), "x", "y", "z")
    p.add_constraint(lambda x, y: (x + y) % 2 == 0, ("x", "y"))
    p.add_constraint(lambda x, y, z: (x * y * z) % 2 != 0, ("x", "y", "z"))
    p.add_constraint(lambda y, z: y < z, ("y", "z"))
    p.add_constraint(lambda z, x: x**2 <= z, ("x", "z"))
    assert tuple(p) == (
        {"x": 3, "y": 7, "z": 9},
        {"x": 3, "y": 5, "z": 9},
        {"x": 3, "y": 3, "z": 9},
    )


def test_variable_order_prefers_degree_over_domain_size():
    """The order variables are assigned in, which decides solution order."""
    p = Problem()
    p.add_variable((1, 2, 3), "wide")
    p.add_variable((7, 8), "narrow", "other")
    p.add_constraint(lambda wide, narrow: wide != narrow - 6, ("wide", "narrow"))
    p.add_constraint(lambda wide, other: wide != other - 6, ("wide", "other"))

    solutions = tuple(p)
    assert solutions == (
        {"wide": 3, "narrow": 8, "other": 8},
        {"wide": 3, "narrow": 8, "other": 7},
        {"wide": 3, "narrow": 7, "other": 8},
        {"wide": 3, "narrow": 7, "other": 7},
        {"wide": 2, "narrow": 7, "other": 7},
        {"wide": 1, "narrow": 8, "other": 8},
    )
    # dict equality ignores key order
    assert tuple(solutions[0]) == ("wide", "narrow", "other")


def test_solution_order_follows_domain_order_per_variable():
    """Each variable's own domain order decides which solutions come first"""
    p = Problem()
    p.add_variable((False, True), "x", "y")
    p.add_variable((True, False), "z")
    p.add_constraint(lambda x, y: x or y, ("x", "y"))
    p.add_constraint(lambda y, z: not (y and z), ("y", "z"))

    assert tuple(p) == (
        {"y": True, "z": False, "x": True},
        {"y": True, "z": False, "x": False},
        {"y": False, "x": True, "z": True},
        {"y": False, "x": True, "z": False},
    )


def test_abandoned_iteration():
    def build():
        p = Problem()
        p.add_variable(range(2, 6), "x", "y", "z")
        p.add_constraint(lambda x, y: x % y == 0, frozenset({"x", "y"}))
        p.add_constraint(lambda x, z: x > z, frozenset({"z", "x"}))
        return p

    def solutions(problem):
        return sorted(tuple(sorted(s.items())) for s in problem)

    expected = solutions(build())
    assert expected

    # forward checking hides values in the domains as the search descends; a
    # consumer that stops early must not be left with a pruned problem.
    p = build()
    next(iter(p))
    assert expected == solutions(p)

    p = build()
    for _ in p:
        break
    assert expected == solutions(p)

    # ... and finishing normally is still repeatable
    p = build()
    assert expected == solutions(p)
    assert expected == solutions(p)
