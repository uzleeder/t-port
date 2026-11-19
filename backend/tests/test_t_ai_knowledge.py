"""T-AI's place knowledge (14 regions, 28 places, English and Uzbek) and how T-AI uses it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.ai.knowledge import PlaceKnowledge

INTERPRET = "/api/v1/ai/interpret"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def kb() -> PlaceKnowledge:
    return PlaceKnowledge.load()


def keys(places) -> list[str]:
    return [p.key for p in places]


# --- the data -------------------------------------------------------------------------------------
def test_every_region_has_a_landmark_and_a_destination_in_both_languages(kb):
    assert len(kb.regions) == 14 and len(kb.places) == 28
    for region in kb.regions:
        assert sorted(p.kind for p in kb.in_region(region)) == ["destination", "landmark"], region
    for p in kb.places:
        assert p.sources and all(url.startswith("https://") for _, url in p.sources), p.key
        for lang in ("en", "uz"):
            t = p.text[lang]
            assert t.name and t.area and t.category, (p.key, lang)
            assert min(len(t.history), len(t.see), len(t.tip)) > 20, (p.key, lang)
        assert p.explore_url == f"/explore/{p.region}#{p.key}"


@pytest.mark.skipif(
    not (REPO / "scripts/build_place_knowledge.py").exists(), reason="needs the full repository"
)
def test_knowledge_files_match_the_place_card_text():
    """backend/app/data/places.json and the frontend copy are rebuilt from content/place-cards."""
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/build_place_knowledge.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr


# --- finding places in a message ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tell me about Registan", ["registan"]),
        ("Is Shohi Zinda worth it?", ["shah-i-zinda"]),
        ("ichan qal'a haqida", ["itchan-kala"]),
        ("What can I see in Khiva?", ["itchan-kala", "kalta-minor"]),  # a city -> its region's places
        ("Things to do in Karakalpakstan", ["moynaq-ships", "savitsky-museum"]),
        ("Buxoro haqida aytib bering", ["lyabi-hauz", "poi-kalon"]),
        ("Что посмотреть в Самарканде?", ["shah-i-zinda", "registan"]),
        ("How do I get to Amirsoy and the Charvak dam?", ["amirsoy", "charvak-dam"]),
    ],
)
def test_find_places(kb, catalog, text, expected):
    assert keys(kb.find(text, catalog)) == expected


def test_find_nothing_for_unrelated_text(kb, catalog):
    assert kb.find("cheapest ticket please", catalog) == []


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Samarqandda nimalarni ko‘rish mumkin?", "uz"),
        ("Buxoro haqida aytib bering", "uz"),
        ("What can I see in Bukhara?", "en"),
        ("Leave Tashkent at 8 o'clock", "en"),
        ("Что посмотреть в Хиве?", "en"),  # no Russian copy yet: answers in English
    ],
)
def test_language(kb, text, lang):
    assert kb.language(text) == lang


# --- T-AI answers ----------------------------------------------------------------------------------
def test_t_ai_answers_a_place_question_from_its_knowledge(client):
    body = client.post(INTERPRET, json={"text": "What can I see in Khiva?"}).json()
    assert body["assistant"] == "T-AI" and body["language"] == "en"
    assert body["answer"] == "Here's what I know about Khorezm: Itchan Kala and Kalta Minor."
    assert [p["key"] for p in body["places"]] == ["itchan-kala", "kalta-minor"]
    itchan = body["places"][0]
    assert itchan["name"] == "Itchan Kala" and "UNESCO" in itchan["history"]
    assert itchan["sources"][0]["url"] == "https://whc.unesco.org/en/list/543"
    assert itchan["explore_url"] == "/explore/khorezm#itchan-kala"
    # No route yet, so T-AI offers to plan one instead of searching.
    assert body["needs_clarification"] and body["results"] is None
    assert body["clarification"] == "Want to go there? Tell me where you're starting from and when."


def test_t_ai_answers_in_uzbek_when_asked_in_uzbek(client):
    body = client.post(INTERPRET, json={"text": "Registon haqida aytib bering"}).json()
    assert body["language"] == "uz"
    assert body["answer"] == "Registon maydoni haqida bilganlarim:"
    (place,) = body["places"]
    assert place["name"] == "Registon maydoni" and place["region_name"] == "Samarqand viloyati"
    assert "madrasa" in place["history"]
    assert "yo‘lga chiqishingizni" in body["clarification"]


def test_trip_requests_also_describe_the_destination(client):
    body = client.post(INTERPRET, json={"text": "Tashkent to Bukhara tomorrow by train"}).json()
    assert body["results"] is not None and not body["needs_clarification"]
    assert [p["key"] for p in body["places"]] == ["lyabi-hauz", "poi-kalon"]
    assert body["answer"] == "While you're there: Lyabi-Hauz and Poi Kalon."


def test_plain_trip_clarifications_are_unchanged(client):
    body = client.post(INTERPRET, json={"text": "cheapest ticket tomorrow"}).json()
    assert body["places"] == [] and body["answer"] is None
    assert body["clarification"].startswith("Where are you travelling from")


def test_a_bare_place_name_is_answered(client):
    body = client.post(INTERPRET, json={"text": "Savitsky museum"}).json()
    assert [p["key"] for p in body["places"]] == ["savitsky-museum"]


def test_incomplete_trips_keep_their_precise_question(client):
    body = client.post(INTERPRET, json={"text": "to Samarkand tomorrow"}).json()
    assert body["places"] == []
    assert body["clarification"] == "Where will you be starting from?"


def test_specific_problems_are_still_explained_alongside_place_answers(client):
    body = client.post(
        INTERPRET, json={"text": "What to see in Samarkand from Tashkent under 50 dollars"}
    ).json()
    assert body["needs_clarification"]
    assert "UZS" in body["clarification"]
