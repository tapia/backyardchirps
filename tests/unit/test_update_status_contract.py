"""
Hold deploy/update.sh to the states and steps the code knows about.

The status file is written by bash and read by Python, so nothing but a test connects the
two. UpdateState and UpdateStep are the contract; this checks the writer keeps to it.

The reader falls back rather than raising when it meets something unknown, which is right
at runtime and would hide a typo forever. This is what makes the typo visible instead.
"""

import re
from pathlib import Path

from backyardchirps.features.updates.entity import UpdateState
from backyardchirps.features.updates.entity import UpdateStep

UPDATER = Path(__file__).resolve().parents[2] / "deploy" / "update.sh"

# `write_status running checking "..."` and `fail checking "..."`, which is write_status
# with the state fixed to failed.
WRITE_STATUS = re.compile(r"^\s*write_status\s+(\S+)\s+(\S+)\s", re.MULTILINE)
FAIL = re.compile(r"^\s*fail\s+(\S+)\s", re.MULTILINE)


def updater_source() -> str:
    return UPDATER.read_text()


def literals(names: set[str]) -> set[str]:
    """
    Drop anything that is a shell variable rather than a name.

    `fail` is `write_status failed "$1" "$2"`, so its own definition looks like a call
    writing a step called "$1". What this checks is the names the script spells out.
    """
    return {name for name in names if not name.startswith(("$", '"', "'"))}


def test_every_state_the_updater_writes_is_one_the_code_knows() -> None:
    written = literals({match.group(1) for match in WRITE_STATUS.finditer(updater_source())})

    assert written, "No write_status calls found, so this test is checking nothing."
    unknown = written - {state.value for state in UpdateState}
    assert not unknown, f"deploy/update.sh writes states the code does not know: {sorted(unknown)}"


def test_every_step_the_updater_writes_is_one_the_code_knows() -> None:
    written = literals({match.group(2) for match in WRITE_STATUS.finditer(updater_source())})
    written |= literals({match.group(1) for match in FAIL.finditer(updater_source())})

    assert written, "No steps found, so this test is checking nothing."
    unknown = written - {step.value for step in UpdateStep}
    assert not unknown, f"deploy/update.sh writes steps the code does not know: {sorted(unknown)}"


def test_the_updater_reports_both_ways_an_update_can_end() -> None:
    """
    A run that only ever wrote `running` would leave the page spinning for ever.
    """
    source = updater_source()
    written = literals({match.group(1) for match in WRITE_STATUS.finditer(source)})

    assert UpdateState.SUCCEEDED.value in written
    assert FAIL.search(source), "Nothing calls fail, so no failure would ever be reported."
