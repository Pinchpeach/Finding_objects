# Multi-axis Classifier Architecture

The classifier is not a single mutually-exclusive label tree. It runs independent
axes so one source may be, for example, an AGB star and a Mira variable.

Axes:
- physical: stellar evolutionary/physical state (WD, RGB, AGB, ...)
- variability: variable-star behaviour/subtype
- compact: NS/pulsar and other compact-object evidence
- extragalactic: galaxy/AGN/QSO refinements
- phenomenon: transient/nebular phenomena (SN, PN, nova, ...)

Every branch must preserve evidence, uncertainty and an abstain/unknown state.
Missing observations are masked, never treated as negative evidence. Validated
WD/DA-DB code remains available and is routed through the physical branch.
