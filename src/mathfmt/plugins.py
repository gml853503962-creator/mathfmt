"""Stable extension API for custom formula recognizers.

Recognizers are deliberately passed to each scan operation instead of being kept
in a process-global registry.  This makes scans deterministic, thread-safe, and
straightforward to reproduce from report metadata.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol, runtime_checkable

Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class FormulaCandidate:
    """A formula span returned by a custom recognizer.

    ``start`` and ``end`` are zero-based offsets into the paragraph text and
    ``source`` must equal ``text[start:end]``.  ``linear`` may normalize custom
    notation into syntax understood by :func:`mathfmt.formula_to_mathml`.

    Custom recognizers normally set only ``start``, ``end``, ``source``,
    ``linear``, ``display``, ``confidence``, ``confidence_reason``, and ``kind``.
    The remaining fields are also used by MathFmt's built-in recognizers.
    """

    start: int
    end: int
    source: str
    linear: str | None = None
    display: bool = False
    explicit: bool = False
    chemistry: bool = False
    physics: str | None = None
    confidence: Confidence | None = None
    confidence_reason: str | None = None
    recognizer: str | None = None
    kind: str | None = None


@runtime_checkable
class FormulaRecognizer(Protocol):
    """Protocol implemented by MathFmt formula-recognition plugins."""

    name: str

    def recognize(self, text: str) -> Iterable[FormulaCandidate]:
        """Return candidate spans for one complete paragraph of text."""


class RecognizerError(ValueError):
    """Raised when a recognizer cannot be loaded or returns invalid data."""


@dataclass(frozen=True)
class _LoadedRecognizer:
    name: str
    plugin: FormulaRecognizer
    spec: str
    version: str | None

    def recognize(self, text: str) -> Iterable[FormulaCandidate]:
        return self.plugin.recognize(text)


def recognizer_name(recognizer: FormulaRecognizer) -> str:
    """Return and validate a recognizer's stable report name."""
    name = getattr(recognizer, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise RecognizerError("Formula recognizer must define a non-empty string 'name'")
    name = name.strip()
    if len(name) > 128 or any(character in "\r\n\t" for character in name):
        raise RecognizerError("Formula recognizer name must be one line and at most 128 characters")
    if not callable(getattr(recognizer, "recognize", None)):
        raise RecognizerError(f"Formula recognizer {name!r} must define recognize(text)")
    version = getattr(recognizer, "version", None)
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise RecognizerError(f"Formula recognizer {name!r} version must be a non-empty string")
    return name


def normalize_recognizers(
    recognizers: Sequence[FormulaRecognizer] | Iterable[FormulaRecognizer],
) -> tuple[FormulaRecognizer, ...]:
    """Validate recognizers and reject ambiguous duplicate names."""
    normalized = tuple(recognizers)
    names: set[str] = set()
    for recognizer in normalized:
        name = recognizer_name(recognizer)
        if name in names:
            raise RecognizerError(f"Duplicate formula recognizer name: {name!r}")
        names.add(name)
    return normalized


def recognizer_metadata(recognizer: FormulaRecognizer) -> dict[str, object]:
    """Return deterministic metadata recorded in scan and batch reports."""
    name = recognizer_name(recognizer)
    plugin = recognizer.plugin if isinstance(recognizer, _LoadedRecognizer) else recognizer
    metadata: dict[str, object] = {
        "name": name,
        "module": plugin.__class__.__module__,
        "object": plugin.__class__.__qualname__,
    }
    spec = getattr(recognizer, "spec", None)
    if isinstance(spec, str) and spec:
        metadata["spec"] = spec
    version = getattr(recognizer, "version", None)
    if version is None:
        version = getattr(plugin, "version", None)
    if isinstance(version, str) and version:
        metadata["version"] = version
    return metadata


def recognizers_metadata(
    recognizers: Sequence[FormulaRecognizer] | Iterable[FormulaRecognizer],
) -> list[dict[str, object]]:
    """Validate recognizers and return their ordered report metadata."""
    return [recognizer_metadata(item) for item in normalize_recognizers(recognizers)]


def load_recognizer(spec: str) -> FormulaRecognizer:
    """Load ``module:object`` as a recognizer.

    Classes are instantiated without arguments.  Other objects must already
    implement :class:`FormulaRecognizer`.  Importing a plugin executes trusted
    Python code, so CLI users should load only modules they trust.
    """
    module_name, separator, object_path = spec.partition(":")
    if not separator or not module_name.strip() or not object_path.strip():
        raise RecognizerError("Recognizer must use the form module:object")
    try:
        value: object = importlib.import_module(module_name.strip())
        for attribute in object_path.strip().split("."):
            value = getattr(value, attribute)
        if inspect.isclass(value):
            value = value()
    except Exception as exc:
        raise RecognizerError(f"Could not load recognizer {spec!r}: {exc}") from exc

    name = recognizer_name(value)  # type: ignore[arg-type]
    version = getattr(value, "version", None)
    return _LoadedRecognizer(
        name=name,
        plugin=value,  # type: ignore[arg-type]
        spec=spec,
        version=version,
    )


def _validate_candidate(text: str, name: str, candidate: FormulaCandidate) -> FormulaCandidate:
    if not isinstance(candidate, FormulaCandidate):
        raise RecognizerError(f"Formula recognizer {name!r} must return FormulaCandidate objects")
    if (
        isinstance(candidate.start, bool)
        or isinstance(candidate.end, bool)
        or not isinstance(candidate.start, int)
        or not isinstance(candidate.end, int)
        or candidate.start < 0
        or candidate.end <= candidate.start
        or candidate.end > len(text)
    ):
        raise RecognizerError(
            f"Formula recognizer {name!r} returned invalid range "
            f"[{candidate.start}, {candidate.end}) for paragraph length {len(text)}"
        )
    expected_source = text[candidate.start : candidate.end]
    if candidate.source != expected_source:
        raise RecognizerError(
            f"Formula recognizer {name!r} returned source that does not match "
            f"text[{candidate.start}:{candidate.end}]"
        )
    if candidate.linear is not None and (
        not isinstance(candidate.linear, str) or not candidate.linear.strip()
    ):
        raise RecognizerError(f"Formula recognizer {name!r} returned an empty linear formula")
    for field_name in ("display", "explicit", "chemistry"):
        if not isinstance(getattr(candidate, field_name), bool):
            raise RecognizerError(f"Formula recognizer {name!r} returned non-boolean {field_name!r}")
    if candidate.physics is not None and (
        not isinstance(candidate.physics, str) or not candidate.physics.strip()
    ):
        raise RecognizerError(f"Formula recognizer {name!r} returned an invalid physics kind")
    if candidate.confidence not in (None, "high", "medium", "low"):
        raise RecognizerError(
            f"Formula recognizer {name!r} returned invalid confidence {candidate.confidence!r}"
        )
    if candidate.confidence_reason is not None and (
        not isinstance(candidate.confidence_reason, str) or not candidate.confidence_reason.strip()
    ):
        raise RecognizerError(f"Formula recognizer {name!r} returned an empty confidence reason")
    if candidate.kind is not None and (not isinstance(candidate.kind, str) or not candidate.kind.strip()):
        raise RecognizerError(f"Formula recognizer {name!r} returned an invalid candidate kind")
    return replace(candidate, recognizer=name)


def recognize_with_plugins(
    text: str,
    recognizers: Sequence[FormulaRecognizer] | Iterable[FormulaRecognizer],
    *,
    claimed: Sequence[tuple[int, int]] = (),
) -> list[FormulaCandidate]:
    """Run plugins in order and return validated, non-overlapping candidates.

    Ranges in ``claimed`` always win.  Among plugins, an earlier recognizer wins
    an overlap.  This is the stable conflict-resolution rule for MathFmt 1.x.
    """
    accepted: list[FormulaCandidate] = []
    occupied = list(claimed)
    for recognizer in normalize_recognizers(recognizers):
        name = recognizer_name(recognizer)
        try:
            raw_candidates = list(recognizer.recognize(text))
        except Exception as exc:
            raise RecognizerError(f"Formula recognizer {name!r} failed: {exc}") from exc
        for raw_candidate in raw_candidates:
            candidate = _validate_candidate(text, name, raw_candidate)
            if any(candidate.start < end and candidate.end > start for start, end in occupied):
                continue
            accepted.append(candidate)
            occupied.append((candidate.start, candidate.end))
    return accepted
