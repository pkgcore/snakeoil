"""
Facilities for solving constraint satisfaction problems.

Usage examples:

>>> def divides_by(x, y):
>>>     return x % y == 0
>>>
>>> p = Problem()
>>> p.add_variable(range(2, 10), 'x', 'y', 'z')
>>> p.add_constraint(divides_by, frozenset({'x', 'y'}))
>>> p.add_constraint(lambda x, z: x > z, frozenset({'z', 'x'}))
>>> p.add_constraint(lambda y, x, z: x+y+z > 0, frozenset({'z', 'x', 'y'}))
>>> for solution in p:
>>>     print(f"x={solution['x']}, y={solution['y']}, z={solution['z']}")
"""

from collections import defaultdict
from typing import Any, Iterable, Protocol


class Constraint(Protocol):
    """Type used for constraint satisfaction check.

    .. py:function:: __call__(**kwargs: Any) -> bool

        Check satisfaction of the constraint.

        :param kwargs: keyworded arguments, named after the variables passed to
            :py:func:`Problem.add_constraint`, with assigned value from the
            domain.
        :return: ``True`` if the assignment is satisfied.
    """

    def __call__(self, **kwargs: Any) -> bool:
        raise NotImplementedError("Constraint", "__call__")


class _Domain(list):
    def __init__(self, items: Iterable[Any]):
        super().__init__(items)
        self._hidden = []
        self._states = []

    def hide_value(self, value):
        super().remove(value)
        self._hidden.append(value)

    def push_state(self):
        self._states.append(len(self))

    def pop_state(self):
        if diff := self._states.pop() - len(self):
            self.extend(self._hidden[-diff:])
            del self._hidden[-diff:]


class Problem:
    """
    Class used to define a problem and retrieve solutions.

    Define a problem by calling :py:func:`add_variable` and then
    :py:func:`add_constraint`, and then iterate over the problem to
    retrieve solutions satisfying the problem.

    For building solutions for the problem, the back tracking algorithm
    is used. It is a deterministic algorithm, which means the same solution
    is built if the variables and constraints were identically built.

    :note: The class is mutable, so adding variables or constraints
        during iteration of solutions might break the solver.

    .. py:function:: __iter__() -> Iterator[dict[str, Any]]

        Retrieve solutions satisfying the problem. Each solution consists
        of a :py:class:`dict` assigning to each variable in the problem a
        single value from it's domain.
    """

    def __init__(self):
        self.variables: dict[str, _Domain] = {}
        self.constraints: list[tuple[Constraint, frozenset[str]]] = []
        self.vconstraints: dict[
            str, list[tuple[Constraint, frozenset[str]]]
        ] = defaultdict(list)

    def add_variable(self, domain: Iterable[Any], *variables: str):
        """Add variables to the problem, which use the specified domain.

        :param domain: domain of possible values for the variables.
        :param variables: names of variables, to be used in assignment and
            checking the constraint satisfaction.
        :raises AssertionError: if the variable was already added previously
            to this problem.

        :Note: The solver prefers later values from the domain,
            meaning the first solutions will try to use the later values
            from each domain.
        """
        for variable in variables:
            assert (
                variable not in self.variables
            ), f"variable {variable!r} was already added"
            self.variables[variable] = _Domain(domain)

    def add_constraint(self, constraint: Constraint, variables: frozenset[str]):
        """Add constraint to the problem, which depends on the specified
        variables.

        :param constraint: Callable which accepts as keyworded args the
            variables, and returns True only if the assignment is satisfied.
        :param variables: names of variables, on which the constraint depends.
            Only those variables will be passed during check of constraint.
        :raises AssertionError: if the specified variables weren't added
            previously, so they have no domain.
        """
        self.constraints.append((constraint, variables))
        for variable in variables:
            assert variable in self.variables, f"unknown variable {variable!r}"
            self.vconstraints[variable].append((constraint, variables))

    def __check(
        self,
        constraint: Constraint,
        variables: frozenset[str],
        assignments: dict[str, Any],
    ) -> bool:
        assignments = {k: v for k, v in assignments.items() if k in variables}
        unassigned = variables - assignments.keys()
        if not unassigned:
            return constraint(**assignments)
        if len(unassigned) == 1:
            var = next(iter(unassigned))
            if domain := self.variables[var]:
                for value in domain[:]:
                    assignments[var] = value
                    if not constraint(**assignments):
                        domain.hide_value(value)
                del assignments[var]
                return bool(domain)
        return True

    def __iter__(self):
        for constraint, variables in self.constraints:
            if len(variables) == 1:
                variable, *_ = variables
                domain = self.variables[variable]
                for value in domain[:]:
                    if not constraint(**{variable: value}):
                        domain.remove(value)
                self.constraints.remove((constraint, variables))
                self.vconstraints[variable].remove((constraint, variables))

        assignments: dict[str, Any] = {}
        queue: list[tuple[str, _Domain, tuple[_Domain, ...]]] = []

        while True:
            # mix the Degree and Minimum Remaining Values (MRV) heuristics
            lst = sorted(
                (-len(self.vconstraints[name]), len(domain), name)
                for name, domain in self.variables.items()
            )
            for _, _, variable in lst:
                if variable not in assignments:
                    values = self.variables[variable][:]

                    push_domains = tuple(
                        domain
                        for name, domain in self.variables.items()
                        if name != variable and name not in assignments
                    )
                    break
            else:
                # no unassigned variables, we've got a solution.
                yield assignments.copy()
                # go back to last variable, if there's one.
                if not queue:
                    return
                variable, values, push_domains = queue.pop()
                for domain in push_domains:
                    domain.pop_state()

            while True:
                # we have a variable: do we have any values left?
                if not values:
                    # no, go back to last variable, if there's one
                    while queue:
                        del assignments[variable]
                        variable, values, push_domains = queue.pop()
                        for domain in push_domains:
                            domain.pop_state()
                        if values:
                            break
                    else:
                        return

                # got a value - check it
                assignments[variable] = values.pop()

                for domain in push_domains:
                    domain.push_state()

                if all(
                    self.__check(constraint, constraint_vars, assignments)
                    for constraint, constraint_vars in self.vconstraints[variable]
                ):
                    break

                for domain in push_domains:
                    domain.pop_state()
            # append state before looking for next variable
            queue.append((variable, values, push_domains))
