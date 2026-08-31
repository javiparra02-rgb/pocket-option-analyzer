from __future__ import annotations

import json
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import CurrentVisualPriceStatus
from pocket_option_analyzer.vision.services import (
    PocketOptionCurrentVisualPriceExtractor,
)
from pocket_option_analyzer.vision.services import (
    pocket_option_current_visual_price_extractor as extractor_module,
)

_QualifiedSemanticCandidate = extractor_module._QualifiedSemanticCandidate
_SemanticCandidateGroup = extractor_module._SemanticCandidateGroup


_SESSION_NAME = "p04b_session_08_noise_floor_02"
_FORMAL_FALSE_AMBIGUITIES = (
    166,
    1354,
    1357,
    1359,
    1363,
    1364,
    1436,
    1439,
    1487,
    1490,
    1513,
    1520,
    1538,
    1539,
    1543,
    1545,
    1566,
    1568,
    1569,
    1572,
    1614,
    1666,
    1728,
    1729,
    1752,
    1768,
    1772,
    1773,
    1775,
    1829,
    1906,
    2145,
    2187,
    2238,
    2239,
    2247,
    2264,
    2268,
    2270,
    2274,
    2294,
    2298,
    2299,
    2312,
    2402,
    2419,
    2428,
    2429,
    2448,
    2451,
    2453,
    2455,
    2470,
    2472,
    2473,
    2481,
    2502,
    2506,
    2507,
    2526,
    2531,
)


@dataclass(frozen=True, slots=True)
class _QualifiedSummary:
    candidate_id: str
    qualified_row_ids: tuple[int, ...]
    line_hypothesis_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FrameSummary:
    status: CurrentVisualPriceStatus
    roi_y: float | None
    candidates: tuple[_QualifiedSummary, ...]
    semantic_group_count: int
    representative_window_id: str | None


class _CapturingExtractor(PocketOptionCurrentVisualPriceExtractor):
    def __init__(self) -> None:
        super().__init__()
        self.qualified_candidates: tuple[_QualifiedSemanticCandidate, ...] = ()

    def _semantic_candidate_groups(
        self,
        candidates: tuple[_QualifiedSemanticCandidate, ...],
    ) -> tuple[_SemanticCandidateGroup, ...]:
        self.qualified_candidates = candidates
        return super()._semantic_candidate_groups(candidates)


def _session_paths() -> tuple[Path, Path]:
    parent = Path.home() / "Documents" / "Programas"
    return parent / _SESSION_NAME, parent / f"{_SESSION_NAME}.zip"


def _identity_records(session_root: Path, archive: ZipFile | None) -> list[dict]:
    relative = Path("visual_evidence") / "identity_shadow" / "frames.jsonl"
    try:
        with (session_root / relative).open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream]
    except OSError:
        if archive is None:
            pytest.skip("P0.4b session08 identity evidence is not available locally.")
        member = f"{_SESSION_NAME}/{relative.as_posix()}"
        with archive.open(member) as stream:
            return [json.loads(line) for line in stream]


def _image_bytes(
    *,
    session_root: Path,
    relative: Path,
    archive: ZipFile | None,
) -> bytes:
    try:
        return (session_root / "visual_evidence" / relative).read_bytes()
    except OSError:
        if archive is None:
            pytest.skip(f"P0.4b session08 image is not available: {relative}")
        member = f"{_SESSION_NAME}/visual_evidence/{relative.as_posix()}"
        try:
            return archive.read(member)
        except KeyError:
            pytest.skip(f"P0.4b session08 image is not available: {relative}")


@lru_cache(maxsize=1)
def _replay() -> dict[int, _FrameSummary]:
    session_root, archive_path = _session_paths()
    if not session_root.is_dir() and not archive_path.is_file():
        pytest.skip("P0.4b session08 evidence is not available locally.")
    archive_context = ZipFile(archive_path) if archive_path.is_file() else nullcontext()
    extractor = _CapturingExtractor()
    summaries: dict[int, _FrameSummary] = {}
    with archive_context as archive:
        records = _identity_records(session_root, archive)
        for record in records:
            image_data = _image_bytes(
                session_root=session_root,
                relative=Path(record["png"]["filename"]),
                archive=archive,
            )
            image = cv2.imdecode(
                np.frombuffer(image_data, dtype=np.uint8),
                cv2.IMREAD_UNCHANGED,
            )
            if image is None:
                pytest.fail(f"Unable to decode session08 frame {record['frame_id']}.")
            analysis = extractor.extract_with_trace(image)
            semantic = analysis.trace.semantic_search
            groups = semantic.semantic_groups if semantic is not None else ()
            representative = (
                groups[0].representative_window_id if len(groups) == 1 else None
            )
            summaries[record["frame_id"]] = _FrameSummary(
                status=analysis.extraction.status,
                roi_y=(
                    analysis.extraction.price.roi_y
                    if analysis.extraction.price is not None
                    else None
                ),
                candidates=tuple(
                    _QualifiedSummary(
                        candidate_id=candidate.semantic_candidate_id,
                        qualified_row_ids=candidate.qualified_row_ids,
                        line_hypothesis_ids=candidate.line_hypothesis_ids,
                    )
                    for candidate in extractor.qualified_candidates
                ),
                semantic_group_count=len(groups),
                representative_window_id=representative,
            )
    assert len(summaries) == 2612
    return summaries


