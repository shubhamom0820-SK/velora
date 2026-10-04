"""Sightengine, real and fake (T-4.4, D-094).

The real client talks to `httpx.MockTransport` here: no test reaches
Sightengine. What a real answer looks like was checked once, for real, by
`app/tools/sightengine_shape.py` (its date and the shape seen are on T-4.4);
these tests hold the client to what that check and the documentation say.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.providers import moderation
from app.core.providers.moderation import (
    CHECK_URL,
    CHECKED_ANSWER,
    KNOWN_FIELDS,
    MODELS,
    NUDITY_CLASSES,
    FakeModeration,
    ModerationFailed,
    Scores,
    SightengineModeration,
    fake_answer,
    field_paths,
    parse_check,
)
from app.modules.photos import moderation as rules
from app.tools.sightengine_shape import differences, shape
from tests.conftest import CapturedLogs

USER, SECRET = "api-user-for-tests", "api-secret-for-tests"
JPEG = b"\xff\xd8\xff\xe0 a re-encoded photo \xff\xd9"


def _client(
    answer: Callable[[httpx.Request], httpx.Response], seen: list[httpx.Request]
) -> SightengineModeration:
    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        seen.append(request)
        return answer(request)

    return SightengineModeration(USER, SECRET, transport=httpx.MockTransport(handler))


def _ok(body: Any = CHECKED_ANSWER) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _: httpx.Response(200, content=json.dumps(body).encode())


def _form(request: httpx.Request) -> dict[str, Any]:
    """The multipart body's fields: text fields by value, files by name."""
    content_type = request.headers["content-type"]
    boundary = content_type.split("boundary=")[1].encode()
    fields: dict[str, Any] = {}
    for part in request.content.split(b"--" + boundary)[1:-1]:
        head, _, body = part.strip(b"\r\n").partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        if b"filename=" in head:
            fields[name] = ("file", body)
        else:
            fields[name] = body.decode()
    return fields


# --- Reading an answer -------------------------------------------------------------


def test_the_checked_answer_reads_as_its_scores() -> None:
    scores = parse_check(json.dumps(CHECKED_ANSWER))

    assert scores == Scores(
        nudity={
            "sexual_activity": 0.01,
            "sexual_display": 0.01,
            "erotica": 0.01,
            "very_suggestive": 0.01,
        },
        minors=(0.01,),
        artificial_faces=0,
        text_artificial=0.01,
    )


def test_the_reader_reads_exactly_the_classes_the_decision_uses() -> None:
    assert NUDITY_CLASSES == rules.EXPLICIT


def _without(path: list[str]) -> dict[str, Any]:
    answer = copy.deepcopy(dict(CHECKED_ANSWER))
    target = answer
    for step in path[:-1]:
        target = target[step]
    del target[path[-1]]
    return answer


def _replaced(path: list[Any], value: Any) -> dict[str, Any]:
    answer = copy.deepcopy(dict(CHECKED_ANSWER))
    target = answer
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return answer


@pytest.mark.parametrize(
    "answer",
    [
        _without(["nudity", "erotica"]),
        _without(["faces"]),
        _without(["text", "has_artificial"]),
        _replaced(["faces", 0, "attributes"], {"minor": 0.01}),  # face-attributes'
        _replaced(["nudity", "sexual_display"], "0.97"),
        _replaced(["status"], "partial"),
    ],
    ids=[
        "a nudity class missing",
        "no faces list",
        "no embedded-text score",
        "the deprecated model's minor field",
        "a score as a string",
        "an unknown status",
    ],
)
def test_an_answer_in_any_other_shape_fails_loudly_never_reads_as_zero(
    answer: dict[str, Any],
) -> None:
    """A field renamed, moved or retyped must stop the photo, never pass it as
    if the score were 0: the reason D-094 compares shapes."""
    with pytest.raises(ModerationFailed, match="shape this module doesn't know"):
        parse_check(json.dumps(answer))


def test_sightengines_own_refusal_is_named_by_its_type_and_code() -> None:
    refusal = {
        "status": "failure",
        "request": {"id": "req_x", "timestamp": 1.0, "operations": 0},
        "error": {
            "type": "argument_error",
            "code": 1,
            "message": "Incorrect API user or API secret",
        },
    }

    with pytest.raises(ModerationFailed, match=r"refused: argument_error \(1\)"):
        parse_check(json.dumps(refusal))


