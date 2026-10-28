from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import pytest

from pocket_option_analyzer.vision.models import CurrentVisualPriceStatus
from pocket_option_analyzer.vision.models.current_visual_price_search import (
    CurrentVisualPriceLabelAssociation,
)
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
    proposed_line_hypothesis_ids_at_selected_row: tuple[str, ...]
    label_association_status_by_row: tuple[tuple[int, str], ...]
    qualified_local_guide_row_ids: tuple[int, ...]
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


def _association_status_by_row(
    associations: tuple[CurrentVisualPriceLabelAssociation, ...],
) -> tuple[tuple[int, str], ...]:
    # An unpaired hypothesis legitimately has no row-bearing pair descriptor.
    return tuple(
        sorted(
            {
                (run.row_y, association.status)
                for association in associations
                for pair in association.pairs
                for run in pair.hypothesis.runs
            }
        )
    )


def test_replay_association_summary_accepts_unpaired_hypothesis() -> None:
    unpaired = CurrentVisualPriceLabelAssociation(
        hypothesis_id="unpaired",
        pairs=(),
        eligible_pair_ids=(),
        rejected_pair_ids=(),
        component_groups=(),
        admissible_groups=(),
        canonical_window=None,
        max_line_gap_ratio=0.01,
    )
    assert unpaired.status == "unavailable"
    assert _association_status_by_row((unpaired,)) == ()


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
                proposed_line_hypothesis_ids_at_selected_row=(
                    tuple(
                        sorted(
                            {
                                pair.hypothesis.hypothesis_id
                                for pair in semantic.line_label_pairs
                                for run in pair.hypothesis.runs
                                if analysis.extraction.price is not None
                                and run.row_y == int(analysis.extraction.price.roi_y)
                            }
                        )
                    )
                    if semantic is not None
                    else ()
                ),
                label_association_status_by_row=(
                    _association_status_by_row(semantic.label_associations)
                    if semantic is not None
                    else ()
                ),
                qualified_local_guide_row_ids=(
                    tuple(
                        sorted(
                            {
                                guide.row_y
                                for evaluation in semantic.window_evaluations
                                for guide in evaluation.local_guides
                                if guide.qualified
                            }
                        )
                    )
                    if semantic is not None
                    else ()
                ),
                semantic_group_count=len(groups),
                representative_window_id=representative,
            )
    assert len(summaries) == 2612
    return summaries


@pytest.mark.parametrize(
    ("frame_id", "expected_y"),
    [
        pytest.param(166, 129.0, id="F166"),
        pytest.param(1354, 178.0, id="F1354"),
        pytest.param(1363, 197.0, id="F1363"),
        pytest.param(1728, 150.0, id="F1728"),
        pytest.param(2402, 155.0, id="F2402"),
        pytest.param(2451, 185.0, id="F2451"),
    ],
)
def test_session08_fragmented_line_archetype_is_recovered(
    frame_id: int,
    expected_y: float,
) -> None:
    frame = _replay()[frame_id]

    assert frame.status is CurrentVisualPriceStatus.OK
    assert frame.roi_y == expected_y
    assert frame.semantic_group_count == 1
    assert len(frame.proposed_line_hypothesis_ids_at_selected_row) >= 2
    assert frame.candidates
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
        (int(expected_y),)
    }
    assert all(
        set(candidate.line_hypothesis_ids).issubset(
            frame.proposed_line_hypothesis_ids_at_selected_row
        )
        for candidate in frame.candidates
    )
    assert frame.representative_window_id == max(
        candidate.candidate_id.split(":", maxsplit=1)[0]
        for candidate in frame.candidates
    )


def test_session08_f1021_ui_annotation_does_not_create_second_price() -> None:
    frame = _replay()[1021]

    assert frame.status is CurrentVisualPriceStatus.OK
    assert frame.roi_y == 398.0
    assert frame.semantic_group_count == 1
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
        (398,),
    }


def test_session08_f1067_ui_annotation_is_not_a_second_price() -> None:
    frame = _replay()[1067]

    # Keep the UI proposal visible, but do not bridge its detached glyphs into
    # an accredited LABEL. The real marker retains its external GUIDE.
    assert (121, "unavailable") in frame.label_association_status_by_row
    assert (121, "available") not in frame.label_association_status_by_row
    assert 121 not in frame.qualified_local_guide_row_ids
    assert (171, "available") in frame.label_association_status_by_row
    assert 171 in frame.qualified_local_guide_row_ids
    assert frame.status is CurrentVisualPriceStatus.OK
    assert frame.roi_y == 171.0
    assert frame.semantic_group_count == 1
    assert {candidate.qualified_row_ids for candidate in frame.candidates} == {
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


def test_session08_full_replay_respects_semantic_group_resolution() -> None:
    replay = _replay()
    assert len(replay) == 2612
    for frame in replay.values():
        if frame.semantic_group_count == 0:
            assert frame.status is CurrentVisualPriceStatus.NO_VISUAL_PRICE_CANDIDATE
            assert frame.roi_y is None
        elif frame.semantic_group_count == 1:
            assert frame.status in {
                CurrentVisualPriceStatus.OK,
                CurrentVisualPriceStatus.LOW_CONFIDENCE,
            }
            assert frame.representative_window_id is not None
            assert (frame.roi_y is not None) == (
                frame.status is CurrentVisualPriceStatus.OK
            )
        else:
            assert frame.status is CurrentVisualPriceStatus.AMBIGUOUS_VISUAL_PRICE
            assert frame.roi_y is None


def test_session08_qualified_candidate_population_remains_small() -> None:
    replay = _replay()

    # The historical maximum was 15 before GUIDE–LABEL qualification. It is
    # an upper-bound guard, not a required number of qualified candidates.
    assert 0 < max(len(frame.candidates) for frame in replay.values()) <= 15
