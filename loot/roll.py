"""副本掉落与ROLL点系统"""
import random
from dataclasses import dataclass, field

# 职业 -> 护甲类型
CLASS_ARMOR = {
    "warrior": "plate", "paladin": "plate", "deathknight": "plate",
    "hunter": "mail", "shaman": "mail",
    "rogue": "leather", "druid": "leather", "monk": "leather",
    "mage": "cloth", "priest": "cloth", "warlock": "cloth",
}
ARMOR_ORDER = ["cloth", "leather", "mail", "plate"]

@dataclass
class LootItem:
    iid: str
    name: str
    required_class: str = ""  # 职业限制
    armor_type: str = ""  # 护甲类型
    drop_rate: float = 0.1

class LootSystem:
    SOFT_PITY = 20   # 连续未出次数达到后逐步提升掉率
    HARD_PITY = 50   # 硬保底：连续未出达到此次数必掉
    DUP_WINDOW = 3   # 防重复：最近N次掉落记录内同一件不再出
    BASE_GROUP = 10  # 掉率基准人数

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.pity_counter: dict[str, int] = {}  # boss_id -> 未出次数
        self.recent_drops: dict[str, list] = {}  # boss_id -> [item_ids]
        self.trade_window = 7200  # 2小时可交易
        self.rolls: dict[str, list] = {}  # item_id -> [(player, type, roll)]

    def roll_drop(self, boss_id: str, loot_table: list[LootItem], player_count: int = 10) -> list:
        # 个人拾取：掉率按人数相对基准缩放
        scale = max(0.0, player_count / self.BASE_GROUP)
        counter = self.pity_counter.get(boss_id, 0)
        drops = []
        for item in loot_table:
            if not self.check_duplicate_protection(boss_id, item.iid):
                continue
            rate = min(1.0, item.drop_rate * scale)
            # 软保底：连续未出越多掉率越高
            if counter >= self.SOFT_PITY:
                rate = min(1.0, rate * (1 + (counter - self.SOFT_PITY + 1) * 0.25))
            if self.rng.random() < rate:
                drops.append(item)
        # 硬保底：达到上限仍未出则强制掉一件（优先掉率最低的）
        if not drops and counter + 1 >= self.HARD_PITY and loot_table:
            eligible = [i for i in loot_table
                        if self.check_duplicate_protection(boss_id, i.iid)] or list(loot_table)
            drops.append(min(eligible, key=lambda i: i.drop_rate))
        if drops:
            self.pity_counter[boss_id] = 0
            recent = self.recent_drops.setdefault(boss_id, [])
            recent.extend(i.iid for i in drops)
            del recent[:-10]
        else:
            self.pity_counter[boss_id] = counter + 1
        return drops

    def can_need(self, player_class: str, item: LootItem) -> bool:
        if item.required_class and item.required_class != player_class:
            return False
        if item.armor_type:
            own = CLASS_ARMOR.get(player_class)
            if own is None:
                return False
            # 只能需求自身护甲类型及以下的装备
            if ARMOR_ORDER.index(own) < ARMOR_ORDER.index(item.armor_type):
                return False
        return True

    def resolve_roll(self, item_id: str) -> str:
        # 需求优先于贪婪：有人需求时贪婪不参与
        entries = self.rolls.get(item_id)
        if not entries:
            return ""
        needs = [e for e in entries if e[1] == "need"]
        pool = needs if needs else [e for e in entries if e[1] == "greed"]
        if not pool:
            return ""
        best = max(pool, key=lambda x: x[2])
        return best[0]

    def on_roll_timeout(self, item_id: str) -> tuple:
        # 倒计时结束：先需求，无人需求则贪婪，都没人则分解
        winner = self.resolve_roll(item_id)
        if winner:
            return ("loot", winner)
        return ("disenchant", "")

    def add_roll(self, item_id: str, player: str, roll_type: str, roll: int):
        self.rolls.setdefault(item_id, []).append((player, roll_type, roll))

    def check_duplicate_protection(self, boss_id: str, item_id: str) -> bool:
        # 最近掉落记录中出现过的装备进入冷却，短期内不再掉落
        recent = self.recent_drops.get(boss_id, [])
        if item_id in recent[-self.DUP_WINDOW:]:
            return False
        return True

    def can_trade(self, item_id: str, elapsed: float) -> bool:
        # 分配后2小时内可交易给同团成员，超时绑定
        return elapsed <= self.trade_window