# --- The real client ----------------------------------------------------------------


async def test_a_check_is_one_post_of_the_image_with_three_models() -> None:
    seen: list[httpx.Request] = []
    client = _client(_ok(), seen)

    scores = await client.check(JPEG)

    assert scores.minors == (0.01,)
    [request] = seen
    assert (request.method, str(request.url)) == ("POST", CHECK_URL)
    assert _form(request) == {
        "models": "nudity-2.1,face-age,text",
        "api_user": USER,
        "api_secret": SECRET,
        "media": ("file", JPEG),
    }
    await client.aclose()


@pytest.mark.parametrize(
    "outcome", ["approve", "nudity", "minor_suspected", "no_face", "text_overlay"]
)
async def test_every_request_stays_on_the_plain_image_api(outcome: str) -> None:
    """T-4.4's constraint, and /privacy's truth (D-048): only `check.json`,
    only the models, the keys and the image. Nothing that turns on human
    review (a workflow), the Feedback API, the Upload API or a list, each of
    which keeps the file at Sightengine. Adding any fails here first."""
    seen: list[httpx.Request] = []
    client = _client(_ok(fake_answer(outcome)), seen)  # type: ignore[arg-type]

    for _ in range(3):
        await client.check(JPEG)

    for request in seen:
        assert request.url.host == "api.sightengine.com"
        assert request.url.path == "/1.0/check.json"
        assert request.url.query == b""  # nothing rides in the URL, keys least of all
        assert set(_form(request)) == {"models", "api_user", "api_secret", "media"}
        assert _form(request)["models"].split(",") == list(MODELS)
    await client.aclose()


@pytest.mark.parametrize(
    ("answer", "says"),
    [
        (lambda _: httpx.Response(500, content=b"oops"), "answered 500"),
        (
            lambda _: httpx.Response(
                401,
                content=json.dumps(
                    {"status": "failure", "error": {"type": "auth", "code": 1}}
                ).encode(),
            ),
            r"answered 401: Sightengine refused: auth \(1\)",
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectTimeout("slow", request=request)
            ),
            r"no answer from Sightengine \(ConnectTimeout\)",
        ),
        (lambda _: httpx.Response(200, content=b"<html>"), "doesn't know"),
    ],
    ids=["a 5xx", "a refusal", "a timeout", "not json"],
)
async def test_a_failure_is_moderation_failed_naming_only_its_kind(
    answer: Callable[[httpx.Request], httpx.Response], says: str
) -> None:
    seen: list[httpx.Request] = []
    client = _client(answer, seen)

    with pytest.raises(ModerationFailed, match=says) as failure:
        await client.check(JPEG)
    assert SECRET not in str(failure.value)
    assert USER not in str(failure.value)
    await client.aclose()


def test_building_it_opens_no_connection() -> None:
    """The API builds every provider and never moderates."""
    client = SightengineModeration(USER, SECRET)

    assert client._client is None


# --- The fake -----------------------------------------------------------------------


async def test_the_fake_answers_in_the_documented_shape_through_the_same_reader() -> (
    None
):
    fake = FakeModeration()

    assert await fake.check(b"a") == parse_check(json.dumps(CHECKED_ANSWER))
    assert fake.checked == [b"a"]


@pytest.mark.parametrize(
    ("outcome", "check"),
    [
        ("reject:nudity", lambda s: s.nudity["sexual_display"] == 0.97),
        ("reject:minor_suspected", lambda s: s.minors == (0.93,)),
        ("reject:no_face", lambda s: s.minors == ()),
        ("reject:text_overlay", lambda s: s.text_artificial == 0.99932),
    ],
)
async def test_the_fake_scores_each_reason_once(
    outcome: str, check: Callable[[Scores], bool]
) -> None:
    fake = FakeModeration()
    fake.next = outcome

    assert check(await fake.check(b"a"))
    assert await fake.check(b"b") == parse_check(json.dumps(CHECKED_ANSWER))


async def test_the_fake_fails_once_when_told() -> None:
    fake = FakeModeration()
    fake.next = "fail"

    with pytest.raises(ModerationFailed):
        await fake.check(b"a")
    assert (await fake.check(b"b")).minors == (0.01,)


