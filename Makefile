PYTHON_IMAGE := mirror.gcr.io/library/python:3.12-alpine
CONTAINER_WORKDIR := /pmt

# NOTE: $(1) is forwarded to uv (e.g. --upgrade)
define uv-pip-compile
	podman run --rm \
		--volume "$(CURDIR):$(CONTAINER_WORKDIR):rw,Z" \
		--workdir "$(CONTAINER_WORKDIR)" \
		$(PYTHON_IMAGE) \
		sh -c ' \
			pip install uv && \
			uv pip compile --generate-hashes --output-file=requirements.txt --python=3.12 $(1) pyproject.toml && \
			uv pip compile --extra=test --generate-hashes --output-file=requirements-test.txt --python=3.12 $(1) pyproject.toml && \
			uv pip compile --generate-hashes --output-file=requirements-build.txt --python=3.12 $(1) requirements-build.in \
		'
endef

.PHONY: deps/compile deps/upgrade

deps/compile:
	$(call uv-pip-compile)

deps/upgrade:
	$(call uv-pip-compile, --upgrade)


.PHONY: venv/create venv/remove venv/recreate

venv/create:
	python3 -m venv --upgrade-deps .venv
	.venv/bin/python3 -m pip install -r requirements-test.txt
	.venv/bin/python3 -m pip install pip-tools

venv/remove:
	rm -rf .venv

venv/recreate: venv/remove venv/create
