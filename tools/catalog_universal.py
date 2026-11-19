"""Build the seed catalog from misode/mcmeta's 26.3-summary release data.

The JSON is build-time data only. The in-game filter is one real item of each
listed type in a vanilla double chest. No predicates or packs run in the world.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

OUTPUT = Path(__file__).with_name('data') / 'java-26.3-warehouse.json'
SOURCE = 'https://github.com/misode/mcmeta/tree/d96c75fec200c4580dd75e033a76341521165461'
SEEDS_PER_CHEST = 42  # 12 guaranteed free slots, even for renamed items.
COLORS = ('light_blue', 'light_gray', 'white', 'orange', 'magenta', 'yellow', 'lime', 'pink',
          'gray', 'cyan', 'purple', 'blue', 'brown', 'green', 'red', 'black')
SHULKERS = frozenset(('shulker_box', *(f'{dye}_shulker_box' for dye in COLORS)))

# Order also determines distance travelled. Common bulk materials go first.
LABELS = (
    ('stone', 'Камень'), ('boxes', 'Шалкеры'), ('earth', 'Земля и песок'), ('metal', 'Металлы'),
    ('mineral', 'Руды и самоцветы'), ('redstone', 'Механизмы'), ('farm', 'Урожай'),
    ('food', 'Еда'), ('blocks', 'Стройка'), ('wood', 'Дерево'), ('woodwork', 'Столярка'),
    ('tools', 'Инструменты'), ('weapons', 'Оружие'), ('armor', 'Броня'),
    ('transport', 'Транспорт'), ('brewing', 'Зелья'), ('supplies', 'Материалы'),
    ('plants', 'Растения'), ('water', 'Море и лёд'), ('nether', 'Незер и Край'),
    ('glass', 'Стекло'), ('paint', 'Краски'), ('wool', 'Шерсть'), ('clay', 'Керамика'),
    ('concrete', 'Бетон'), ('decor', 'Декор'), ('library', 'Книги и карты'),
    ('relics', 'Коллекция'), ('technical', 'Техпредметы'), ('eggs', 'Яйца призыва'),
    ('containers', 'Ёмкости'), ('other', 'Разное'),
)
WOODS = ('acacia', 'bamboo', 'birch', 'cherry', 'crimson', 'dark_oak', 'jungle', 'mangrove',
         'oak', 'pale_oak', 'spruce', 'warped')


def kind(name, props, tags, blocks):
    """Classify in order; broader rules must not catch earlier specialties."""
    color = next((p for p in COLORS if name.startswith(p + '_')), None)
    dyed = name[len(color)+1:] if color else name
    if name in SHULKERS:
        return 'boxes'
    if name.endswith('_spawn_egg'):
        return 'eggs'
    if name in {'barrier', 'bedrock', 'command_block', 'chain_command_block', 'repeating_command_block',
                'structure_block', 'structure_void', 'debug_stick', 'jigsaw', 'light', 'knowledge_book',
                'test_block', 'test_instance_block', 'spawner', 'budding_amethyst', 'end_portal_frame',
                'infested_stone', 'command_block_minecart', 'player_head', 'allow', 'deny'} or name.startswith('infested_'):
        return 'technical'
    if name in {'potion', 'splash_potion', 'lingering_potion', 'tipped_arrow', 'glass_bottle',
                'brewing_stand', 'cauldron', 'blaze_powder', 'spider_eye', 'fermented_spider_eye',
                'phantom_membrane', 'ghast_tear', 'glistering_melon_slice', 'rabbit_foot', 'magma_cream', 'dragon_breath'}:
        return 'brewing'
    if name in tags('swords', 'spears', 'arrows') or name in {'bow', 'crossbow', 'trident', 'mace', 'shield', 'wind_charge'}:
        return 'weapons'
    if (name in tags('head_armor', 'chest_armor', 'leg_armor', 'foot_armor') or
            name.endswith('_armor') or name in {'elytra', 'turtle_helmet'}):
        return 'armor'
    if name in tags('axes', 'hoes', 'pickaxes', 'shovels', 'compasses') or name in {
            'shears', 'brush', 'fishing_rod', 'flint_and_steel', 'spyglass', 'lead', 'goat_horn', 'clock', 'name_tag'}:
        return 'tools'
    if name in tags('boats', 'chest_boats', 'harnesses') or name.endswith(('_minecart', '_harness')) or name in {
            'minecart', 'saddle', 'carrot_on_a_stick', 'warped_fungus_on_a_stick', 'firework_rocket'}:
        return 'transport'
    if name in {'wheat', 'hay_block', 'apple', 'beetroot', 'carrot', 'potato', 'pumpkin', 'melon', 'melon_slice',
                'sugar_cane', 'cocoa_beans', 'sweet_berries', 'glow_berries', 'nether_wart', 'bone_meal',
                'sugar', 'carved_pumpkin', 'dried_kelp', 'dried_kelp_block', 'pitcher_pod'} or name.endswith('_seeds'):
        return 'farm'
    if 'minecraft:food' in props or name in tags('eggs'):
        return 'food'
    if name.endswith(('_bucket', '_bundle')) or name in {'bucket', 'bundle', 'bowl'}:
        return 'containers'
    if name in {'book', 'writable_book', 'written_book', 'enchanted_book', 'paper', 'map'} or name.endswith('_map'):
        return 'library'
    if name in tags('metal_nuggets') or name.endswith(('_ingot', '_nugget')) or name in {
            'iron_block', 'copper_block', 'gold_block', 'netherite_block', 'netherite_scrap', 'ancient_debris'}:
        return 'metal'
    if name.endswith('_ore') or name.startswith('raw_') or name in {
            'coal', 'charcoal', 'coal_block', 'diamond', 'emerald', 'lapis_lazuli', 'quartz', 'amethyst_shard',
            'diamond_block', 'emerald_block', 'lapis_block', 'amethyst_block'}:
        return 'mineral'
    if name in tags('copper_golem_statues') or any(v in name for v in (
            'redstone', 'comparator', 'repeater', 'piston', 'observer', 'dispenser', 'dropper', 'rail', 'hopper',
            'sensor', 'crafter', 'lightning_rod', 'daylight_detector', 'target', 'tripwire', 'lever')):
        return 'redstone'
    if name in tags('dirt', 'mud', 'grass_blocks') or name in {'sand', 'red_sand', 'gravel', 'clay', 'clay_ball', 'suspicious_sand', 'suspicious_gravel'}:
        return 'earth'
    if 'glass' in name:
        return 'glass'
    if 'terracotta' in name or name in {'brick', 'bricks', 'brick_slab', 'brick_stairs', 'brick_wall', 'flower_pot'}:
        return 'clay'
    if 'concrete' in name:
        return 'concrete'
    if dyed in {'wool', 'carpet', 'bed', 'cushion'} or name in {'string', 'cobweb'}:
        return 'wool'
    if name in tags('dyes', 'loom_patterns', 'banners'):
        return 'paint'
    if name in tags('logs') or name == 'stick' or name.startswith('stripped_') or (
            name.startswith(tuple(p + '_' for p in WOODS)) and name.endswith('_planks')):
        return 'wood'
    if (name.startswith(tuple(p + '_' for p in WOODS)) and name.endswith((
            '_button', '_door', '_fence', '_fence_gate', '_sign', '_plate', '_shelf', '_slab', '_stairs', '_trapdoor'))):
        return 'woodwork'
    if name in tags('flowers', 'leaves', 'saplings', 'mushrooms', 'moss_blocks') or any(v in name for v in (
            'vine', 'azalea', 'sapling', 'propagule', 'fungus', 'roots', 'petals', 'lichen', 'cactus')):
        return 'plants'
    if any(v in name for v in ('coral', 'prismarine', 'kelp', 'ice', 'sponge', 'seagrass', 'sea_pickle', 'nautilus', 'turtle_egg')):
        return 'water'
    if name in {'obsidian', 'crying_obsidian', 'blaze_rod', 'ender_pearl', 'ender_eye', 'shulker_shell'} or any(
            v in name for v in ('nether', 'purpur', 'netherrack', 'end_stone', 'chorus', 'soul_sand', 'blackstone', 'basalt', 'glowstone')):
        return 'nether'
    if any(v in name for v in ('music_disc', 'pottery_sherd', 'smithing_template', 'ominous', 'banner_pattern', 'trial_key', 'disc_fragment')) or name == 'dragon_egg':
        return 'relics'
    if name in {'bone', 'bone_block', 'slime_ball', 'slime_block', 'resin_clump', 'resin_block', 'leather',
                'feather', 'gunpowder', 'rotten_flesh', 'honeycomb', 'honeycomb_block', 'ink_sac', 'glow_ink_sac',
                'armadillo_scute', 'turtle_scute', 'flint', 'rabbit_hide', 'resin_brick'}:
        return 'supplies'
    if name in blocks and any(v in name for v in ('stone', 'deepslate', 'tuff', 'andesite', 'diorite',
             'granite', 'calcite', 'dripstone')):
        return 'stone'
    if name in {'armor_stand', 'item_frame', 'glow_item_frame', 'painting'} or (name in blocks and any(
            v in name for v in ('sign', 'lantern', 'torch', 'candle', 'chest', 'barrel', 'head', 'skull', 'campfire',
                                'bookshelf', 'anvil', 'pot', 'shelf', 'chain', 'bell'))):
        return 'decor'
    if name in blocks:
        return 'blocks'
    return 'other'


def generate(metadata: Path):
    registry = json.loads((metadata/'registries/data.json').read_text())
    props = json.loads((metadata/'item_components/data.json').read_text())
    names = set(registry['item'])
    if names != set(props) or json.loads((metadata/'version.json').read_text())['data_version'] != 5023:
        raise ValueError('Expected the complete Java 26.3 release summary')
    raw_tags = json.loads((metadata/'data/tag/item/data.json').read_text())
    def tags(*keys):
        result = set()
        for key in keys:
            for value in raw_tags.get(key, {}).get('values', ()):
                value = value if isinstance(value, str) else value['id']
                if value.startswith('#minecraft:'):
                    result |= tags(value.removeprefix('#minecraft:'))
                elif value.startswith('minecraft:'):
                    result.add(value.removeprefix('minecraft:'))
        return result
    groups = defaultdict(list)
    blocks = frozenset(registry['block'])
    for name in sorted(names - {'air'}):
        groups[kind(name, props[name], tags, blocks)].append(name)
    bins = []
    for id_, label in LABELS:
        items = groups[id_]
        count = (len(items) + SEEDS_PER_CHEST - 1) // SEEDS_PER_CHEST
        # Leave extra room for cobblestone and deepslate in the first drawer.
        # The rest split evenly, including the remaining two stone drawers.
        first = 26 if id_ == 'stone' and count == 3 and len(items) <= 26 + 2*SEEDS_PER_CHEST else 0
        batches = ([items[:first]] if first else [])
        tail = items[first:]
        remaining = count - len(batches)
        batches.extend(tail[len(tail)*i//remaining:len(tail)*(i+1)//remaining] for i in range(remaining))
        for i, batch in enumerate(batches, 1):
            bins.append([label if count == 1 else f'{label} {i}', batch])
    assert sum(len(ids) for _, ids in bins) + 1 == len(names)
    return {'java': '26.3', 'source': SOURCE, 'registry_items': len(names), 'bins': bins}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('metadata', type=Path, help='extracted mcmeta tag 26.3-summary')
    args = parser.parse_args()
    catalog = generate(args.metadata)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{len(catalog['bins'])} double chests, {catalog['registry_items'] - 1} item IDs excluding air")


if __name__ == '__main__':
    main()
