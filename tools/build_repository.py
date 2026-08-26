"""
Turn a pool of .deb files into the signed apt repository a station installs from.

  uv run --no-project python tools/build_repository.py --pool build/pool --add build/packages/*.deb

Two suites share one pool:

  stable   what a station follows. Releases only
  main     the per-commit suite. Releases and builds off main

Output is key=value lines on stdout and progress on stderr, the same shape the other two
builders use, so a caller can do:

  uv run --no-project python tools/build_repository.py … >> "$GITHUB_ENV"

--no-project because nothing here needs the project environment. It shells out to
apt-ftparchive and gpg, so it runs on Debian and not on a laptop. The parts worth testing
are pure and live at the top of the file.
"""

import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
from collections import defaultdict
from itertools import zip_longest
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent

# Both suites, and which packages each one is offered. stable is what an owner's station
# follows; main exists so every commit is exercised on real hardware before it is a release.
STABLE = "stable"
MAIN = "main"
SUITES = (STABLE, MAIN)

COMPONENT = "main"
ARCHITECTURE = "arm64"

# Everything comes from one source tree, so one pool directory holds all of it. The b/ level
# is Debian's convention: the first letter of the source package name.
POOL_PREFIX = f"pool/{COMPONENT}/b/backyardchirps"

# How many versions of each package survive a prune, per suite. The two big packages keep
# one because the published site has a 1 GB limit and they are what fills it. Keeping a few
# of the app costs little and leaves apt something to downgrade to by hand.
#
# This is not what protects a rollback: the updater pre-downloads the version it would roll
# back to, so a station never depends on an old version still being here.
KEEP_PER_SUITE = {
    "backyardchirps": 5,
    "backyardchirps-deps": 1,
    "backyardchirps-species-data": 1,
    "backyardchirps-archive-keyring": 1,
}
KEEP_BY_DEFAULT = 1

ORIGIN = "Backyard Chirps"
LABEL = "Backyard Chirps"
DESCRIPTION = "Backyard Chirps station packages"

# The keyring package, and the two files inside it that decide what a station trusts and
# where it looks.
KEYRING_PACKAGE = "backyardchirps-archive-keyring"
KEYRING_FILES = (
    "./usr/share/keyrings/backyardchirps-archive-keyring.gpg",
    "./etc/apt/sources.list.d/backyardchirps.sources",
)

# A pooled file is identified by its own control data, never by its name.
CONTROL_FIELDS = ("Package", "Version", "Architecture")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the signed apt repository from a pool of .deb files.")
    parser.add_argument(
        "--pool",
        type=Path,
        required=True,
        help="flat directory of .deb files, as downloaded from the pool release. Mutated in place",
    )
    parser.add_argument(
        "--add",
        type=Path,
        nargs="*",
        default=[],
        help="newly built .deb files to put in the pool before indexing",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "build" / "repository",
        help="where to write the tree to publish (default: build/repository). Emptied first",
    )
    parser.add_argument(
        "--sign-key",
        default="",
        help="key id to sign the Release files with. Without it nothing is signed, which is only ever a test",
    )
    arguments = parser.parse_args()

    pool = arguments.pool.resolve()
    pool.mkdir(parents=True, exist_ok=True)
    output = arguments.output.resolve()

    added = _add_to_pool(pool, arguments.add)
    pooled = _pooled(pool)
    kept, pruned = plan_pool(pooled, just_built=added)
    for name in pruned:
        (pool / name).unlink()
        _say(f"pruned {name} ({pooled[name][0]} {pooled[name][1]})")

    shutil.rmtree(output, ignore_errors=True)
    published = _lay_out_pool(pool, output, kept, pooled)
    _write_indexes(output, published, arguments.sign_key)
    if arguments.sign_key:
        _export_key(output, arguments.sign_key)

    _say(f"{len(kept)} packages in the pool, {len(pruned)} pruned")
    print(f"REPOSITORY_DIR={output}")
    print(f"POOL_DIR={pool}")
    print(f"ADDED={','.join(added)}")
    print(f"PRUNED={','.join(pruned)}")


