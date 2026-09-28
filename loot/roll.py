"""副本掉落与ROLL点系统 - 含7个bug"""
import random
from dataclasses import dataclass, field

@dataclass
class LootItem:
    iid: str
    name: str
    required_class: str = ""  # 职业限制
    armor_type: str = ""  # 护甲类型
    drop_rate: float = 0.1

class LootSystem:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.pity_counter: dict[str, int] = {}  # boss_id -> 未出次数
        self.recent_drops: dict[str, list] = {}  # boss_id -> [item_ids]
        self.trade_window = 7200  # 2小时可交易
        self.rolls: dict[str, list] = {}  # item_id -> [(player, type, roll)]

    def roll_drop(self, boss_id: str, loot_table: list[LootItem], player_count: int = 10) -> list:
        # bug1: 无保底
        drops = []
        for item in loot_table:
            if self.rng.random() < item.drop_rate:
                drops.append(item)
        # bug2: 不按人数缩放
        return drops

    def can_need(self, player_class: str, item: LootItem) -> bool:
        # bug3: 不检查职业限制
        return True

    def resolve_roll(self, item_id: str) -> str:
        # bug4: 需求和贪婪混比
        if item_id not in self.rolls:
            return ""
        best = max(self.rolls[item_id], key=lambda x: x[2])
        return best[0]

    def add_roll(self, item_id: str, player: str, roll_type: str, roll: int):
        self.rolls.setdefault(item_id, []).append((player, roll_type, roll))

    def check_duplicate_protection(self, boss_id: str, item_id: str) -> bool:
        # bug5: 无防重复
        return True

    def can_trade(self, item_id: str, elapsed: float) -> bool:
        # bug6: 无交易期限
        return True
