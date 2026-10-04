"""Who the dev seed writes (T-1.15).

Where each piece comes from:

- **The prototype** (`docs/prototype/velora-prototype-reference.html`, the `P`
  array): each profile's first name, username, about text (verbatim, but for
  the four below), gender, hometown (`from`), its neighbourhood (`city`, in
  Bengaluru, which P-38 moved to Phagwara, below), its three tags as
  the first three interests, its `intent` as the first intent, `joined`,
  `showKudos`, and `v` for the men. The prototype's `likedYou` set the likes.
- **Drafted by Claude from each profile's about text, on 3 October 2026:** the
  two further interests each, except the three below; the second and third
  intents; the dates of birth, which give the prototype's ages on that date,
  with birthdays Claude chose; who hides their age or distance, who hides
  gifts, and who hides their profile; Kavya's "Carnatic", not in the catalogue,
  replaced by "Indie music" (P-27); the three test accounts' profiles; and the
  test accounts' three passes.
- **Decided by the advisor directing T-1.15 (Claude, in a separate chat, not
  the founder), 3 October 2026:** Ishita, Riya and Pooja, whom the prototype
  marks unverified, stop at the selfie step, unverified, so T-4.5 has women to
  verify (D-008 makes every onboarded woman verified); Riya's like moved to
  Tanvi, a verified woman, so no like is lost;
  the test accounts pass on two or three people, so discovery's "a profile you
  swiped doesn't come back" has data; and each location is scattered inside
  its area (seed/run.py, `scatter`), never on the centroid.
- **Reviewed by that advisor, 3 October 2026,** who replaced three of Claude's
  drafts: Sanya's Travel with Old Hindi cinema, Dev's Reading with Trekking,
  Pooja's Startups with Anime.
- **The founder read all twenty and signed off on the set, with no changes,**
  on 3 October 2026.
- **The test man's 60 credits:** T-1.15's plan, granted from T-5.1, when
  `wallet.service.credit()` exists to grant them (rule 5).
- **Each placeholder photo's colours (T-4.4):** the prototype's `c1` and `c2`
  for its twenty profiles; the test man and the test woman, who aren't in the
  prototype, take the first two of its `GR` gradients (Claude's choice, 4
  October 2026).

The phone numbers sit in one block, `+91 90000 00xxx`: `00001`-`00003` for the
test accounts, `001NN` for the prototype's profile NN. India reserves no
fictional range, so any of them may be a real person's (D-064). That's why the
seed never prints one, and why T-3.2 and T-3.14 keep an OTP to them on this
machine.

**Moved to Phagwara by P-38 (5 October 2026),** with `areas`:

- **Drafted by Claude, not yet reviewed by the founder:** the Phagwara area in
  place of each prototype neighbourhood, one for one, so neighbours stay
  neighbours, except Ananya's, moved to Chachoki: four people in one area put
  two of them 89 m apart at P-38's 250 m scatter, and the seed keeps everyone
  100 m apart. And four about texts rewritten for Phagwara: Ananya's hikes,
  Sanya's being Punjabi far from Punjab, Siddharth's "Bengaluru by choice",
  and Ishita's sketching on the metro, which Phagwara doesn't have.
- **Rewriting Ishita's, which P-38's entry didn't list, was the advisor's call**
  (Claude, in a separate chat), 5 October 2026.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.enums import Gender, OnboardingStep, Role, Seeking, SwipeDirection


@dataclass(frozen=True)
class Person:
    key: str  # how `LIKES` names this person
    phone: str  # E.164, as normalize_phone returns it
    role: Role = Role.USER
    step: OnboardingStep = OnboardingStep.DONE
    gender: Gender | None = None
    dob: date | None = None
    verified: bool = False
    first_name: str | None = None
    username: str | None = None
    about: str | None = None
    hometown: str | None = None
    area: str | None = None  # an `areas.name` in seed.run.AREA_CITY
    seeking: Seeking | None = None
    interests: tuple[str, ...] = ()  # `interests.label`s
    intents: tuple[str, ...] = ()  # `intents.label`s
    joined_days_ago: int = 0
    hide_age: bool = False
    hide_distance: bool = False
    is_hidden: bool = False
    show_kudos: bool = True
    show_gifts: bool = True
    pin: str | None = None
    # Only the three test accounts keep one of their own, readable and fixed;
    # everyone else gets signup's generated code (T-3.3).
    referral_code: str | None = None
    # Granted once through `wallet.service.credit()` (T-5.1), even to someone
    # already there. Only a man may hold any (D-076).
    credits: int = 0
    # The placeholder photo's two colours (T-4.4): the prototype's `c1`, `c2`.
    # Everyone past the photos step has one; nobody before it does.
    gradient: tuple[str, str] | None = None


@dataclass(frozen=True)
class SeedSwipe:
    swiper: str
    target: str
    dir: SwipeDirection


F, M = Gender.FEMALE, Gender.MALE
MEN, WOMEN = Seeking.MEN, Seeking.WOMEN
SELFIE = OnboardingStep.SELFIE

# The test woman's PIN. None of the shapes a common-PIN blocklist catches first:
# no run, no repeat, no year or date, no line on the keypad. T-3.9's rules
# (D-069) allow it; a test there holds it so, and `make seed` checks it too.
TEST_WOMAN_PIN = "4829"

TEST_ACCOUNTS: tuple[Person, ...] = (
    Person(
        key="test_man",
        phone="+919000000001",
        referral_code="TESTMAN",
        gender=M,
        dob=date(1998, 6, 1),
        first_name="Test man",
        username="test_man",
        gradient=("#E8455F", "#6E1028"),
        about="The seeded test man, for local development. Not a real person.",
        hometown="Bengaluru",
        area="Guru Hargobind Nagar",
        seeking=WOMEN,
        interests=("Cricket", "Cooking", "Travel", "Gaming", "Filter coffee"),
        intents=("Something serious",),
        credits=60,
    ),
    Person(
        key="test_woman",
        phone="+919000000002",
        referral_code="TESTWOMAN",
        gender=F,
        dob=date(2000, 9, 20),
        verified=True,
        first_name="Test woman",
        username="test_woman",
        gradient=("#D9663F", "#7A1228"),
        about="The seeded test woman, for local development. Not a real person.",
        hometown="Bengaluru",
        area="Guru Hargobind Nagar",
        seeking=MEN,
        interests=("Reading", "Yoga", "Baking", "Dogs", "Indie music"),
        intents=("Long term", "Go with the flow"),
        pin=TEST_WOMAN_PIN,
    ),
    # Onboarding not started, so not in discovery.
    Person(
        key="moderator",
        phone="+919000000003",
        referral_code="MODERATOR",
        role=Role.MODERATOR,
        step=OnboardingStep.DOB,
    ),
)

PROTOTYPE: tuple[Person, ...] = (
    Person(
        key="ananya",
        phone="+919000000101",
        gender=F,
        dob=date(2002, 3, 14),
        verified=True,
        first_name="Ananya",
        username="ananya_d",
        gradient=("#E8455F", "#6E1028"),
        about=(
            "Moved here for work three years ago and still can't handle the "
            "traffic. I hike most weekends — Triund if I have two days, the "
            "Shivaliks past Hoshiarpur if I don't."
        ),
        hometown="Dehradun",
        area="Chachoki",
        seeking=MEN,
        interests=("Filter coffee", "Trekking", "Indie music", "Travel", "Yearner"),
        intents=("Something serious", "Long term"),
        joined_days_ago=2,
    ),
    Person(
        key="meera",
        phone="+919000000102",
        gender=F,
        dob=date(2000, 7, 22),
        verified=True,
        first_name="Meera",
        username="meera.k",
        gradient=("#D9663F", "#7A1228"),
        about=(
            "Bengali, so I have strong opinions about fish and football. I throw "
            "pottery badly on Sundays. My dog Laddu is the real main character."
        ),
        hometown="Kolkata",
        area="Model Town",
        seeking=MEN,
        interests=("Pottery", "Dogs", "Old Hindi cinema", "Cooking", "Yapper"),
        intents=("Long term",),
        joined_days_ago=18,
        hide_distance=True,
    ),
    Person(
        key="ishita",
        phone="+919000000103",
        step=SELFIE,
        gender=F,
        dob=date(2003, 1, 9),
        first_name="Ishita",
        username="ishita_draws",
        gradient=("#C4324E", "#4E0A1C"),
        about=(
            "Grew up in Pune, here for my first job. I sketch strangers on the "
            "bus to Jalandhar. Please don't be offended if I sketch you."
        ),
        hometown="Pune",
        area="Banga Road",
        seeking=MEN,
        interests=(
            "Badminton",
            "Street food",
            "Sketching",
            "Hopeless romantic",
            "Photography",
        ),
        intents=("Go with the flow", "Friendship"),
        joined_days_ago=1,
        show_kudos=False,
    ),
    Person(
        key="sanya",
        phone="+919000000104",
        gender=F,
        dob=date(1998, 11, 30),
        verified=True,
        first_name="Sanya",
        username="sanya_bakes",
        gradient=("#B8496A", "#5C0F26"),
        about=(
            "Chandigarh girl in Phagwara, which means I judge every paratha "
            "against my mum's. I read two books a week and bake when I'm stressed."
        ),
        hometown="Chandigarh",
        area="Sarai Road",
        seeking=MEN,
        interests=("Reading", "Yoga", "Baking", "Cooking", "Old Hindi cinema"),
        intents=("Casual dating", "Situationship", "Go with the flow"),
        joined_days_ago=40,
        hide_age=True,
        show_kudos=False,
    ),
    Person(
        key="riya",
        phone="+919000000105",
        step=SELFIE,
        gender=F,
        dob=date(2004, 5, 5),
        first_name="Riya",
        username="riya_gg",
        gradient=("#D9553F", "#78121A"),
        about=(
            "Final year, part-time streamer. I'm much funnier over text than in "
            "person, fair warning."
        ),
        hometown="Hyderabad",
        area="Law Gate",
        seeking=MEN,
        interests=("Gaming", "Anime", "Cats", "Yapper", "Yearner"),
        intents=("Go with the flow", "Friendship"),
        joined_days_ago=3,
    ),
    Person(
        key="kavya",
        phone="+919000000106",
        gender=F,
        dob=date(2000, 12, 18),
        verified=True,
        first_name="Kavya",
        username="kavya.sings",
        gradient=("#C2405A", "#450A1A"),
        about=(
            "Trained in Carnatic vocal since I was six. I run half marathons and "
            "shoot film photography. Early mornings are non-negotiable."
        ),
        hometown="Mysuru",
        area="Satnampura",
        seeking=MEN,
        interests=("Indie music", "Running", "Photography", "Yoga", "Filter coffee"),
        intents=("Something serious",),
        joined_days_ago=25,
        hide_distance=True,
    ),
    Person(
        key="diya",
        phone="+919000000107",
        gender=F,
        dob=date(1998, 2, 27),
        verified=True,
        first_name="Diya",
        username="diya_reads",
        gradient=("#E8455F", "#4E0A1C"),
        about=(
            "Architect. Moved from Kochi for a project and stayed. I read mostly "
            "non-fiction and I've been slowly working through every filter coffee "
            "place in the city."
        ),
        hometown="Kochi",
        area="Maheru",
        seeking=MEN,
        interests=("Reading", "Travel", "Cooking", "Filter coffee", "Sketching"),
        intents=("Long term", "Something serious"),
        joined_days_ago=6,
    ),
    Person(
        key="nandini",
        phone="+919000000108",
        gender=F,
        dob=date(2002, 8, 11),
        verified=True,
        first_name="Nandini",
        username="nandini.m",
        gradient=("#D9663F", "#6E1028"),
        about=(
            "Yoga instructor and part-time graphic designer. I foster dogs, which "
            "means my flat is chaos roughly half the year."
        ),
        hometown="Nagpur",
        area="Bhagatpura",
        seeking=MEN,
        interests=("Yoga", "Dogs", "Indie music", "Sketching", "Hopeless romantic"),
        intents=("Something serious",),
        joined_days_ago=11,
    ),
    Person(
        key="pooja",
        phone="+919000000109",
        step=SELFIE,
        gender=F,
        dob=date(2000, 4, 2),
        first_name="Pooja",
        username="pooja_runs",
        gradient=("#C4324E", "#7A1228"),
        about=(
            "Data analyst. Indori, so I have unreasonably high standards for poha. "
            "Training for a half marathon, badly."
        ),
        hometown="Indore",
        area="Chahal Nagar",
        seeking=MEN,
        interests=("Running", "Street food", "Gaming", "Cooking", "Anime"),
        intents=("Casual dating",),
        joined_days_ago=4,
    ),
    Person(
        key="tanvi",
        phone="+919000000110",
        gender=F,
        dob=date(2002, 10, 25),
        verified=True,
        first_name="Tanvi",
        username="tanvi_clicks",
        gradient=("#B8496A", "#450A1A"),
        about=(
            "Photography student from Jaipur. I spend weekends shooting heritage "
            "buildings and evenings rewatching Guru Dutt films."
        ),
        hometown="Jaipur",
        area="LPU",
        seeking=MEN,
        interests=("Photography", "Old Hindi cinema", "Baking", "Travel", "Yearner"),
        intents=("Go with the flow",),
        joined_days_ago=8,
        show_gifts=False,
    ),
    Person(
        key="arjun",
        phone="+919000000111",
        gender=M,
        dob=date(1999, 6, 17),
        verified=True,
        first_name="Arjun",
        username="arjun_cooks",
        gradient=("#A8253C", "#3E0812"),
        about=(
            "Product designer, Rajasthani, moved here in 2021. I cook for people "
            "when I like them, which is how you'll know."
        ),
        hometown="Jaipur",
        area="Model Town",
        seeking=WOMEN,
        interests=("Cricket", "Cooking", "Travel", "Sketching", "Hopeless romantic"),
        intents=("Something serious",),
        joined_days_ago=5,
    ),
    Person(
        key="dev",
        phone="+919000000112",
        gender=M,
        dob=date(2001, 9, 3),
        verified=True,
        first_name="Dev",
        username="dev.builds",
        gradient=("#C43450", "#5A0E22"),
        about=(
            "Building something in fintech. I run at 6am to feel like I have my "
            "life together. It works about half the time."
        ),
        hometown="Bhopal",
        area="Guru Hargobind Nagar",
        seeking=WOMEN,
        interests=("Startups", "Running", "Photography", "Filter coffee", "Trekking"),
        intents=("Go with the flow", "Casual dating", "Friendship"),
        joined_days_ago=12,
    ),
    Person(
        key="kabir",
        phone="+919000000113",
        gender=M,
        dob=date(1997, 1, 26),
        first_name="Kabir",
        username="kabir_lko",
        gradient=("#CC6440", "#661020"),
        about=(
            "Lawyer. Lucknowi, which means I'm annoyingly polite. I read a lot and "
            "argue for a living, so I've learned when not to."
        ),
        hometown="Lucknow",
        area="Sarai Road",
        seeking=WOMEN,
        interests=("Reading", "Old Hindi cinema", "Street food", "Yapper", "Travel"),
        intents=("Long term", "Something serious"),
        joined_days_ago=1,
        hide_age=True,
    ),
    Person(
        key="rohan",
        phone="+919000000114",
        gender=M,
        dob=date(2001, 12, 19),
        verified=True,
        first_name="Rohan",
        username="rohan_goa",
        gradient=("#E04A62", "#4A0C1E"),
        about=(
            "Backend engineer. Grew up on a beach, now I live in traffic. I have "
            "two dogs and a guitar I'm mediocre at."
        ),
        hometown="Goa",
        area="Law Gate",
        seeking=WOMEN,
        interests=("Gaming", "Dogs", "Indie music", "Travel", "Startups"),
        intents=("Casual dating",),
        joined_days_ago=7,
    ),
    Person(
        key="vikram",
        phone="+919000000115",
        gender=M,
        dob=date(1996, 3, 8),
        verified=True,
        first_name="Vikram",
        username="vik_rides",
        gradient=("#A8253C", "#5C0F26"),
        about=(
            "Consultant, Tamil, based here eight years. Weekend motorcycle rides "
            "and a camera I overpaid for. Looking for something that lasts."
        ),
        hometown="Chennai",
        area="Hadiabad",
        seeking=WOMEN,
        interests=("Travel", "Photography", "Cricket", "Trekking", "Hopeless romantic"),
        intents=("Something serious", "Long term"),
        joined_days_ago=22,
        show_gifts=False,
    ),
    Person(
        key="aditya",
        phone="+919000000116",
        gender=M,
        dob=date(2000, 8, 15),
        first_name="Aditya",
        username="adi_plays",
        gradient=("#C43450", "#3E0812"),
        about=(
            "Software engineer from Patna. I play badminton four nights a week and "
            "cook badly the other three."
        ),
        hometown="Patna",
        area="Banga Road",
        seeking=WOMEN,
        interests=("Badminton", "Anime", "Cooking", "Gaming", "Street food"),
        intents=("Go with the flow",),
        joined_days_ago=2,
        show_kudos=False,
    ),
    Person(
        key="karan",
        phone="+919000000117",
        gender=M,
        dob=date(1998, 5, 13),
        verified=True,
        first_name="Karan",
        username="karan_lifts",
        gradient=("#CC6440", "#4E0A1C"),
        about=(
            "Sales, and yes I know what that sounds like. From Amritsar. I gym in "
            "the mornings and cook Punjabi food badly on Sundays."
        ),
        hometown="Amritsar",
        area="Sukhchain Nagar",
        seeking=WOMEN,
        interests=("Running", "Cooking", "Travel", "Street food", "Yapper"),
        intents=("Long term",),
        joined_days_ago=30,
        is_hidden=True,
    ),
    Person(
        key="siddharth",
        phone="+919000000118",
        gender=M,
        dob=date(1995, 7, 4),
        verified=True,
        first_name="Siddharth",
        username="sid_writes",
        gradient=("#E04A62", "#661020"),
        about=(
            "Reporter covering city politics. Delhi-born, Phagwara by choice. I "
            "read, I walk a lot, and I know where the good coffee is."
        ),
        hometown="Delhi",
        area="Guru Nanak Nagar",
        seeking=WOMEN,
        interests=("Reading", "Indie music", "Filter coffee", "Yapper", "Trekking"),
        intents=("Something serious",),
        joined_days_ago=14,
        hide_age=True,
    ),
    Person(
        key="neel",
        phone="+919000000119",
        gender=M,
        dob=date(2001, 2, 20),
        first_name="Neel",
        username="neel_shoots",
        gradient=("#C2405A", "#450A1A"),
        about=(
            "Gujarati, shoot weddings for a living and street photography for "
            "myself. My weekends are booked eight months out, so weekdays it is."
        ),
        hometown="Ahmedabad",
        area="Bhullarai",
        seeking=WOMEN,
        interests=(
            "Photography",
            "Gaming",
            "Street food",
            "Travel",
            "Hopeless romantic",
        ),
        intents=("Casual dating", "Situationship"),
        joined_days_ago=3,
        hide_distance=True,
    ),
    Person(
        key="yash",
        phone="+919000000120",
        gender=M,
        dob=date(2003, 10, 1),
        verified=True,
        first_name="Yash",
        username="yash_codes",
        gradient=("#B8496A", "#78121A"),
        about=(
            "First job out of college. From Surat. I game too much, I'm learning "
            "to cook, and I'm figuring out what I'm doing here."
        ),
        hometown="Surat",
        area="Maheru",
        seeking=WOMEN,
        interests=("Gaming", "Anime", "Startups", "Cooking", "Yearner"),
        intents=("Go with the flow", "Friendship", "Casual dating"),
        joined_days_ago=9,
    ),
)

PEOPLE: tuple[Person, ...] = TEST_ACCOUNTS + PROTOTYPE

LIKE, SUPER, PASS = SwipeDirection.LIKE, SwipeDirection.SUPER, SwipeDirection.PASS

# Never a like both ways: that's a match, which T-6.4 makes, not the seed.
SWIPES: tuple[SeedSwipe, ...] = (
    # A super-like costs a man Velas; for a woman it's free (D-002).
    SeedSwipe("ananya", "test_man", SUPER),
    SeedSwipe("meera", "test_man", LIKE),
    SeedSwipe("tanvi", "test_man", LIKE),  # Riya's, in the prototype
    SeedSwipe("arjun", "test_woman", LIKE),
    SeedSwipe("rohan", "test_woman", LIKE),
    # The test accounts' own passes, so their decks show that a profile they
    # swiped doesn't come back.
    SeedSwipe("test_man", "diya", PASS),
    SeedSwipe("test_man", "nandini", PASS),
    SeedSwipe("test_woman", "kabir", PASS),
)
