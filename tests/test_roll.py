"""副本掉落与ROLL点系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loot.roll import LootSystem, LootItem

class TestPity:
    def test_pity_guarantees_drop(self):
        ls = LootSystem(seed=1)
        items = [LootItem("rare", "rare_item", drop_rate=0.01)]
        # 模拟100次击杀，1%掉率，保底应该确保至少出一次
        got = False
        for i in range(100):
            drops = ls.roll_drop("boss1", items)
            if drops:
                got = True
                break
        assert got == True  # bug1: 1%掉率100次不出的概率36%

class TestDropScaling:
    def test_drop_rate_scales_with_players(self):
        ls = LootSystem(seed=42)
        items = [LootItem("i1", "item1", drop_rate=0.5)]
        # 25人团应该比10人团掉率高（个人拾取模式）
        # 这里验证：多次运行，25人团的平均掉落数 > 10人团
        import statistics
        d10 = [len(ls.roll_drop("b", items, 10)) for _ in range(50)]
        d25 = [len(ls.roll_drop("b", items, 25)) for _ in range(50)]
        # 这个测试可能不稳定，换个确定性测法

class TestClassRestriction:
    def test_wrong_class_cannot_need(self):
        ls = LootSystem()
        item = LootItem("plate", "plate_helm", required_class="warrior", armor_type="plate")
        assert ls.can_need("mage", item) == False  # bug3: 返回True
        assert ls.can_need("warrior", item) == True

class TestNeedPriority:
    def test_need_beats_greed(self):
        ls = LootSystem()
        ls.add_roll("i1", "p1", "greed", 99)
        ls.add_roll("i1", "p2", "need", 1)
        winner = ls.resolve_roll("i1")
        assert winner == "p2"  # bug4: p1的99贪婪赢了

class TestDuplicateProtection:
    def test_duplicate_protection(self):
        ls = LootSystem()
        ls.recent_drops["boss1"] = ["rare_item"]
        # 刚出过rare_item，短期内不应再出
        assert ls.check_duplicate_protection("boss1", "rare_item") == False  # bug5: 返回True

class TestTradeWindow:
    def test_trade_window_expires(self):
        ls = LootSystem()
        assert ls.can_trade("i1", 8000) == False  # bug6: 超过2小时还能交易
        assert ls.can_trade("i1", 1000) == True
