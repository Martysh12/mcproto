from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Optional

from typing_extensions import Self

__all__ = ["SemanticVersion"]


_SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_NUMBER_RE = re.compile("[0-9]+")


@dataclass
class SemanticVersion:
    """Comparable representation of semantic project versions.

    .. seealso:: `Semantic Versioning specification. <https://semver.org>`_
    """

    version: tuple[int, int, int]
    prerelease: Optional[tuple[str, ...]] = None
    build_metadata: Optional[tuple[str, ...]] = None

    @classmethod
    def from_string(cls, string_version: str) -> Self:
        """Build an instance from the semantic version passed as a string"""
        match = _SEMVER_REGEX.match(string_version)
        if not match:
            raise ValueError(f"Invalid version: {string_version!r} (not a semantic version)")

        major, minor, patch, prerelease, build_metadata = match.group(
            "major", "minor", "patch", "prerelease", "buildmetadata"
        )

        version = int(major), int(minor), int(patch)
        prerelease = tuple(prerelease.split(".")) if prerelease else None
        build_metadata = tuple(build_metadata.split(".")) if build_metadata else None

        return cls(version, prerelease, build_metadata)

    @property
    def major(self) -> int:
        """Major version number of the semantic version."""
        return self.version[0]

    @property
    def minor(self) -> int:
        """Minor version number of the semantic version."""
        return self.version[1]

    @property
    def patch(self) -> int:
        """Patch version number of the semantic version."""
        return self.version[2]

    def __str__(self) -> str:
        vstring = ".".join(map(str, self.version))

        if self.prerelease:
            vstring += "".join(map(str, self.prerelease))

        return vstring

    def __repr__(self) -> str:
        return f"ProjectVersion({str(self)!r})"

    def __eq__(self, other: Any) -> bool:  # noqa: ANN401
        if not isinstance(other, SemanticVersion):
            return NotImplemented

        # Compare general versions
        if self.version != other.version:
            return False

        # If this is a full release, check if other is also
        if self.prerelease is None:
            return other.prerelease is None

        # This version is a prerelease (we know from above check), but other version isn't
        if other.prerelease is None:
            return False

        # Both versions are pre-releases, only succeed if they're matching
        return self.prerelease == other.prerelease

    @staticmethod
    def _lt_prerelease(prerelease1: tuple[str, ...], prerelease2: tuple[str, ...]) -> bool:
        """Perform a less than comparison on pre-release versions (``prerelease1`` < ``prerelease2``).

        This check is based on the semantic version rules:
            - A larger set of pre-release fields has higher precedence (if all preceding identifiers are equal)
            - Identifiers consisting of only digits are compared numerically.
            - Identifiers containing letters or hyphens are compared lexically in ASCII order.
            - Numeric identifiers have lower precedence than non-numeric ones.
        """
        # Compare each pre-release identifier from left to right, until a difference is found
        for self_id, other_id in zip_longest(prerelease1, prerelease2, fillvalue=None):
            # - A larger set of pre-release fields has higher precedence (if all preceding identifiers are equal)

            # other has higher precedence, as it has more fields
            if self_id is None:
                return True
            # Self has higher precedence, as it has more fields
            if other_id is None:
                return False

            if _NUMBER_RE.match(self_id):
                self_id = int(self_id)
            if _NUMBER_RE.match(other_id):
                other_id = int(other_id)

            # - Identifiers consisting of only digits are compared numerically.
            if isinstance(self_id, int) and isinstance(other_id, int):
                if self_id == other_id:
                    continue
                return self_id < other_id

            # - Identifiers containing letters or hyphens are compared lexically in ASCII order.
            if isinstance(self_id, str) and isinstance(other_id, str):
                if self_id == other_id:
                    continue
                return self_id < other_id

            # - Numeric identifiers have lower precedence than non-numeric ones.
            return isinstance(other_id, str)

        # All pre-release fields are equal
        return False

    def __lt__(self, other: Any) -> bool:  # noqa: ANN401
        if not isinstance(other, SemanticVersion):
            return NotImplemented

        # First compare general versions
        if self.version < other.version:
            return True
        if self.version > other.version:
            return False

        # Versions are equal, compare prerelease status

        # If self is a full release, other is either before self (if it's a prerelease), or it's equal
        # in either case, the less than check fails.
        if self.prerelease is None:
            return False

        # We know this is a prerelease (from above check), so if other is a full release,
        # we know it came before self, passing the less than check.
        if other.prerelease is None:
            return True

        # Compare the individual prereleases
        return self._lt_prerelease(self.prerelease, other.prerelease)

    def __gt__(self, other: Any) -> bool:  # noqa: ANN401
        return other.__lt__(self)

    def __ge__(self, other: Any) -> bool:  # noqa: ANN401
        return self.__gt__(other) or self.__eq__(other)

    def __le__(self, other: Any) -> bool:  # noqa: ANN401
        return self.__lt__(other) or self.__eq__(other)
