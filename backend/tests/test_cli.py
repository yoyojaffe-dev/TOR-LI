"""Unit tests for the shared CLI helpers (validators + SIGINT wrapper)."""

import argparse

import pytest

from scripts import _cli


@pytest.mark.parametrize("value,expected", [("1", 1), ("5000", 5000)])
def test_positive_int_accepts(value: str, expected: int) -> None:
    assert _cli.positive_int(value) == expected


@pytest.mark.parametrize("value", ["0", "-5", "abc", "1.5"])
def test_positive_int_rejects(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _cli.positive_int(value)


@pytest.mark.parametrize("value,expected", [("0", 0.0), ("3", 3.0), ("2.5", 2.5)])
def test_nonneg_float_accepts(value: str, expected: float) -> None:
    assert _cli.nonneg_float(value) == expected


@pytest.mark.parametrize("value", ["-0.1", "x"])
def test_nonneg_float_rejects(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _cli.nonneg_float(value)


@pytest.mark.parametrize("value", ["-90", "0", "32.0853", "90"])
def test_latitude_accepts_in_range(value: str) -> None:
    _cli.latitude(value)  # no raise


@pytest.mark.parametrize("value", ["-90.1", "90.1", "999", "nope"])
def test_latitude_rejects_out_of_range(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _cli.latitude(value)


@pytest.mark.parametrize("value", ["-180", "34.78", "180"])
def test_longitude_accepts_in_range(value: str) -> None:
    _cli.longitude(value)  # no raise


@pytest.mark.parametrize("value", ["-180.1", "180.1", "bad"])
def test_longitude_rejects_out_of_range(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _cli.longitude(value)


def test_run_safely_passes_through_normal_return() -> None:
    calls = []
    _cli.run_safely(lambda: calls.append("ran"))
    assert calls == ["ran"]


def test_run_safely_converts_sigint_to_exit_130() -> None:
    def boom() -> None:
        raise KeyboardInterrupt

    with pytest.raises(SystemExit) as exc:
        _cli.run_safely(boom)
    assert exc.value.code == 130


def test_add_version_flag_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    _cli.add_version(parser)
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    assert "tor-li-agents" in capsys.readouterr().out
