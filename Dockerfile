FROM quay.io/konflux-ci/rust-builder:1.94.1@sha256:8e84d5507f664cd2d3c6dfa1ad5ac33c3fd13480d6571c4ec1b9c3d26a28f0bc AS rust-builder
# need to use ubi9 images as rust needs gcc and ubi9 has it installed
FROM registry.access.redhat.com/ubi9/python-312:latest@sha256:56fad467cb1e41666f0028b7fd71107df0556bcc9ecfc577597858c85618f55c AS base
USER 0
WORKDIR /src
COPY requirements.txt requirements-build.txt ./
COPY --from=rust-builder /usr/local/share/rust /usr/local/share/rust
ENV PATH="/usr/local/share/rust/bin:${PATH}"

# Use pip from the base image to install the requirements.
# The bundled pip is older than the one in the base image and does not include this:
# https://github.com/pypa/pip/pull/12449
# So the build fails with missing wheel package when installing oras from requirements.txt which does
# not have `build-system` metadata in pyproject.toml.
RUN python3.12 -m venv --without-pip /venv && pip --python=/venv/bin/python install --no-cache-dir -r requirements.txt
COPY . .
RUN pip --python=/venv/bin/python install --no-cache-dir .

##########################
# GENERATE RELEASE ARTIFACTS (sdist, wheel, checksums, manifest) FROM SOURCE
# Version is read from src/pipeline_migration/__init__.py.
# This only builds the installable sdist/wheel artifacts
##########################
FROM registry.access.redhat.com/ubi9/python-312-minimal:9.8@sha256:a3a5cfe0c6738de28a6fa8f8cb61c16491605dd6786905c8984b79385c353783 AS package
USER 0
COPY --from=base /venv /venv
WORKDIR /src
COPY . .
RUN pip --python=/venv/bin/python install --no-cache-dir -r requirements-extras.txt
RUN mkdir -p /out && /venv/bin/python hack/build_release_artifacts.py /out

##########################
# RELEASE IMAGE
# Based on ubi9-minimal to satisfy Conforma gate
##########################
FROM registry.access.redhat.com/ubi9/ubi-minimal:9.8-1791279563@sha256:5ed244b62bbf4095080144d9d35eb8fcd3d39a9801f94aadd63b9d10978a01ae AS release
LABEL maintainer="Red Hat"
LABEL io.k8s.display-name="pipeline-migration-tool-release"
LABEL io.openshift.tags="konflux, pipeline-migration-tool, cli"
LABEL summary="pipeline-migration-tool"
LABEL description="Release artifacts (sdist, wheel, checksums, manifest) for pipeline-migration-tool"
LABEL name="pipeline-migration-tool-release"
LABEL com.redhat.component="pipeline-migration-tool"
LABEL vendor="Red Hat, Inc."
LABEL release="1"
COPY LICENSE /licenses/LICENSE
COPY --from=package --chown=1001:0 /out/* /releases/
USER 1001

##########################
# ASSEMBLE THE FINAL (SLIM) IMAGE
##########################
FROM registry.access.redhat.com/ubi9/python-312-minimal:9.8@sha256:a3a5cfe0c6738de28a6fa8f8cb61c16491605dd6786905c8984b79385c353783 AS runtime
LABEL maintainer="Red Hat"
LABEL io.k8s.display-name="pipeline-migration-tool"
LABEL io.openshift.tags="konflux, pipeline-migration-tool, cli"
LABEL summary="pipeline-migration-tool"
LABEL name="pipeline-migration-tool"
LABEL com.redhat.component="pipeline-migration-tool"

COPY --from=base /venv /venv
USER 0
RUN ln -s /venv/bin/pipeline-migration-tool /usr/local/bin/pipeline-migration-tool

USER 1001

ENTRYPOINT [ "/usr/local/bin/pipeline-migration-tool" ]
