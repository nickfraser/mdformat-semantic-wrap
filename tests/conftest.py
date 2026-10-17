"""Keep pytest's temporary files inside the agent-owned workspace area."""


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(config.rootpath / ".ocs" / "pytest-tmp")