def _legacy_group_count(candidates: tuple[_QualifiedSummary, ...]) -> int:
    if not candidates:
        return 0
    parents = list(range(len(candidates)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for left_index, left in enumerate(candidates):
        left_ids = frozenset(left.line_hypothesis_ids)
        for right_index in range(left_index + 1, len(candidates)):
            if left_ids.intersection(candidates[right_index].line_hypothesis_ids):
                union(left_index, right_index)
    return len({find(index) for index in range(len(candidates))})


@pytest.mark.parametrize(
    ("frame_id", "expected_y", "expected_candidate_count"),
    [
        pytest.param(166, 129.0, 6, id="F166"),
        pytest.param(1354, 178.0, 6, id="F1354"),
        pytest.param(1363, 197.0, 7, id="F1363"),
        pytest.param(1728, 150.0, 8, id="F1728"),
        pytest.param(2402, 155.0, 9, id="F2402"),
        pytest.param(2451, 185.0, 5, id="F2451"),
    ],
)
def test_session08_fragmented_line_archetype_is_recovered(
    frame_id: int,
    expected_y: float,
    expected_candidate_count: int,
) -> None:
    frame = _replay()[frame_id]

    assert frame.status is CurrentVisualPriceStatus.OK
    assert frame.roi_y == expected_y
    assert frame.semantic_group_count == 1
    assert len(frame.candidates) == expected_candidate_count
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
        (int(expected_y),)
    }
    assert (
        len(
            {
                line_id
                for candidate in frame.candidates
                for line_id in candidate.line_hypothesis_ids
            }
        )
        == 2
    )
    assert any(
        left.qualified_row_ids == right.qualified_row_ids
        and not set(left.line_hypothesis_ids).intersection(right.line_hypothesis_ids)
        for index, left in enumerate(frame.candidates)
        for right in frame.candidates[index + 1 :]
    )
    assert frame.representative_window_id == max(
        candidate.candidate_id.split(":", maxsplit=1)[0]
        for candidate in frame.candidates
    )


def test_session08_f1021_distinct_vertical_prices_remain_ambiguous() -> None:
    frame = _replay()[1021]

    assert frame.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    assert frame.semantic_group_count == 2
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
        (121,),
        (398,),
    }


def test_session08_f1067_merges_only_same_row_fragments() -> None:
    frame = _replay()[1067]

    assert frame.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
    assert frame.semantic_group_count == 3
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
        (116,),
        (121,),
        (171,),
    }


def test_session08_all_formal_false_ambiguities_are_recovered() -> None:
    replay = _replay()
    recovered = [replay[frame_id] for frame_id in _FORMAL_FALSE_AMBIGUITIES]

    assert len(recovered) == 61
    assert all(frame.status is CurrentVisualPriceStatus.OK for frame in recovered)
    assert all(frame.semantic_group_count == 1 for frame in recovered)
    assert all(
        len({candidate.qualified_row_ids for candidate in frame.candidates}) == 1
        for frame in recovered
    )
    assert all(
        frame.roi_y == float(frame.candidates[0].qualified_row_ids[0])
        for frame in recovered
    )


def test_session08_full_replay_changes_only_exact_same_row_ambiguities() -> None:
    replay = _replay()
    legacy_counts: Counter[str] = Counter()
    post_counts = Counter(frame.status.value for frame in replay.values())
    transitions: Counter[tuple[str, str]] = Counter()
    ambiguous_group_transitions: Counter[tuple[int, int]] = Counter()

    for frame in replay.values():
        legacy_groups = _legacy_group_count(frame.candidates)
        if legacy_groups == 0:
            legacy_status = CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
        elif legacy_groups == 1:
            legacy_status = CurrentVisualPriceStatus.OK
        else:
            legacy_status = CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
            ambiguous_group_transitions[
                (legacy_groups, frame.semantic_group_count)
            ] += 1
        legacy_counts[legacy_status.value] += 1
        transitions[(legacy_status.value, frame.status.value)] += 1

    assert legacy_counts == Counter(
        {
            CurrentVisualPriceStatus.OK.value: 2349,
            CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE.value: 99,
            CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE.value: 164,
        }
    )
    assert post_counts == Counter(
        {
            CurrentVisualPriceStatus.OK.value: 2413,
            CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE.value: 35,
            CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE.value: 164,
        }
    )
    assert transitions == Counter(
        {
            (
                CurrentVisualPriceStatus.OK.value,
                CurrentVisualPriceStatus.OK.value,
            ): 2349,
            (
                CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE.value,
                CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE.value,
            ): 164,
            (
                CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE.value,
                CurrentVisualPriceStatus.OK.value,
            ): 64,
            (
                CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE.value,
                CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE.value,
            ): 35,
        }
    )
    assert ambiguous_group_transitions == Counter(
        {(2, 1): 64, (2, 2): 16, (3, 3): 15, (4, 3): 4}
    )


def test_session08_qualified_candidate_population_remains_small() -> None:
    replay = _replay()

    assert max(len(frame.candidates) for frame in replay.values()) == 15