def suites_for(version: str) -> tuple[str, ...]:
    """
    Which suites a version belongs in.

    A build off main carries a PEP 440 local version, the + and everything after it, and
    that is the whole difference between "somebody pushed to main" and "somebody cut a
    release". Only a release reaches a station an owner runs.
    """
    return (MAIN,) if "+" in version else SUITES


def plan_additions(pooled: set[tuple[str, str]], incoming: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """
    Which of the packages just built are actually new, given what the pool already holds.

    Identity is the package name and its version, and nothing else.
    """
    return {identity for identity in incoming if identity not in pooled}


def keyring_files_that_changed(built: dict[str, str], published: dict[str, str]) -> list[str]:
    """
    Which of the keyring package's files differ between a fresh build and the published copy
    carrying the same version. Empty means the two are the same package.

    Compared file by file rather than by the .deb's bytes, because nfpm stamps the build time
    into an archive and two builds of one version therefore never match.
    """
    return sorted(name for name in set(built) | set(published) if built.get(name) != published.get(name))


def plan_pool(
    pooled: dict[str, tuple[str, str]],
    just_built: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Decide which pooled files survive, given every file name mapped to its package and
    version.
    """
    one_per_version: dict[tuple[str, str], str] = {}
    for name in sorted(pooled):
        one_per_version.setdefault(pooled[name], name)

    per_suite: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (package, version), name in one_per_version.items():
        for suite in suites_for(version):
            per_suite[(suite, package)].append(name)

    kept: set[str] = set()
    for (_, package), names in per_suite.items():
        newest_first = sorted(names, key=lambda name: DebianVersion(pooled[name][1]), reverse=True)
        kept.update(newest_first[: KEEP_PER_SUITE.get(package, KEEP_BY_DEFAULT)])
    kept.update(name for name in just_built or [] if name in pooled)

    return sorted(kept), sorted(set(pooled) - kept)


def stanzas_for(packages_text: str, pooled: dict[str, tuple[str, str]], suite: str) -> str:
    """
    Cut one suite's Packages index out of the index of the whole pool.
    """
    wanted = []
    for stanza in packages_text.strip().split("\n\n"):
        if not stanza.strip():
            continue
        name = Path(_field(stanza, "Filename")).name
        entry = pooled.get(name)
        if entry is None:
            _fail(f"apt-ftparchive indexed {name}, which is not in the pool.")
        if suite in suites_for(entry[1]):
            wanted.append(stanza.strip())
    return "\n\n".join(wanted) + "\n" if wanted else ""


class DebianVersion:
    """
    A Debian version that sorts the way dpkg sorts it.
    """

    def __init__(self, version: str) -> None:
        self.text = version
        epoch, _, rest = version.partition(":")
        if not rest:
            self.epoch, rest = 0, version
        else:
            self.epoch = int(epoch)
        self.upstream, _, self.revision = rest.rpartition("-")
        if not self.upstream:
            self.upstream, self.revision = rest, ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DebianVersion):
            return NotImplemented
        return _compare(self, other) == 0

    def __lt__(self, other: "DebianVersion") -> bool:
        return _compare(self, other) < 0

    def __repr__(self) -> str:
        return f"DebianVersion({self.text!r})"


def _compare(left: DebianVersion, right: DebianVersion) -> int:
    if left.epoch != right.epoch:
        return -1 if left.epoch < right.epoch else 1
    upstream = _compare_parts(left.upstream, right.upstream)
    return upstream if upstream else _compare_parts(left.revision, right.revision)


def _compare_parts(left: str, right: str) -> int:
    """
    Compare one half of two versions, run by run, padding the shorter one.
    """
    for mine, theirs in zip_longest(_comparable(left), _comparable(right), fillvalue=[0]):
        if mine != theirs:
            return -1 if mine < theirs else 1
    return 0


def _comparable(part: str) -> list[list[int]]:
    """
    Turn one half of a version into runs Python can compare, following dpkg's rule.
    """
    runs: list[list[int]] = []
    index = 0
    while index < len(part):
        letters = ""
        while index < len(part) and not part[index].isdigit():
            letters += part[index]
            index += 1
        runs.append([_character_order(character) for character in letters] + [0])

        digits = ""
        while index < len(part) and part[index].isdigit():
            digits += part[index]
            index += 1
        runs.append([int(digits) if digits else 0])
    return runs


def _character_order(character: str) -> int:
    """
    dpkg's order for the non-digit characters: a tilde first, then letters, then everything
    else. Shifting the non-letters above the whole ASCII range is what puts them last.
    """
    if character == "~":
        return -1
    if character.isalpha():
        return ord(character)
    return ord(character) + 256


def _add_to_pool(pool: Path, new_packages: list[Path]) -> list[str]:
    """
    Copy the newly built packages in, keeping any version that is already published.
    """
    pooled = _pooled(pool)
    incoming = [(package, _identity(package)) for package in new_packages if _exists(package)]
    wanted = plan_additions(set(pooled.values()), [identity for _, identity in incoming])
    # By identity rather than by name, for the reason everything else here is: the pool store
    # rewrites some names, so the published copy of a version is not always where its own
    # name would put it.
    published = {identity: pool / name for name, identity in sorted(pooled.items(), reverse=True)}

    added = []
    for package, identity in incoming:
        if identity not in wanted:
            if identity[0] == KEYRING_PACKAGE:
                _refuse_a_changed_keyring(package, published[identity], identity[1])
            _say(f"{identity[0]} {identity[1]} is already published, keeping the pooled copy")
            continue
        wanted.remove(identity)
        shutil.copy2(package, pool / _canonical_name(identity))
        added.append(_canonical_name(identity))
        _say(f"added {identity[0]} {identity[1]}")
    return added


def _refuse_a_changed_keyring(built: Path, published: Path, version: str) -> None:
    """
    Stop the publish when the keyring package was rebuilt with new content at a version that
    has already been published.
    """
    changed = keyring_files_that_changed(_keyring_digests(built), _keyring_digests(published))
    if not changed:
        return
    _say(f"the keyring package differs from the published {version} in: {', '.join(changed)}")
    _fail(
        f"The keyring package was rebuilt with new content at version {version}, which is "
        "already published, so no station would ever be offered it.\n"
        "Rotating the archive key or changing APT_BASE_URL does not move that version on its "
        "own: it counts commits over packaging/apt.\n"
        "Give it a version of its own with --keyring-version on tools/build_packages.py, or "
        "change a file in packaging/apt in the same commit."
    )


def _keyring_digests(package: Path) -> dict[str, str]:
    """
    A sha256 of each of the keyring package's two files, read out of the .deb itself.
    """
    payload = _capture_bytes(["dpkg-deb", "--fsys-tarfile", str(package)])
    digests = {}
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        for name in KEYRING_FILES:
            try:
                member = archive.extractfile(name)
            except KeyError:
                member = None
            if member is None:
                _fail(f"{package.name} does not carry {name}.")
            digests[name] = hashlib.sha256(member.read()).hexdigest()
    return digests


def _exists(package: Path) -> bool:
    if not package.exists():
        _fail(f"{package} does not exist.")
    return True


def _pooled(pool: Path) -> dict[str, tuple[str, str]]:
    """
    Every .deb in the pool, mapped to the package and version it says it is.
    """
    return {path.name: _identity(path) for path in sorted(pool.glob("*.deb"))}


def _identity(package: Path) -> tuple[str, str]:
    """
    The package name and version, out of the .deb's own control data.
    """
    fields = _capture_bytes(["dpkg-deb", "--field", str(package), *CONTROL_FIELDS]).decode("utf-8")
    read = {}
    for line in fields.splitlines():
        name, _, value = line.partition(":")
        read[name.strip()] = value.strip()
    for field in CONTROL_FIELDS:
        if not read.get(field):
            _fail(f"{package.name} has no {field} field.")
    if read["Architecture"] != ARCHITECTURE:
        _fail(f"{package.name} is {read['Architecture']}, and this repository carries {ARCHITECTURE} only.")
    return (read["Package"], read["Version"])


def _canonical_name(identity: tuple[str, str]) -> str:
    return f"{identity[0]}_{identity[1]}_{ARCHITECTURE}.deb"


def _lay_out_pool(
    pool: Path, output: Path, kept: list[str], pooled: dict[str, tuple[str, str]]
) -> dict[str, tuple[str, str]]:
    """
    Put the surviving packages where their Filename field will say they are, under the name
    Debian would give them rather than whatever the pool store called them.

    Hard links where the filesystem allows it, so the tree costs no extra disk. That matters
    more than it sounds: the virtualenv package alone is most of what the published site is
    allowed to hold.
    """
    destination = output / POOL_PREFIX
    destination.mkdir(parents=True)
    published = {}
    for name in kept:
        canonical = _canonical_name(pooled[name])
        published[canonical] = pooled[name]
        try:
            os.link(pool / name, destination / canonical)
        except OSError:
            shutil.copy2(pool / name, destination / canonical)
    return published


def _write_indexes(output: Path, published: dict[str, tuple[str, str]], sign_key: str) -> None:
    """
    Index the pool once, split the result per suite, and write a Release beside each.
    """
    _say("indexing the pool")
    packages_text = _capture(["apt-ftparchive", "packages", POOL_PREFIX], working_directory=output)

    for suite in SUITES:
        binary = output / "dists" / suite / COMPONENT / f"binary-{ARCHITECTURE}"
        binary.mkdir(parents=True)
        (binary / "Packages").write_text(stanzas_for(packages_text, published, suite), encoding="utf-8")
        # Both, because apt picks whichever it prefers and an older one may only know gzip.
        _run(["gzip", "--keep", "--force", "--no-name", "Packages"], working_directory=binary)
        _run(["xz", "--keep", "--force", "Packages"], working_directory=binary)
        _write_release(output, suite, sign_key)


def _write_release(output: Path, suite: str, sign_key: str) -> None:
    """
    Write the Release file for one suite and sign it.

    No Valid-Until. It is the honest choice here: the taxonomy job publishes only when the
    upstream file changes, so weeks can pass between publishes, and an expiry would turn a
    quiet month into every station reporting a broken repository.
    """
    suite_dir = output / "dists" / suite
    settings = {
        "Origin": ORIGIN,
        "Label": LABEL,
        "Suite": suite,
        "Codename": suite,
        "Architectures": ARCHITECTURE,
        "Components": COMPONENT,
        "Description": f"{DESCRIPTION} ({suite})",
    }
    options = []
    for name, value in settings.items():
        options += ["-o", f"APT::FTPArchive::Release::{name}={value}"]
    release = _capture(
        ["apt-ftparchive", *options, "release", str(suite_dir.relative_to(output))],
        working_directory=output,
    )
    (suite_dir / "Release").write_text(release, encoding="utf-8")

    if not sign_key:
        _say(f"{suite}: not signed, because no key was given")
        return
    _run(
        ["gpg", "--batch", "--yes", "--local-user", sign_key, "--clearsign", "--output", "InRelease", "Release"],
        working_directory=suite_dir,
    )
    _run(
        [
            "gpg",
            "--batch",
            "--yes",
            "--local-user",
            sign_key,
            "--detach-sign",
            "--armor",
            "--output",
            "Release.gpg",
            "Release",
        ],
        working_directory=suite_dir,
    )


def _export_key(output: Path, sign_key: str) -> None:
    """
    The public key at the root of the site, which is what a first install fetches before it
    has any package at all. Every install after that gets it from the keyring package.
    """
    (output / "KEY.gpg").write_bytes(_capture_bytes(["gpg", "--export", sign_key]))


def _field(stanza: str, name: str) -> str:
    for line in stanza.splitlines():
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1].strip()
    _fail(f"A Packages stanza has no {name} field:\n{stanza}")


def _capture(command: list[str], working_directory: Path) -> str:
    return _capture_bytes(command, working_directory).decode("utf-8")


def _capture_bytes(command: list[str], working_directory: Path | None = None) -> bytes:
    result = subprocess.run(command, cwd=working_directory, capture_output=True, check=False)
    if result.returncode != 0:
        _fail(f"`{' '.join(command)}` failed with exit {result.returncode}:\n{result.stderr.decode('utf-8')}")
    return result.stdout


def _run(command: list[str], working_directory: Path) -> None:
    result = subprocess.run(command, cwd=working_directory, stdout=sys.stderr, check=False)
    if result.returncode != 0:
        _fail(f"`{' '.join(command)}` failed with exit {result.returncode}. The reason is above.")


def _say(message: str) -> None:
    print(f"[repository] {message}", file=sys.stderr)


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
