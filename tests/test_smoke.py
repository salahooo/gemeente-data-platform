"""Rooktest voor de minimale applicatie."""

from gemeente_data_platform.main import main


def test_main_confirms_project_foundation(capsys) -> None:
    """De entrypoint geeft de bevestiging van de projectbasis weer."""
    main()

    captured = capsys.readouterr()
    assert captured.out == "Gemeente Data Platform: projectbasis werkt.\n"
