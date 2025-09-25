from os import PathLike
from typing import TypedDict, NotRequired

FilePath = PathLike[str] | str

AnnotationsT = dict[str, str]


class DescriptorT(TypedDict):
    mediaType: str
    digest: str
    size: int
    annotations: NotRequired[AnnotationsT]
    artifactType: NotRequired[str]
    data: NotRequired[str]


class ImageIndexT(TypedDict):
    schemaVersion: int
    mediaType: str
    manifests: list[DescriptorT]
    annotations: NotRequired[AnnotationsT]


class ManifestT(TypedDict):
    schemaVersion: int
    mediaType: str
    config: DescriptorT
    layers: list[DescriptorT]
    annotations: NotRequired[AnnotationsT]
