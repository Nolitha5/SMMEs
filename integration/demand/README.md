# Florah Demand integration

Pinned source: `Nolitha5/SMMEs`, branch `Florah`, commit
`e3534ef9ebc94460328a07bd45bedcec03cee956`.

The real D1-D5 implementation is copied under `vendor/florah-demand/` by the
apply script. The shared platform does not rewrite those algorithms.

Production boundary:

`D1 -> D2/D3 -> D4 -> florah_adapter.py -> canonical DemandForecast -> agentOutputs/agentState`

D5 remains Demand's quality-feedback capability. Internal Florah events remain
inside the Demand domain; cross-domain routing uses the shared platform events.

Florah's standalone Firebase configuration and Demand-specific persistence are
not treated as the shared production database. The shared Firebase project and
business-scoped exchange layer remain authoritative for cross-domain outputs.
