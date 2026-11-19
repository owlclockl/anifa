"""Boolean netlist for the Moonspire 8-bit integer calculator.

Bit zero is the least significant throughout. Only three physical gates
are needed: inversion, OR, and A AND NOT B (a subtract-mode comparator).
"""
from __future__ import annotations

from dataclasses import dataclass

BITS = 8
MODES = ('+', '−', '×', '÷', '%', 'AND', 'OR', 'XOR')
INPUTS = tuple(f'{label}{i}' for label, count in (('A', BITS), ('B', BITS), ('M', 3)) for i in range(count))
OUTPUTS = tuple(f'R{i}' for i in range(2*BITS)) + ('NEG', 'ERR')


@dataclass(frozen=True)
class Gate:
    op: str
    args: tuple[int, ...]
    bank: str


class Circuit:
    def __init__(self, extra_inputs=()):
        self.gates = [Gate('ZERO', (), ''), Gate('ONE', (), '')]
        self.inputs = {name: i for i, name in enumerate(INPUTS+tuple(extra_inputs), 2)}
        self.gates.extend(Gate('INPUT', (), 'PANEL') for _ in self.inputs)
        self.outputs = {}
        self.inverse = {0: 1, 1: 0}
        self.cache = {}
        self.bank = 'PANEL'

    def gate(self, op, *args):
        key = op, args
        if key not in self.cache:
            self.cache[key] = len(self.gates)
            self.gates.append(Gate(op, args, self.bank))
        return self.cache[key]

    def invert(self, a):
        if a not in self.inverse:
            b = self.gate('NOT', a)
            self.inverse[a] = b
            self.inverse[b] = a
        return self.inverse[a]

    def or_(self, a, b):
        if a == 0 or a == b:
            return b
        if b == 0:
            return a
        if a == 1 or b == 1 or self.inverse.get(a) == b:
            return 1
        return self.gate('OR', *sorted((a, b)))

    def difference(self, a, b):
        """A binary 15-or-0 signal minus another, clamped at zero."""
        if a == b or a == 0 or b == 1:
            return 0
        if b == 0 or self.inverse.get(a) == b:
            return a
        if a == 1:
            return self.invert(b)
        return self.gate('DIFF', a, b)

    def and_(self, a, b):
        return self.difference(a, self.invert(b))

    def xor(self, a, b):
        return self.or_(self.difference(a, b), self.difference(b, a))

    def any(self, nodes):
        nodes = list(nodes)
        if not nodes:
            return 0
        while len(nodes) > 1:
            nodes = [self.or_(*nodes[i:i+2]) if i+1 < len(nodes) else nodes[i] for i in range(0, len(nodes), 2)]
        return nodes[0]

    def mux(self, flag, yes, no):
        if yes == no:
            return yes
        return self.or_(self.and_(yes, flag), self.difference(no, flag))

    def add(self, a, b):
        carry, bits = 0, []
        for x, y in zip(a, b, strict=True):
            left = self.difference(x, y)
            prop = self.or_(left, self.difference(y, x))
            r = self.difference(carry, prop)
            bits.append(self.or_(self.difference(prop, carry), r))
            carry = self.or_(self.difference(x, left), self.difference(carry, r))
        return bits, carry

    def subtract(self, a, b):
        borrow, bits = 0, []
        for x, y in zip(a, b, strict=True):
            gen = self.difference(y, x)
            prop = self.or_(self.difference(x, y), gen)
            r = self.difference(borrow, prop)
            bits.append(self.or_(self.difference(prop, borrow), r))
            borrow = self.or_(gen, r)
        return bits, borrow

    def absolute(self, word, negative):
        # Negation keeps the initial string of 0s and the lowest 1.
        lower, result = 0, []
        for bit in word:
            result.append(self.xor(bit, self.and_(lower, negative)))
            lower = self.or_(lower, bit)
        return result

    def multiply(self, a, b):
        result = [0]*(2*BITS)
        for i, v in enumerate(b):
            self.bank = f'MUL{i}'
            row = [self.and_(u, v) for u in a]
            low, carry = self.add(result[i:i+BITS], row)
            result[i:i+BITS+1] = [*low, carry]
        return result

    def divide(self, a, b):
        remainder, quotient = list(a), [0]*BITS
        # Restoring division, specialized to known shifts: never change the
        # low bits below the trial subtract. The high bits shifted out of
        # B must be zero or the trial subtraction cannot fit in eight bits.
        high = [self.any(b[BITS-i:]) for i in range(BITS)]
        for i in reversed(range(BITS)):
            self.bank = f'DIV{i}'
            trial, under = self.subtract(remainder[i:], b[:BITS-i])
            quot = self.invert(self.or_(under, high[i]))
            remainder[i:] = [self.mux(quot, t, r) for t, r in zip(trial, remainder[i:], strict=True)]
            quotient[i] = quot
        return quotient, remainder

    def evaluate(self, inputs, *, one=True):
        values = [one ^ one, one]
        for name in self.inputs:
            values.append(inputs[name])
        for g in self.gates[len(values):]:
            a = values[g.args[0]]
            if g.op == 'DELAY':
                values.append(a)  # identity once every repeater has settled
                continue
            if g.op == 'NOT':
                values.append(a ^ one)
                continue
            b = values[g.args[1]]
            values.append(a | b if g.op == 'OR' else a & (b ^ one))
        return values

    def live(self):
        needed = set(self.outputs.values())
        for idx in reversed(range(len(self.gates))):
            if idx in needed:
                needed.update(self.gates[idx].args)
        return needed


