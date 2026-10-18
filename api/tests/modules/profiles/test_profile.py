"""`PATCH /v1/me/profile` (T-3.7): first name, hometown and city at the
`profile` step, about at the `about` step (D-068), each held to
`profiles.rules`, and nothing sent echoed into an error or a log."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OnboardingStep
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from tests.conftest import CapturedLogs, MakeUser

pytestmark = pytest.mark.usefixtures("test_redis")

ABOUT = "Chai, long walks by the canal, and arguing about films with friends."


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _error(response: Response) -> dict[str, Any]:
    body: dict[str, Any] = response.json()["error"]
    return body


async def _patch(client: AsyncClient, token: str, **fields: Any) -> Response:
    return await client.patch("/v1/me/profile", json=fields, headers=_bearer(token))


async def _at(
    db: AsyncSession, make_user: MakeUser, step: OnboardingStep, *, empty: bool = True
) -> tuple[User, str, Profile]:
    """A user at `step`, their profile's text cleared unless `empty` is False."""
    user, token = await make_user(onboarded=not empty)
    user.onboarding_step = step
    profile = await db.get(Profile, user.id)
    assert profile is not None
    if empty:
        profile.first_name = profile.hometown = profile.city = profile.about = None
    await db.flush()
    return user, token, profile


# --- The profile step ----------------------------------------------------------------


async def test_the_profile_step_advances_once_all_three_are_set(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)

    first = await _patch(client, token, first_name="Simran")
    assert first.status_code == 200, first.text
    assert first.json()["onboarding_step"] == "profile"

    rest = await _patch(client, token, hometown="Jalandhar", city="Phagwara")
    assert rest.status_code == 200
    assert rest.json()["onboarding_step"] == "username"
    await db.refresh(profile)
    assert (profile.first_name, profile.hometown, profile.city) == (
        "Simran",
        "Jalandhar",
        "Phagwara",
    )


@pytest.mark.parametrize(
    "name",
    ["हरप्रीत", "ਗੁਰਪ੍ਰੀਤ ਕੌਰ", "D’Souza", "Mary-Jane"],
    ids=["Devanagari", "Gurmukhi", "apostrophe", "hyphen"],
)
async def test_a_first_name_in_any_script_is_stored_as_typed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, name: str
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)

    response = await _patch(client, token, first_name=f"  {name} ")

    assert response.status_code == 200, response.text
    assert response.json()["profile"]["first_name"] == name
    await db.refresh(profile)
    assert profile.first_name == name


async def test_every_refused_field_is_named_and_nothing_is_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)

    response = await _patch(
        client, token, first_name="Ravi2", hometown="X" * 41, city="Phagwara"
    )

    assert response.status_code == 400
    assert _error(response)["details"]["fields"] == [
        {
            "field": "first_name",
            "problem": (
                "may only hold letters, single spaces, and an apostrophe or hyphen "
                "inside a name"
            ),
        },
        {"field": "hometown", "problem": "must be 1 to 40 characters"},
    ]
    await db.refresh(profile)
    await db.refresh(user)
    assert (profile.first_name, profile.hometown, profile.city) == (None,) * 3
    assert user.onboarding_step is OnboardingStep.PROFILE


async def test_a_blank_field_is_refused_and_a_null_one_is_left_alone(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)
    assert (await _patch(client, token, first_name="Simran")).status_code == 200

    blank = await _patch(client, token, first_name="   ")
    null = await _patch(client, token, first_name=None, city="Phagwara")

    assert blank.status_code == 400
    assert null.status_code == 200
    await db.refresh(profile)
    assert (profile.first_name, profile.city) == ("Simran", "Phagwara")


async def test_a_profile_field_before_its_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.SEEKING)

    response = await _patch(client, token, first_name="Simran")

    assert response.status_code == 403
    assert _error(response)["code"] == "ONBOARDING_INCOMPLETE"
    assert _error(response)["details"] == {"step": "seeking"}
    await db.refresh(profile)
    assert profile.first_name is None


# --- The about step ------------------------------------------------------------------


async def test_about_before_its_step_is_refused_with_everything_sent_beside_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    """At `profile`, about's step isn't reached: the whole request is refused,
    the profile fields sent with it too."""
    user, token, profile = await _at(db, make_user, OnboardingStep.PROFILE)

    response = await _patch(
        client, token, first_name="Simran", hometown="Jalandhar", city="Phagwara",
        about=ABOUT,
    )  # fmt: skip

    assert response.status_code == 403
    assert _error(response)["details"] == {"step": "profile"}
    await db.refresh(profile)
    await db.refresh(user)
    assert (profile.first_name, profile.about) == (None, None)
    assert user.onboarding_step is OnboardingStep.PROFILE


async def test_about_at_its_step_is_set_and_moves_on_to_photos(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about=f"  {ABOUT}\n")

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "photos"
    await db.refresh(profile)
    assert profile.about == ABOUT


@pytest.mark.parametrize("about", ["", "   \n  "], ids=["empty", "spaces"])
async def test_an_empty_about_at_its_step_skips_it_storing_none(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, about: str
) -> None:
    """The bio is optional (D-951): empty once trimmed is the skip, stored as
    NULL, never ''."""
    _, token, profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about=about)

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == "photos"
    assert response.json()["profile"]["about"] is None
    await db.refresh(profile)
    assert profile.about is None


async def test_a_short_about_is_kept_as_written(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about="Chai.")

    assert response.status_code == 200, response.text
    await db.refresh(profile)
    assert profile.about == "Chai."


