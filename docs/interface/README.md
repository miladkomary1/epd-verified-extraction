# Interface screenshots

A reference implementation of this workflow is deployed as a web application. **It is
not part of this repository, it is not open source, and nothing here depends on it.**
These screenshots exist so that the workflow can be seen running end to end rather than
taken on trust.

They were captured from a local instance with the model fixed to the one the paper
evaluates. The deployment now reaches a newer model by default, and on the declaration
below the two do not fail in the same place, which is itself the reason the workflow
puts its trust in the checks rather than in the model.

| File | What it shows |
|---|---|
| `exampleA_clean.png` | A tile-adhesive declaration read by the deterministic parser alone: 208 values surfaced, none withheld. |
| `exampleB_withheld.png` | The same interface on a declaration where the model misreads an exponent: 201 surfaced, 7 withheld. |
| `cascade.png` | The recommended configuration, parser first and model for the gaps, on the same declaration: 205 surfaced, 3 withheld. |
| `registry_record.png` | A registry record read by identifier and screened against the same arithmetic identities. |
| `export_options.png` | The export controls. Only the registry column layout is evaluated in the paper. |
| `upload_and_engines.png` | The document and engine selection step. |
| `disclaimer.png` | The acknowledgement shown before any result is displayed. |

## The example worth looking at

In `exampleB_withheld.png` the global warming potential for module A4 is struck through
and marked as not locatable in the document text. The declaration prints `1.8E-01`; the
model returned `0.00018`. No rendering of the emitted number occurs anywhere in the
source, so the grounding check withholds it instead of reporting it.

The renewable primary energy entries for module A5 fail for a different reason. The
declaration itself gives 26.6 and -26.4 against a stated total of 0.185, which do not
sum, so the additivity identity fails on the document's own numbers rather than on the
reading of them.

`cascade.png` is the same declaration under the recommended configuration. The count
moves to 205 surfaced and 3 withheld, because the deterministic parser reads the four
module A4 entries exactly where the model misread them. What stays withheld is the
inconsistency in the document, which no engine can resolve.