@pytest.mark.parametrize("outcome", ["reject:blurry", "reject:other", "maybe"])
async def test_the_fake_refuses_an_outcome_no_score_gives(outcome: str) -> None:
    fake = FakeModeration()
    fake.next = outcome

    with pytest.raises(ValueError, match=f"not {outcome!r}"):
        await fake.check(b"a")


# --- D-094's real check, and what it found ---------------------------------------------


def test_an_answer_with_no_text_has_no_boxes_as_real_answers_do() -> None:
    """Found by D-094's real check, 4 October 2026: the documentation shows
    `boxes: []`, Sightengine sends no `boxes` at all. A reader that required
    them refused every ordinary photo."""
    assert "boxes" not in CHECKED_ANSWER["text"]

    assert parse_check(json.dumps(CHECKED_ANSWER)).text_artificial == 0.01


def test_a_real_box_carries_a_prob_the_documentation_doesnt_show() -> None:
    [box] = fake_answer("text_overlay")["text"]["boxes"]

    assert box["prob"] == 0.99


@pytest.mark.parametrize(
    "path",
    [
        ["text", "boxes"],
        ["media"],
        ["request"],
        ["nudity", "suggestive_classes"],
        ["nudity", "context"],
        ["nudity", "none"],
        ["text", "has_natural"],
        ["faces", 0, "x1"],
    ],
    ids=lambda path: ".".join(map(str, path)),
)
def test_a_field_the_decision_never_reads_may_go(path: list[Any]) -> None:
    """The founder, 4 October 2026: fail closed on the fields read, never on
    the rest. A vendor dropping or reshaping one of these changes no decision."""
    answer = fake_answer("text_overlay")
    target = answer
    for step in path[:-1]:
        target = target[step]
    del target[path[-1]]

    assert parse_check(json.dumps(answer)).text_artificial == 0.99932


def test_a_field_never_seen_is_logged_once_by_name_never_refused(
    captured_logs: CapturedLogs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(moderation, "_noticed", set())
    answer = fake_answer("approve")
    answer["nudity"]["new_class"] = 0.42
    answer["faces"][0]["attributes"]["age"]["band"] = "18-24"
    answer["brand_new_model"] = {"score": 0.5}

    first = parse_check(json.dumps(answer))
    parse_check(json.dumps(answer))

    assert first == parse_check(json.dumps(CHECKED_ANSWER))
    logged = [
        e for e in captured_logs.events if e["event"] == "moderation.unknown_fields"
    ]
    assert [(e["log_level"], e["fields"]) for e in logged] == [
        (
            "warning",
            [
                "brand_new_model",
                "brand_new_model.score",
                "faces[].attributes.age.band",
                "nudity.new_class",
            ],
        )
    ]
    assert "0.42" not in captured_logs.text and "18-24" not in captured_logs.text
    captured_logs.assert_listening()


def test_the_checked_answer_has_no_unknown_fields() -> None:
    for outcome in ("approve", "nudity", "minor_suspected", "no_face", "text_overlay"):
        assert field_paths(fake_answer(outcome)) <= KNOWN_FIELDS


def test_the_shape_check_sees_names_nesting_and_types_never_values() -> None:
    fake = shape(fake_answer("text_overlay"))

    assert differences(shape(fake_answer("text_overlay")), fake) == []
    # Values differ, the shape doesn't.
    assert (
        differences(
            shape(
                fake_answer("approve") | {"text": fake_answer("text_overlay")["text"]}
            ),
            fake,
        )
        == []
    )

    renamed = fake_answer("text_overlay")
    renamed["faces"][0]["attributes"] = {"minor": 0.01}
    assert differences(shape(renamed), fake) == [
        "faces[].attributes.age: in the fake's answer, not the real one",
        "faces[].attributes.minor: in the real answer, not the fake's",
    ]

    retyped = fake_answer("text_overlay")
    retyped["request"]["operations"] = "3"
    assert differences(shape(retyped), fake) == [
        "request.operations: real string, fake number"
    ]

    boxless = fake_answer("approve")
    assert differences(shape(boxless), fake) == [
        "text.boxes: in the fake's answer, not the real one"
    ]


def test_an_empty_list_says_nothing_about_its_elements() -> None:
    no_faces = fake_answer("no_face")

    assert differences(shape(no_faces), shape(fake_answer("approve"))) == []
