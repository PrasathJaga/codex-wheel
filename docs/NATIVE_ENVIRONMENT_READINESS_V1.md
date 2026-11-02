# Native environment readiness — blocked result, 2 November 2026

**The desired native-build/test result was not achieved. Neither baseline has
been executed.** This is a dependency-admission report, not a successful native
build, an application failure, an unfamiliar evaluation or a Meta finding.

The source candidates and their original direction remain unchanged. The
comparison registry is still empty. No dependency version was upgraded, native
test removed, source distribution built, network restriction bypassed or new paid
call made. The earlier real generic Meta integration results are unaffected.

## Concrete results

| Candidate | Readiness result | Evidence / remaining gap |
| --- | --- | --- |
| Spring Java record refactor | Blocked before native execution | Root `complete`, Java 17/Spring Boot parent 3.0.0, native Maven web/test/plugin graph needs a complete reviewed environment |
| Historical httpbin Python fix | Blocked through current wheel-only path | Exact requirements include six releases with no wheel in the retrieved PyPI metadata snapshot |

The six releases are:

- decorator 3.4.0
- Flask 0.10.1
- itsdangerous 0.24
- Jinja2 2.7.2
- MarkupSafe 0.23
- Werkzeug 0.9.4

The recorded PyPI endpoints, filenames, package types, sizes, hashes and URLs are
in `evaluation/native_readiness_v1/python-release-evidence.json`. Primary examples:
https://pypi.org/pypi/Flask/0.10.1/json and
https://pypi.org/pypi/MarkupSafe/0.23/json . Observations are a 2 November 2026
snapshot, not a guarantee of all future artifact availability. Metadata was fetched
without credentials; package files were not downloaded, unpacked or executed.
The response digest is recorded; the committed snapshot retains the artifact facts
used by the analysis rather than the complete PyPI description/response body.

Some other pins have wheels, but their runtime/platform compatibility and complete
transitive closure have **not** been established. The report does not infer that
having a wheel means Python 3.12 compatibility. This snapshot declares Python
2.7/3.4 compatibility upstream; that is not evidence it runs on today's approved
images. A reviewed preinstalled environment or isolated source-build capability
could be a separate route, but neither has been prepared here.

## Actual framework gaps

The existing dependency acquisition path accepts explicitly reviewed wheel and
Maven artifact files, at most 64 artifacts/32 MiB. The offline executor can consume
a verified bundle. That is not a resolver or a complete framework environment.

1. Maven parent/BOM inheritance, transitive dependencies, build plugins, test
   runtime and writable local-cache requirements are not resolved automatically.
   Literal POM inspection cannot establish the complete native environment.
2. The dependency-bundle consumption capability is connected to offline build/test
   execution, not the shared HTTP service lifecycle. A working test-only bundle
   would not silently make the application runtime complete.
3. The current Python acquisition policy rejects source distributions. Building
   these exact old releases would require a separately reviewed, versioned build
   environment and build dependencies; installing latest packages is not the same
   source/environment task.

These are limitations of Wheel's current onboarding, **not proof that Spring or
httpbin themselves are broken**. We did not run a known-missing-dependency command
merely to obtain a predictable failure and call that native validation. No native
JUnit/unittest pass is claimed. A green readiness-unit workflow only verifies the
analysis and preserved blocked result.

## Reproducible readiness analysis

`evaluation.native_readiness_v1.qualify` reads authenticated source archives and a
separate profile. The same shape supports Java and Python roots without a project
name or business-specific branch in the analyzer:

- `schema=wheel-native-readiness-profile-v1`;
- `language`, `root`, `dependency_manifest`;
- `native_tests`: unchanged command arrays/timeouts describing the checks still
  required, never commands executed by this module.

Profiles choose `complete/pom.xml` and the actual Maven verify command for Spring,
and root `requirements.txt` with native unittest discovery for httpbin. Profiles
and source descriptor hashes bind each report. Release metadata is bound to the
exact requirements bytes. Literal requirements ranges/options/URLs or conflicting
pins are rejected rather than guessed. XML declarations are rejected; inherited
versions remain unknown instead of being invented.

`*-readiness.json` files contain `desired_native_pass_achieved=false`,
`baseline_executed=false`, exact observed evidence and separate blockers. Replay
using `WHEEL_EXTERNAL_INTAKE_DIR` pointed at the four authenticated source archives:

```bash
WHEEL_EXTERNAL_INTAKE_DIR=/path/to/archives \
  python -m unittest discover -s preflight_tests -p test_native_readiness.py -v
```

No SDK, Docker, pip/Maven, native project import or application request is made.
All existing frozen investigator/comparison code and prior results remain unchanged.
External code receives neither Wheel source nor project credentials.

## Next decision and engineering gate

The dependent unfamiliar comparison is stopped at environment readiness. Required
work is a general reviewed framework-environment capability: complete Maven cache
qualification and offline runtime consumption; and, if supporting these exact
legacy Python pins, a reviewed compatible environment or bounded source-build
path. Those capabilities need their own protocol/version, negative controls and
live tests before an evaluation can rely on them. Do not silently broaden limits,
allow unrestricted build egress or modify a frozen investigation after exposure.

It is also valid to screen another repository against the declared supported scope
before registration, retaining this unsupported candidate in the intake record.
That would not demonstrate support for these legacy projects, and must not be
presented as an unfamiliar success on the first candidate inspected. Any new
candidate still requires native baseline evidence and actual provenance review.

The current step therefore establishes an honest **blocked** qualification result.
It does not complete native execution or the external evaluation. Further paid
investigation is unjustified until the environment gate is satisfied.
