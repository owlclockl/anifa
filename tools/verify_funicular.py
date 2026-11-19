"""Exercise the exported incline on a disposable, local vanilla Java 26.3 server.

Requires a Java 25+ runtime and the official server JAR (downloads are not performed).
Usage: python -m tools.verify_funicular --java /path/to/java --server /path/to/server.jar
"""

from __future__ import annotations

from . import catacomb_funicular as f
from .vanilla_catacomb_test import Server, Y_LIFT, place, read_args, session, xyz

# Bounds of the engine and its surroundings, in generator coords, inclusive.
BOUNDS = ((-70, -42, 166), (-18, -7, 216))


class Incline(Server):
    def token(self, at):
        self.checked(f'if items block {xyz(at)} container.0 minecraft:{f.TOKEN_ITEM}', 'Interlock token')
        other = f.LATCH if at == f.TOKEN else f.TOKEN
        self.checked(f'unless items block {xyz(other)} container.* minecraft:{f.TOKEN_ITEM}', 'Duplicate token')

    def rail(self, index, active=False):
        self.block(f.PARKS[index], f'powered_rail[shape=north_south,powered={str(active).lower()}]')

    def idle(self):
        self.token(f.TOKEN)
        for i, lamp in enumerate(f.LAMPS):
            self.rail(i)
            self.block(lamp, 'redstone_lamp[lit=false]')

    def press(self, index):
        x, y, z = f.CONTROLS[index]
        # A real wooden-button activation (arrow's hitbox), not a forced powered
        # state. This triggers the same neighbour updates and expiry as a use.
        self.commands(f'summon minecraft:arrow {x + .09} {y + Y_LIFT + .5} {z + .5} '
                      '{NoGravity:1b,Tags:["incline_test_arrow"]}')
        self.step(2)
        self.block(f.CONTROLS[index], 'oak_button[powered=true]')
        self.commands('kill @e[tag=incline_test_arrow]')

    def at_station(self, i):
        x, y, z = f.PARKS[i]
        self.checked(f'if entity @e[tag=incline_cart,type=minecart,x={x+.5},y={y+Y_LIFT+.06},z={z+.5},distance=..0.75]',
                     f'Cart stopped at station {i}')


def test(server, *, strict=True):
    place(server, 'incline', BOUNDS, strict=strict, padding=9)
    server.step(60)
    server.idle()
    for p in f.STOCK:
        server.checked(f'if items block {xyz(p)} container.0 minecraft:minecart', 'Station stock')
    x, y, z = f.PARKS[0]
    server.commands(f'summon minecraft:minecart {x+.5} {y+Y_LIFT+.063} {z+.5} {{Tags:["incline_cart"]}}')
    server.step(20)
    server.at_station(0)
    # Call from the other station; keep the second button attempt in the busy window.
    server.press(1)
    server.step(55)
    server.token(f.LATCH)
    for lamp in f.LAMPS:
        server.block(lamp, 'redstone_lamp[lit=true]')
    server.press(0)
    server.step(65)
    for i in (0, 1):
        server.rail(i)
    # The destination detector and actual bell must fire on a passing cart.
    hit = False
    for _ in range(21):
        check = server.commands(f'execute if block {xyz(f.DETECTORS[1])} detector_rail[powered=true] '
                                f'if block {xyz(f.BELLS[1])} bell[powered=true] run say ZZ_BELL_ZZ')
        if '] ZZ_BELL_ZZ' in check:
            hit = True
            break
        server.step(4)
    if not hit:
        raise AssertionError('The lower detector did not ring its bell')
    server.step(70)
    server.at_station(1)
    server.token(f.LATCH)
    server.step(230)
    server.idle()
    server.at_station(1)
    print('PASS: distant call; descent; second request suppressed; brake and automatic reset', flush=True)

    server.commands(f'summon armor_stand {x+.5} {y+Y_LIFT+1} {z+.5} {{Invisible:1b,Tags:["incline_rider"]}}',
                    'ride @e[tag=incline_rider,limit=1] mount @e[tag=incline_cart,limit=1]')
    server.press(1)
    server.step(90)
    server.token(f.LATCH)
    # Save during the cycle, not just in the idle state.
    server.stop()
    server.start()
    server.step(350)
    server.idle()
    server.at_station(0)
    server.checked('as @e[tag=incline_cart,limit=1] on passengers if entity @s[tag=incline_rider]',
                   'Passenger preserved through uphill run and reload')
    print('PASS: local dispatch uphill with a passenger; save/restart mid-cycle; cart, token and brakes recover', flush=True)

    for i in (0, 1, 0, 1):
        server.press(i)
        server.step(410)
        server.idle()
        server.at_station(1 - i)
    print('PASS: four more launches alternating directions after reload', flush=True)


def main():
    args = read_args(__doc__)
    with session(args, 'incline', BOUNDS, Incline) as server:
        test(server, strict=not args.neighbor_updates)


if __name__ == '__main__':
    main()
