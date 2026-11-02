# First public-source candidate intake — 2 November 2026

This is read-only intake after the frozen transfer protocol in PR56. It pins real
upstream changes and establishes reproducible source identities. **Neither pair
is registered for execution; no project build/test, Meta call, independent review
or unfamiliar benchmark has occurred.** The sources were selected and inspected
by the Codex assistant after the protocol freeze. Historical outcomes are public
and already known. Do not call this independent/blind case preparation.

## Pinned candidates

| Candidate | Original change | Parent → candidate | Current disposition |
| --- | --- | --- | --- |
| Java: Spring REST guide | Maintainer replaces `Greeting` class with Java record | `9ed28134892e3218e518fd98f76dcc128af916dc` → `e03c1e1564715197d3ccaf383f10e7fcebbf2de2` | Source verified; possible preserving refactor, not runtime-verified |
| Python: httpbin #330 | Contributor fixes invalid status-code handling | `a22fc1fb65adf8dda9888663a7e778e58c9b83e6` → `3fe84ea4760172f2ce2fde709127c3814fa0e88f` | Source verified; historical fix, baseline direction and legacy environment unresolved |

Primary provenance:

- https://github.com/spring-guides/gs-rest-service/commit/e03c1e1564715197d3ccaf383f10e7fcebbf2de2
- https://github.com/postmanlabs/httpbin/pull/330
- https://github.com/postmanlabs/httpbin/commit/3fe84ea4760172f2ce2fde709127c3814fa0e88f

The source descriptors commit exact public codeload URLs, revisions, compressed
sizes/SHA256 values, archive roots, upstream author login, original reference and
complete GitHub changed-path list. Reports reconstruct the full source inventories
and compare actual changed paths against that list. All four archives passed the
existing bounded regular-file collector. Spring has 37 files per revision; httpbin
has 31 per revision. Hash binding proves byte identity against the descriptor,
not independent review, source authenticity by signature or runtime correctness.
The operator obtained the descriptor metadata from the primary GitHub APIs.

Source archives are fetched only from public GitHub, with no auth header. They
are read as data, never installed, imported or executed. Reports contain source
identities/discovery facts, not an executable environment or hidden chosen plan.
No source archive is bundled into the Wheel repository. No Wheel code or
credentials are sent to upstream repositories; no fork, push, issue or outreach
has been made there.

## Actual gaps, not assumptions

**Java.** The selected `complete` sample declares Spring Boot 3.0.0, Java 17,
web/test starters and the Spring Boot Maven plugin. Its native JUnit test path is
`complete/src/test/java/com/example/restservice/GreetingControllerTests.java`.
The commit changes only README and Greeting source. A preserving API prediction
must be checked against the guide's declared representation and actual execution;
the record refactor is not automatically healthy because it looks equivalent.
The complete reviewed Maven dependency/plugin environment has not been locked or
executed. Do not use syntax-only checks in place of these native tests.

**Python.** The historical snapshot declares Python 2.7/3.4 classifiers and pins
Flask 0.10.1, gevent 1.0.2 and related legacy packages. Compatibility with any
approved modern runtime is unverified. The fix modifies `httpbin/core.py`, README
and `test_httpbin.py`, adding invalid-input tests. Preserve that test difference;
do not claim a common unchanged test suite or a JUnit-like coverage gap here.

The original pair direction is parent-to-fix. Under an expectation describing the
fixed invalid-input behavior, the old baseline may be invalid. That must stop the
comparison. Do not quietly swap revisions, relax the expectation or cherry-pick
input to manufacture a healthy baseline. A separately declared rollback/fault
replay could be useful engineering evidence, but it would be a retrospective
known-fault task requiring its own explicit review—not a newly found regression
or the original upstream PR direction. No such replay is registered here.

Both candidates still require reviewed runtime/dependency inputs, native build/test
execution, approved source-derived HTTP expectations and external adapter/provenance
review before frozen transfer admission. Neither has a selected conventional or
model experiment. Their `comparison_eligible=false` reports are intentional.

## Rejected candidates are retained

`evaluation/external_intake_v1/catalog.json` also records:

- Bottle #1226: `Allow` header change. Frozen checker lacks header predicates.
- Bottle #1454: exception attachment on malformed JSON. Frozen request schema
  produces valid structured JSON; no arbitrary malformed-body or exception tool.
- NanoHTTPD #525: stream cleanup after send failures. Requires unsupported
  transport fault/resource observation.

These were static suitability rejections, not execution failures. No investigator
prompt, request alias, checker predicate or runtime capability was added after
reading those defects. Keep them in the denominator of candidate-screening work;
do not present a successful candidate as the first one inspected.

## Reproduce intake without execution

Download each exact URL in its `*-source.json` descriptor to a new local archive
file, then run:

```bash
python -m evaluation.external_intake_v1.intake \
  --descriptor evaluation/external_intake_v1/spring_record_refactor-source.json \
  --baseline /path/to/spring_record_refactor-baseline.tar.gz \
  --candidate /path/to/spring_record_refactor-candidate.tar.gz \
  --output /tmp/new-spring-intake.json
```

The output must be new. The CLI rejects changed hashes/sizes/URLs, unsafe archives
and any undeclared changed path. No model client, subprocess, package manager or
project module is invoked. `WHEEL_EXTERNAL_INTAKE_DIR` enables exact source-report
replay in the focused tests. CI downloads the four immutable revision archives,
checks their committed hashes and replays the reports with no Docker or secrets.
Retrieval/integrity failure is retained as a failed CI check, not retried to obtain
a favorable report.

## Review packet for another developer

An independent developer does not need Wheel source or project credentials. Give
them only the source descriptors/upstream links, these factual intake reports and
the public case-format/tool-interface specification. Ask them to:

1. Check actual upstream provenance, pair direction and prior outcome knowledge.
2. Supply/review a complete reproducible environment and native test commands
   without skipping/weaking tests or updating dependencies just to pass.
3. Approve intended API behavior from attributable project documentation/tests,
   distinguishing intended changes from regressions; leave unclear behavior unknown.
4. Prepare a source-aware conventional proposal against the same reviewed context
   and typed interface, with preparation kind and measured/unknown effort disclosed.
5. Review the assembled case hashes and retained labels/provenance before execution.

The operator then assembles the packet using the unchanged frozen admission path;
only after the full Java/Python batch and actual separate review are committed
may a concrete bounded launch proceed. Merely copying a person's upstream login
into a review record is not approval of our adapter or case. No reviewer has been
invented or contacted, and the frozen registry remains empty.

Next engineering gate is runtime/environment readiness and real independent review.
If either candidate cannot fit the frozen process, retain its unsupported outcome
and declare any future broader capability as a separate version. No judging score,
production impact, unfamiliar discovery or Meta superiority follows from intake.
