def test_ktrdr_imports():
    """Test that basic KTRDR imports work."""
    try:
        import ktrdr

        assert True
    except ImportError:
        raise AssertionError("Failed to import ktrdr package") from None


def test_environment():
    """Test that the testing environment is properly set up."""
    assert True, "Basic test environment check passed"
