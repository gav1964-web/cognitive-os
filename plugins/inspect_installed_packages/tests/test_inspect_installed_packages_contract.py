from plugins.inspect_installed_packages.src.main import run


def test_inspect_installed_packages_contract():
    result = run({"packages": ["sys", "definitely_missing_package_for_cos"]})

    assert result["packages"][0]["package"] == "sys"
    assert result["packages"][0]["available"] is True
    assert result["packages"][1] == {
        "package": "definitely_missing_package_for_cos",
        "available": False,
        "version": None,
    }
