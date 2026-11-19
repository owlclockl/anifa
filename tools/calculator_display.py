"""Decimal conversion, seven-segment decoding and the display timer netlist."""
from __future__ import annotations

from functools import cache
from itertools import combinations, product

from . import calculator_logic as logic

DIGITS = ('abcdef', 'bc', 'abdeg', 'abcdg', 'bcfg', 'acdfg', 'acdefg', 'abc', 'abcdefg', 'abcdfg')
SEGMENTS = 'abcdefg'
STAGES = 10


@cache
def implicants(on):
    """Minimize a 4-input truth table for a valid BCD nibble (0...9)."""
    on = set(on)
    primes = []
    for pattern in product((-1, 0, 1), repeat=4):  # -1: omit this literal
        cover = {n for n in range(10) if all(p < 0 or n >> i & 1 == p for i, p in enumerate(pattern))}
        if cover and cover <= on:
            primes.append((pattern, cover))
    primes = [(p, s) for p, s in primes if not any(s < larger for _, larger in primes)]
    for count in range(len(primes)+1):
        solutions = [group for group in combinations(primes, count) if set().union(*(s for _, s in group)) == on]
        if solutions:
            best = min(solutions, key=lambda g: sum(p.count(0)+p.count(1) for p, _ in g))
            return tuple(p for p, _ in best)
    raise AssertionError(on)


def table(c, bits, on):
    def term(pattern):
        node = 1
        for bit, value in zip(bits, pattern):
            if value == 1:
                node = c.and_(node, bit)
            elif value == 0:
                node = c.difference(node, bit)
        return node
    return c.any(term(p) for p in implicants(tuple(on)))


def add_three_if_needed(c, nibble):
    """A shared-term add-3 network; the input digit is always 0 through 9."""
    ones, twos, fours, eights = nibble
    four = c.difference(fours, c.or_(ones, twos))
    adjust = c.or_(eights, c.difference(fours, four))
    new_two = c.or_(c.difference(twos, c.difference(fours, ones)), c.difference(eights, ones))
    new_four = c.or_(four, c.and_(eights, ones))
    return [c.xor(ones, adjust), new_two, new_four, adjust]


def binary_to_bcd(c, word):
    """Shift-and-add-3 (double dabble), folding unreachable leading digits."""
    bcd = [[0]*4 for _ in range(5)]  # ones first
    for step, carry in enumerate(reversed(word)):
        c.bank = f'BCD{step//2}'
        for decade, nibble in enumerate(bcd):
            old = nibble
            if 2**step > 5*10**decade:
                old = add_three_if_needed(c, nibble)
            bcd[decade], carry = [carry, *old[:3]], old[3]
    return bcd


def display(c, word, negative, error, ready):
    bcd = binary_to_bcd(c, word)
    c.bank = 'GLYPH'
    show = c.difference(ready, error)
    seen = 0
    result = {'SIGN': c.and_(negative, show), 'WARN': c.and_(ready, error)}
    for i in reversed(range(5)):
        bits = bcd[i]
        seen = c.or_(seen, c.any(bits))
        enabled = c.and_(seen, show) if i else show
        for segment in SEGMENTS:
            lit = table(c, bits, (n for n, glyph in enumerate(DIGITS) if segment in glyph))
            result[f'D{i}{segment}'] = c.and_(lit, enabled)
    return result


def design():
    c = logic.design(('HOLD',))
    hold = c.inputs['HOLD']
    c.bank = 'TIMER'
    start = c.invert(hold)
    for i in range(STAGES):
        c.bank = f'DELAY{i}'
        elapsed = c.gate('DELAY', start)
        c.bank = 'TIMER'
        start = c.difference(elapsed, hold)
        if i < STAGES-1:
            c.outputs[f'P{i}'] = start
    ready = start
    c.bank = f'DELAY{STAGES}'
    reveal = c.gate('DELAY', ready)
    c.bank = 'TIMER'
    c.outputs[f'P{STAGES-1}'] = c.difference(reveal, hold)
    c.outputs.update(display(c, [c.outputs[f'R{i}'] for i in range(16)], c.outputs['NEG'], c.outputs['ERR'], ready))
    return c


def glyphs(value, error=False, ready=True):
    """Reference list of lit segment names, independent of the circuit."""
    if not ready:
        return set()
    if error:
        return {'WARN'}
    return ({'SIGN'} if value < 0 else set()) | {
        f'D{i}{segment}' for i, digit in enumerate(reversed(str(abs(value)))) for segment in DIGITS[int(digit)]}
