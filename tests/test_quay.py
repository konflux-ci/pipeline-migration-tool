import pytest
import requests
import responses

from pipeline_migration.registry import HTTP_TIMEOUT, Container
from pipeline_migration.quay import list_active_repo_tags


class TestListActiveRepoTags:

    @responses.activate
    def test_list_activate_repo_tags(self):
        repository = "quay.io/ns/app"
        tags = [{"name": "tag1"}, {"name": "tag2"}]

        responses.add(
            responses.GET,
            "https://quay.io/api/v1/repository/ns/app/tag/?page=1&onlyActiveTags=true",
            json={"tags": tags, "page": 1, "has_additional": False},
        )

        got = list_active_repo_tags(Container(repository))
        assert list(got) == tags

    @responses.activate
    def test_pagination(self):
        repository = "quay.io/ns/app"
        tags_page_1 = [{"name": f"tag{i}"} for i in range(5)]
        tags_page_2 = [{"name": "tag7"}, {"name": "tag8"}, {"name": "tag9"}]

        api_url = "https://quay.io/api/v1/repository/ns/app/tag/"

        responses.get(
            f"{api_url}?page=1&onlyActiveTags=true",
            json={"tags": tags_page_1, "page": 1, "has_additional": True},
        )
        responses.get(
            f"{api_url}?page=2&onlyActiveTags=true",
            json={"tags": tags_page_2, "page": 2, "has_additional": False},
        )

        got = list_active_repo_tags(Container(repository))
        expected = tags_page_1[:]
        expected.extend(tags_page_2)
        assert list(got) == expected

    @responses.activate
    def test_request_has_timeout(self):
        responses.get(
            "https://quay.io/api/v1/repository/ns/app/tag/?page=1&onlyActiveTags=true",
            json={"tags": [], "page": 1, "has_additional": False},
        )

        list(list_active_repo_tags(Container("quay.io/ns/app")))
        assert responses.calls[0].request.req_kwargs["timeout"] == HTTP_TIMEOUT

    @responses.activate
    def test_raise_timeout_error(self):
        responses.get(
            "https://quay.io/api/v1/repository/ns/app/tag/?page=1&onlyActiveTags=true",
            body=requests.exceptions.ReadTimeout("read timed out"),
        )

        with pytest.raises(requests.exceptions.ReadTimeout):
            list(list_active_repo_tags(Container("quay.io/ns/app")))
