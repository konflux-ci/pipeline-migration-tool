FROM registry.access.redhat.com/ubi10/python-312-minimal:10.2-1790171185@sha256:318c7712f8334c7148719d0025a969b984c92f790b1d444baadb53c0433987c4 AS base
USER root
COPY requirements.txt requirements-build.txt ./
RUN python3.12 -m venv /venv && \
    /venv/bin/pip install -r requirements-build.txt --no-deps --no-cache-dir --require-hashes && \
    /venv/bin/pip install -r requirements.txt --no-deps --no-cache-dir --require-hashes
COPY . .
RUN /venv/bin/pip install --no-cache-dir .

FROM registry.access.redhat.com/ubi10/python-312-minimal:10.2-1790171185@sha256:318c7712f8334c7148719d0025a969b984c92f790b1d444baadb53c0433987c4
LABEL maintainer="Red Hat"
LABEL io.k8s.display-name="pipeline-migration-tool"
LABEL io.openshift.tags="konflux, pipeline-migration-tool, cli"
LABEL summary="pipeline-migration-tool"
LABEL name="pipeline-migration-tool"
LABEL com.redhat.component="pipeline-migration-tool"

COPY --from=base /venv /venv
USER root
RUN ln -s /venv/bin/pipeline-migration-tool /usr/local/bin/pipeline-migration-tool

USER 1001

ENTRYPOINT [ "/usr/local/bin/pipeline-migration-tool" ]
