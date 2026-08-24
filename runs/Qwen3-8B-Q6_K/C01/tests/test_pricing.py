from pricing import calculate_invoice

def test_no_discount():
    assert calculate_invoice([10000, 20000], 0.10, False) == 33000

def test_volume_discount():
    assert calculate_invoice([100000], 0.10, False) == 99000

def test_member_after_volume_discount():
    # 100000 -> 90000 -> member 5% => 85500 -> tax 10% => 94050
    assert calculate_invoice([100000], 0.10, True) == 94050

def test_member_only():
    # 50000 -> 47500 -> 52250
    assert calculate_invoice([50000], 0.10, True) == 52250

def test_half_up_rounding():
    # 101 * 1.005 = 101.505 -> 102 with ROUND_HALF_UP
    assert calculate_invoice([101], 0.005, False) == 102