@pytest.mark.parametrize(
    "about",
    [
        "9876543210",
        "98765 43210",
        "+91 98765 43210",
        "Call me on 98765 43210",
    ],
)
async def test_about_with_a_phone_number_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, about: str
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about=f"{ABOUT} {about}")

    assert response.status_code == 400
    assert _error(response)["details"]["fields"] == [
        {"field": "about", "problem": "can't hold a phone number"}
    ]
    await db.refresh(profile)
    assert profile.about is None


@pytest.mark.parametrize(
    "about",
    [
        "I lived in Delhi 2010-2015",
        "I was born in 1998 and moved here in 2015",
    ],
)
async def test_about_with_years_in_it_is_allowed(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, about: str
) -> None:
    _, token, _profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about=f"{about}, and I love it here.")

    assert response.status_code == 200, response.text


async def test_about_with_a_link_is_refused(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, _profile = await _at(db, make_user, OnboardingStep.ABOUT)

    response = await _patch(client, token, about=f"{ABOUT} instagram.com/simran")

    assert response.status_code == 400
    assert _error(response)["details"]["fields"][0]["problem"] == "can't hold a link"


# --- After the steps: edits that don't advance ---------------------------------------


@pytest.mark.parametrize(
    "step", [OnboardingStep.USERNAME, OnboardingStep.PHOTOS, OnboardingStep.DONE]
)
async def test_after_the_profile_step_its_fields_are_edits(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token, profile = await _at(db, make_user, step, empty=False)

    response = await _patch(client, token, first_name="Harpreet", city="Jalandhar")

    assert response.status_code == 200, response.text
    assert response.json()["onboarding_step"] == step.value
    await db.refresh(profile)
    await db.refresh(user)
    assert (profile.first_name, profile.city) == ("Harpreet", "Jalandhar")
    assert user.onboarding_step is step


@pytest.mark.parametrize("step", [OnboardingStep.PHOTOS, OnboardingStep.DONE])
async def test_after_the_about_step_about_is_an_edit(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser, step: OnboardingStep
) -> None:
    user, token, profile = await _at(db, make_user, step, empty=False)

    response = await _patch(client, token, about=ABOUT)

    assert response.status_code == 200
    await db.refresh(profile)
    await db.refresh(user)
    assert profile.about == ABOUT and user.onboarding_step is step


async def test_after_the_about_step_an_empty_about_clears_it(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    user, token, profile = await _at(db, make_user, OnboardingStep.DONE, empty=False)
    assert profile.about

    response = await _patch(client, token, about="")

    assert response.status_code == 200, response.text
    assert response.json()["profile"]["about"] is None
    await db.refresh(profile)
    await db.refresh(user)
    assert profile.about is None and user.onboarding_step is OnboardingStep.DONE


async def test_a_null_about_is_not_sent_and_changes_nothing(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, profile = await _at(db, make_user, OnboardingStep.DONE, empty=False)
    before = profile.about

    response = await _patch(client, token, about=None)

    assert response.status_code == 200, response.text
    await db.refresh(profile)
    assert profile.about == before and before


@pytest.mark.parametrize("about", ["", "x" * 301], ids=["empty", "301"])
async def test_the_database_refuses_an_empty_or_too_long_about(
    db: AsyncSession, make_user: MakeUser, about: str
) -> None:
    """Below the service (D-951): none is NULL, never '', so a profile says
    "no bio" one way only."""
    user, _ = await make_user()
    write = text("UPDATE profiles SET about = :about WHERE user_id = :id")

    with pytest.raises(IntegrityError) as refused:
        async with db.begin_nested():
            await db.execute(write, {"about": about, "id": user.id})

    assert getattr(refused.value.orig, "sqlstate", None) == "23514"
    assert "ck_profiles_about_length" in str(refused.value)


@pytest.mark.parametrize("about", [None, "x", "x" * 300], ids=["none", "1", "300"])
async def test_the_database_takes_none_or_1_to_300_characters(
    db: AsyncSession, make_user: MakeUser, about: str | None
) -> None:
    user, _ = await make_user()

    async with db.begin_nested():
        await db.execute(
            text("UPDATE profiles SET about = :about WHERE user_id = :id"),
            {"about": about, "id": user.id},
        )

    stored = await db.scalar(
        text("SELECT about FROM profiles WHERE user_id = :id"), {"id": user.id}
    )
    assert stored == about


async def test_about_at_the_username_step_is_onboarding_incomplete(
    db: AsyncSession, client: AsyncClient, make_user: MakeUser
) -> None:
    _, token, _profile = await _at(db, make_user, OnboardingStep.USERNAME)

    response = await _patch(client, token, about=ABOUT)

    assert response.status_code == 403
    assert _error(response)["details"] == {"step": "username"}


# --- Rule 15 ---------------------------------------------------------------------------


async def test_a_refused_phone_number_is_never_echoed_or_logged(
    db: AsyncSession,
    client: AsyncClient,
    make_user: MakeUser,
    captured_logs: CapturedLogs,
) -> None:
    """The number someone tried to put in their about is still a phone number:
    the refusal names the problem, never the value."""
    _, token, _profile = await _at(db, make_user, OnboardingStep.ABOUT)
    number = "98765 43210"

    response = await _patch(client, token, about=f"{ABOUT} Call {number}")

    assert response.status_code == 400
    seen = f"{response.text}\n{captured_logs.text}"
    assert [s for s in (number, "9876543210", "98765") if s in seen] == []
    captured_logs.assert_listening()
