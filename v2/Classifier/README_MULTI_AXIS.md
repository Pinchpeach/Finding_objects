# Classifier target structure

```
Classifier/
├── 01_prepare_input.py
├── control.py                 # existing validated pipeline controller
├── control_axes.py            # multi-axis orchestration
├── architecture/
│   └── README.md
├── axes/
│   ├── physical.py            # WD / RGB / AGB / ...
│   ├── variability.py         # RR Lyrae / Cepheid / Mira / ...
│   ├── compact.py             # NS / pulsar / XRB / ...
│   ├── extragalactic.py       # galaxy / AGN / QSO / ...
│   └── phenomenon.py          # SN / PN / nova / ...
└── existing WD training, validation and Gaia-XP files
```

WD is one validated branch, not the whole classifier. Existing WD files are kept
unchanged while their validated inference is progressively wired into
`axes/physical.py`. Other axes remain explicit UNKNOWN/NOT_IMPLEMENTED until
their evidence models are scientifically validated; placeholder probabilities are
not generated.
