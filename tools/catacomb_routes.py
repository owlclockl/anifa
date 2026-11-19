"""Voxel tread audit for the Abbey: clear heads, openable doors and directional half steps."""

from collections import deque

import numpy as np

from . import build_catacomb_cathedral as b


# A clockwise order makes (d + 2) % 4 the opposite face. The collision model is at
# cell centers/edge-crossings, not a Minecraft movement or finite-width simulation.
DIRECTIONS = tuple(d for d, _, _ in b.t.CARDINAL)
VECTORS = tuple((dz, dx) for _, dx, dz in b.t.CARDINAL)
MAX_STEP = 9  # sixteenths, below Java's usual 0.6-block step height


def stair_edges(name: str, props: tuple) -> tuple[int, int, int, int]:
    p = dict(props)
    if name == 'minecraft:farmland':
        return (15,) * 4
    if name.endswith('_slab') and p['type'] == 'bottom':
        return (8,) * 4
    if name.endswith('_stairs') and p['half'] == 'bottom':
        low = (DIRECTIONS.index(p['facing']) + 2) % 4
        return tuple(8 if d == low else 16 for d in range(4))
    return (16,) * 4


def tread_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    states = b.c.STATES
    carpet = np.array([name.endswith('_carpet') for name, _ in states], dtype=np.uint8)
    through = carpet.astype(bool) | np.array([name in b.r.NONCOLLIDING or name.endswith(('_door', '_fence_gate', '_rail', ':rail', '_button', ':lever'))
                                             for name, _ in states])
    standable = np.array([b.r.could_support_spawn(name, p) or name.endswith(('_stairs', '_slab', '_glass', ':glass'))
                          or name == 'minecraft:sea_lantern' for name, p in states])
    return through, standable, carpet


def paths(blocks: np.ndarray, start: tuple[int, int, int], targets: set[tuple[int, int, int]], *, strict: bool = True,
          limit_y: int = 84, first_y: int = b.Y0) -> set[tuple[int, int, int]]:
    """Return destinations reached. Positions name the floor block (X, Y, Z), not the feet cell."""
    reached, _ = _search(blocks, start, targets, strict, first_y, limit_y)
    return reached


def reachable(blocks: np.ndarray, start: tuple[int, int, int]) -> np.ndarray:
    """All reachable floor cells in the strict model, across the site's full XYZ extent."""
    _, seen = _search(blocks, start, None, True, b.Y0, b.Y1)
    return seen


def _search(blocks, start, targets, strict, first_y, limit_y):
    through, standable, carpet = tread_tables()
    heights = [stair_edges(name, p) for name, p in b.c.STATES]
    low = blocks[first_y - b.Y0:limit_y - b.Y0 + 1]
    room = standable[low[:-2]] & through[low[1:-1]] & through[low[2:]]
    rug_height = carpet[low[1:-1]]
    ny, nz, nx = room.shape
    seen = np.zeros_like(room)

    def index(p):
        x, y, z = p
        return y - first_y, z - b.Z0, x - b.X0

    todo = {index(p): p for p in targets} if targets is not None else None
    here = index(start)
    reached = set()
    if not room[here]:
        return reached, seen
    queue = deque([here])
    seen[here] = True
    while queue and (todo is None or todo):
        y, z, x = queue.popleft()
        p = (y, z, x)
        if todo is not None and p in todo:
            reached.add(todo.pop(p))
        level = heights[low[p]]
        rug = int(rug_height[p]) if strict else 0
        for side, (dz, dx) in enumerate(VECTORS):
            zz, xx = z + dz, x + dx
            if not (0 <= zz < nz and 0 <= xx < nx):
                continue
            before = level[side] + rug
            for yy in range(max(0, y - 1), min(ny, y + 2)):
                dest = (yy, zz, xx)
                if seen[dest] or not room[dest]:
                    continue
                if strict:
                    after = 16 * (yy - y) + heights[low[dest]][(side + 2) % 4] + int(rug_height[dest])
                    if abs(after - before) > MAX_STEP:
                        continue
                seen[dest] = True
                queue.append(dest)
    return reached, seen
