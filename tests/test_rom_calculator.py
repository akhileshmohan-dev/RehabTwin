from rehabilitation.rom_calculator import calculate_rom


def test_basic_rom():
    angles = [170, 150, 120, 90, 110, 140, 170]

    result = calculate_rom(angles)

    assert result["min_angle"] == 90
    assert result["max_angle"] == 170
    assert result["rom"] == 80


def test_empty_input():
    result = calculate_rom([])

    assert result["min_angle"] is None
    assert result["max_angle"] is None
    assert result["rom"] is None


def test_single_angle():
    result = calculate_rom([120])

    assert result["min_angle"] == 120
    assert result["max_angle"] == 120
    assert result["rom"] == 0