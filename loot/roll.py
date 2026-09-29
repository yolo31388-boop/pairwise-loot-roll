"""副本掉落与ROLL点系统"""
import random
from collections import deque
from dataclasses import dataclass, field

@dataclass
class LootItem:
    iid: str
    name: str
    required_class: str = ""  # 职业限制
    armor_type: str = ""  # 护甲类型
    drop_rate: float = 0.1

# 职业可穿戴的护甲类型
CLASS_ARMOR = {
    "warrior": {"plate", "mail", "leather", "cloth"},
    "paladin": {"plate", "mail", "leather", "cloth"},
    "deathknight": {"plate", "mail", "leather", "cloth"},
    "hunter": {"mail", "leather", "cloth"},
    "shaman": {"mail", "leather", "cloth"},
    "rogue": {"leather", "cloth"},
    "druid": {"leather", "cloth"},
    "monk": {"leather", "cloth"},
    "demonhunter": {"leather", "cloth"},
    "mage": {"cloth"},
    "priest": {"cloth"},
    "warlock": {"cloth"},
}

class LootSystem:
    # 保底参数：每次未掉落按基础掉率累加提升，达到硬保底次数必掉
    PITY_SOFT_STEP = 1.0   # 每次未出提升 1 倍基础掉率
    PITY_HARD_CAP = 50     # 连续 50 次未出必掉
    # 防重复：同一件装备掉落后的保护间隔（CD 数）
    DUPLICATE_PROTECTION = 3
    # 个人拾取掉率基准人数
    BASE_PLAYER_COUNT = 10

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.pity_counter: dict[str, int] = {}  # boss_id -> 未出次数
        self.recent_drops: dict[str, list] = {}  # boss_id -> [item_ids]
        self._drop_history: dict[str, deque] = {}  # boss_id -> 每个CD的掉落批次
        self.trade_window = 7200  # 2小时可交易
        self.rolls: dict[str, list] = {}  # item_id -> [(player, type, roll)]

    def _scaled_rate(self, item: LootItem, player_count: int, pity: int) -> float:
        # 个人拾取：掉率按人数缩放
        rate = item.drop_rate * max(1, player_count) / self.BASE_PLAYER_COUNT
        # 软保底：每次未出按基础掉率累加提升
        rate *= 1.0 + self.PITY_SOFT_STEP * pity
        return min(1.0, rate)

    def roll_drop(self, boss_id: str, loot_table: list[LootItem], player_count: int = 10) -> list:
        pity = self.pity_counter.get(boss_id, 0)
        hard_pity = pity >= self.PITY_HARD_CAP
        drops = []
        for item in loot_table:
            # 防重复：保护期内不再掉落同一件
            if not self.check_duplicate_protection(boss_id, item.iid):
                continue
            if hard_pity or self.rng.random() < self._scaled_rate(item, player_count, pity):
                drops.append(item)
        if drops:
            self.pity_counter[boss_id] = 0
        else:
            self.pity_counter[boss_id] = pity + 1
        # 记录本CD掉落，超过保护期的旧记录自动过期
        history = self._drop_history.setdefault(
            boss_id, deque(maxlen=self.DUPLICATE_PROTECTION))
        history.append([item.iid for item in drops])
        self.recent_drops[boss_id] = [iid for batch in history for iid in batch]
        return drops

    def can_need(self, player_class: str, item: LootItem) -> bool:
        # 职业限制
        if item.required_class and player_class != item.required_class:
            return False
        # 护甲类型限制
        if item.armor_type:
            wearable = CLASS_ARMOR.get(player_class)
            if wearable is not None and item.armor_type not in wearable:
                return False
        return True

    def add_roll(self, item_id: str, player: str, roll_type: str, roll: int):
        self.rolls.setdefault(item_id, []).append((player, roll_type, roll))

    def resolve_roll(self, item_id: str) -> str:
        # 需求优先于贪婪：有人需求时贪婪不参与
        if item_id not in self.rolls:
            return ""
        entries = self.rolls[item_id]
        needs = [e for e in entries if e[1] == "need"]
        pool = needs if needs else [e for e in entries if e[1] == "greed"]
        if not pool:
            pool = entries
        best = max(pool, key=lambda x: x[2])
        return best[0]

    def finish_roll(self, item_id: str) -> str:
        # 倒计时结束：先需求、再贪婪，都没人点则分解
        winner = self.resolve_roll(item_id)
        return winner if winner else "disenchant"

    def check_duplicate_protection(self, boss_id: str, item_id: str) -> bool:
        # 保护期内同一件装备不允许连续掉落
        return item_id not in self.recent_drops.get(boss_id, [])

    def can_trade(self, item_id: str, elapsed: float) -> bool:
        # 分配后 2 小时内可交易给同团成员
        return elapsed <= self.trade_window