def design(extra_inputs=()):
    c = Circuit(extra_inputs)
    inputs = lambda label, width: [c.inputs[f'{label}{i}'] for i in range(width)]
    a, b, m = inputs('A', BITS), inputs('B', BITS), inputs('M', 3)
    c.bank = 'SUM'
    low, carry = c.add(a, b)
    addition = [*low, carry]
    c.bank = 'SUB'
    difference, negative = c.subtract(a, b)
    subtraction = c.absolute(difference, negative)
    product = c.multiply(a, b)
    c.bank = 'DIV7'
    quotient, remainder = c.divide(a, b)
    c.bank = 'LOGIC'
    bit_and = [c.and_(x, y) for x, y in zip(a, b)]
    bit_or = [c.or_(x, y) for x, y in zip(a, b)]
    bit_xor = [c.xor(x, y) for x, y in zip(a, b)]
    c.bank = 'SELECT'
    choice = []
    for i in range(len(MODES)):
        wrong = [c.invert(v) if i >> j & 1 else v for j, v in enumerate(m)]
        choice.append(c.invert(c.any(wrong)))
    divide_by_zero = c.invert(c.any(b))
    error = c.and_(c.or_(choice[3], choice[4]), divide_by_zero)
    choice[3] = c.difference(choice[3], divide_by_zero)
    choice[4] = c.difference(choice[4], divide_by_zero)
    result = (addition, subtraction, product, quotient, remainder, bit_and, bit_or, bit_xor)
    for k in range(2*BITS):
        c.bank = f'OUT{k//4}'
        c.outputs[f'R{k}'] = c.any(c.and_(word[k], active) for word, active in zip(result, choice) if k < len(word))
    c.outputs['NEG'] = c.and_(negative, choice[1])
    c.outputs['ERR'] = error
    return c


def inputs_for(a, b, op):
    return {k: bool({'A': a, 'B': b, 'M': op}[k[0]] >> int(k[1:]) & 1) for k in INPUTS}


def read(nets, values):
    word = sum(int(values[nets[f'R{i}']]) << i for i in range(2*BITS))
    return (-word if values[nets['NEG']] else word, bool(values[nets['ERR']]))


def reference(a, b, op):
    if b == 0 and op in (3, 4):
        return 0, True
    return (a+b, a-b, a*b, a//max(1, b), a%max(1, b), a&b, a|b, a^b)[op], False
