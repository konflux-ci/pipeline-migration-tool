# How migration discovery should work

Let's look at an example task that has had multiple versions and migrations.

```text
task/source-build
├── 0.2
│   ├── migrations
│   │   │── 0.2.sh
│   │   └── 0.2.1.sh
│   └── source-build.yaml   <- has app.kubernetes.io/version: "0.2.1"
└── 0.3
    ├── migrations
    │   │── 0.3.sh
    │   └── 0.3.1.sh
    └── source-build.yaml   <- has app.kubernetes.io/version: "0.3.1"
```

* We build both versions of `task/source-build`.
* When building `task/source-build/0.2`, we look at the version label and see `0.2.1`.
  * We attach `migrations/0.2.1.sh`
  * We tag it with `:0.2.1` and `:0.2.1-{timestamp or git_sha or something unique}`
* Same for `task/source-build/0.3`, but with `0.3.1`

Let's say we've been doing it this way for a while and have released all the versions
(`0.2`, `0.2.1`, `0.3`, `0.3.1`) a couple times. In the registry, the situation may
look something like this:

```text
quay.io/konflux-ci/tekton-catalog/task-source-build

  "the 0.2 branch"                          "the 0.3 branch"

      0.2.1-c   <- migrations/0.2.1.sh
        |                                       0.3.1-b     <- migrations/0.3.1.sh
        |                                         |
        |                                       0.3.1-a     <- migrations/0.3.1.sh
      0.2.1-b   <- migrations/0.2.1.sh            |
        |                                         |
      0.2.1-a   <- migrations/0.2.1.sh            |
        |                                        0.3-b      <- migrations/0.3.sh
        |                                         |
        |                                        0.3-a      <- migrations/0.3.sh
       0.2-b    <- migrations/0.2.sh
        |
       0.2-a    <- migrations/0.2.sh
```

*In reality, this would be a single linear timeline of tags. It's split in
two "branches" here for easier visualization.*

When MintMaker updates a user's pipeline from `task-source-build:0.2` to
`task-source-build:0.3.1`, we discover the migrations as follows:

* List all tags for `quay.io/konflux-ci/tekton-catalog/task-source-build`
* Sort and group them by version:
  * `[[0.2-a, 0.2-b], [0.2.1-a, 0.2.1-b, 0.2.1-c], [0.3-a, 0.3-b], [0.3.1-a, 0.3.1-b]]`
* For each version `>0.2, <=0.3.1`, pick an arbitrary tag from its group and download
  the attached migration script
* Done

Why is picking an arbitrary tag okay? Because the migration script for a specific
version is not allowed to change. We have a [CI check] for that. The CI check will
need to be shared across all Task repos - we have [task-repo-shared-ci] for that
(work in progress).

But in the unfortunate case that someone isn't using the CI check and is changing
migration scripts in place, we should pick the *newest* tag from each version group.
That's probably what the migration author intended, even if it may not behave the
way they intended (because the user may have already merged the `x.y` update so
the updated `migrations/x.y.sh` will never get applied).

[CI check]: https://github.com/konflux-ci/build-definitions/blob/705f90a647cf1ac4cf4703ef85fe3d0ad90a6e1e/hack/validate-migration.sh#L318-L321
[task-repo-shared-ci]: https://github.com/konflux-ci/task-repo-shared-ci
