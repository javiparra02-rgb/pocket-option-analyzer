# dynamic_guide_label_v2 — offline experimental, F523D

## Scope and activation

`CompositeGuidePriceExtractor(enabled=True).evaluate_offline(image)` is the only
v2 entry point. Missing/false activation rejects that entry. `extract` and
`extract_with_trace` always delegate to unchanged LEGACY_V1, even on an enabled
instance. There is no live configuration, pipeline binding, OCR, H1/H2, capture,
or score-based fallback. INDEPENDENT_H1_H2_OFFLINE remains a separate contract.

## Observational evidence, not reconstructed pixels

Coordinates are original PNG/ROI coordinates, half-open, without resize. The
explicit nonnegative ROI origin permits frame coordinates by addition only.
The trace binds shape, BGR raster SHA-256 and config digest, not a path or frame ID.

DIRECT means the unchanged v1 HSV mask. COMPOSITE means an original non-mask
pixel passes the tests below. UNACCREDITED means no admitted support, **not**
absence of a visually real guide. Unknown/hidden pixels are never reconstructed.

A candidate is a gap between two original direct runs in the same thin row band.
No recursive accreditation: composite support cannot become another anchor.
Both anchors must be horizontal, share the same band, and be independently
uniform in color and adjacent background. At least one original run must meet
the v1 global hypothesis length (with the existing bounded v1 true-gap rule,
not necessarily one unbroken raw run). Its bounds are recorded separately. The
gap cannot exceed the original strong run
or the prospective 20% image-width band. Anchor width is max(4, 4*band height),
requiring more horizontal than vertical evidence; band height is at most the
existing seven-pixel candidate bound. These are experimental coverage limits,
not learned market calibration. Boundaries, other scales and negative cases
are tested; no frame-specific coordinates enter the algorithm.

For every proposed pixel C, let G be the observed direct anchor color, B its
observed adjacent background and O the background immediately above/below the
gap at the same column. Test the differential compositing relation
`C - G = beta * (O - B)` with a single coefficient across B,G,R, beta in [0.1,0.9].
It follows from two observations of the same foreground with equal opacity on
different backgrounds. No foreground color is synthesized or used as support.
The coefficient must vary by <=0.05 within a row; rows can differ (antialiasing).
Residual <=2 digital levels per channel accommodates integer raster quantization,
not arbitrary hue similarity. Backgrounds must differ by >=16 levels, and both
observed strokes must contrast with their backgrounds by >=8 levels. Upper and
lower two-row backgrounds must agree within two levels. Anchors must agree
within two levels (one edge pixel excluded for antialiasing). No extrapolation
over texture, missing context, differing anchors, empty gaps or budget exhaustion.
The entire gap band must pass; partial fits do not receive support. Every tested
region retains observed samples, anchors, fit bounds and rejection reasons.

This establishes photometric/spatial compatibility, not renderer ownership or
semantic identity by itself. Two observationally indistinguishable objects remain
a limitation; no claim of universal UI protection or recovered layer ordering.

## Two masks and unchanged downstream safeguards

The source raster and direct mask are immutable. A separate GUIDE support mask
is the disjoint union of direct and accepted composite pixels. It feeds line
proposals and exterior local GUIDE measurements only. Residual LABEL components,
label density, row metrics and centroid weights use the original direct mask.
Composite pixels never manufacture LABEL or enlarge its measured support.

Proposals -> association -> exterior GUIDE -> identity -> quality -> selection.
All v1 length, continuity, true-gap and candidate ambiguity thresholds remain
unchanged. Support counts in a v2 local GUIDE are direct+composite; its separate
trace permits their exact intersection with each selected domain. Missing pixels
remain gaps under v1 limits. No high score selects between distinct identities.
F1067's full-gap containment `top <= upper.end_y < lower.y <= bottom` is unchanged.

An offline result envelope keeps the v2 analysis, complete plan and support trace
together. Its JSON-compatible representation is separate from historical recorder
records; the v1 serializer and recorder are not modified. Persist new results in
a separate evidence namespace, never over an existing frame identity.

## Limits and historical acceptance

Budgets (4 Mpx, 4096 proposed bands) fail before partial selection. This is not a
real-time deadline. Flat-background and uniform-anchor requirements deliberately
abstain on unresolved overlap, texture, opacity changes and missing context.
No retry with relaxed thresholds, morphology fill, OCR or independent H1/H2.

The original Session06 visual expectation remains positive. F523 is evaluated
separately in explicit v2 and ordinary v1; v1 abstention is not visual absence.
Principal explicitly authorized the version split on 2026-10-28 after reviewing
the subpixel discrepancy: historical y=265.4985835694051 remains a positive
reference in the independently observed rows 265–266, not an independently
certified decimal centroid. `test_session06_f523_v2_positive_raster_identity_and_exact_centroid`
requires the complete identity chain and computes the exact output centroid from
original direct-mask row counts in the selected window. Composite pixels do not
change centroid weights or historical v1 metrics. V2's output is 265.4825174825175
on the known original. This is not an arbitrary expanded numerical tolerance.
The separate v1 compatibility test records abstention without negating visual
presence; the other thirteen Session06 v1 positive expectations remain unchanged.
No frame/oracle value enters the product. ZIP loading uses original hashed bytes,
not a substitute fixture, and missing Session06 evidence fails this gate.

The complete v2 envelope, including `plan` and `support`, is the auditable result;
do not persist its analysis alone as if it were a fully evidenced v1 record.
The envelope can be serialized deterministically with `to_dict()`; this task
does not wire it into the recorder or live consumers. `price.source` is the v2
contract while the ordinary methods retain the historical v1 source.
