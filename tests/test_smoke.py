from accesstwin import config


def test_config_paths_exist():
    assert config.DATA_DIR.exists()
    assert config.mock_mode() is True
