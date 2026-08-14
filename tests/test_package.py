import quant


def test_package_is_importable() -> None:
    assert quant.__version__ == "0.1.0"
