#!/usr/bin/env python3
import json
import re
import sys


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def normalize_version(s):
    if s.startswith("v"):
        return s[1:]
    return s


def is_valid_semver(v):
    return SEMVER_RE.fullmatch(v) is not None


def pypi_has_version(releases, v):
    return v in releases


def needs_bump(current, target):
    return current != target


def _error(message):
    print(message, file=sys.stderr)


def _normalize(args):
    if len(args) != 1:
        _error("usage: release_prepare.py normalize <input>")
        return 2

    version = normalize_version(args[0])
    if not is_valid_semver(version):
        _error(f"invalid semver: {args[0]}")
        return 1

    print(version)
    return 0


def _pypi_check(args):
    if len(args) != 1:
        _error("usage: release_prepare.py pypi-check <version>")
        return 2

    version = args[0]
    if not is_valid_semver(version):
        _error(f"invalid semver: {version}")
        return 1

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        _error("invalid pypi json")
        return 1

    if not isinstance(payload, dict):
        _error("invalid pypi json: expected object")
        return 1

    releases = payload.get("releases")
    if not isinstance(releases, dict):
        _error("invalid pypi json: releases must be an object")
        return 1

    if pypi_has_version(releases, version):
        _error(f"version already exists on pypi: {version}")
        return 3

    return 0


def _needs_bump(args):
    if len(args) != 2:
        _error("usage: release_prepare.py needs-bump <current> <target>")
        return 2

    print("bump" if needs_bump(args[0], args[1]) else "skip")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        _error("usage: release_prepare.py <command> [args...]")
        return 2

    command = argv[0]
    args = argv[1:]

    if command == "normalize":
        return _normalize(args)
    if command == "pypi-check":
        return _pypi_check(args)
    if command == "needs-bump":
        return _needs_bump(args)

    _error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
