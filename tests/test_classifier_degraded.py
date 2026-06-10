"""quality-pass-1.4 G6 + G9 — classifier degraded mode and French parity.

G6: when BOTH free L6 tiers (NIM + Groq) are down, the filter no longer
passes everything — only articles clearing a tightened keyword bar
(dollar regex OR Cat A+B+C triple co-occurrence) survive. Fail-open
passes are counted and alerted via service_health.

G9: French Category B (economic signal) keywords, French dollar
formatting ("250 millions $"), and per-language pass/reject counters.
"""
import sys
import types

import pytest

import article_filter as af


# ══════════════════════════════════════════════════════════════════════════════
# G9 — French article fixtures (L4 keyword pass + dollar bypass)
# ══════════════════════════════════════════════════════════════════════════════

# >= 6 French fixtures that must pass Layer 1
_FRENCH_SHOULD_PASS = [
    # L4: Cat A (projet/agrandissement/usine...) + French Cat B
    ("Projet d'agrandissement de l'hôpital: le financement est confirmé",
     "Le chantier débutera cet automne"),
    ("Nouvelle usine de batteries: contrat octroyé au consortium québécois",
     "Les travaux de construction commencent en 2027"),
    ("Investissement majeur dans l'infrastructure de transport",
     "Le budget prévoit des retombées régionales"),
    ("Réaménagement du port: appel d'offres lancé",
     "Étude de faisabilité complétée pour le projet"),
    # Dollar bypass with French formatting
    ("Québec annonce un projet de 250 millions $ pour le tramway", ""),
    ("Un investissement de 1,2 milliards $ dans une usine de Bécancour", ""),
]


@pytest.mark.parametrize("title,summary", _FRENCH_SHOULD_PASS)
def test_french_articles_pass_layer1(title, summary):
    assert af.layer1_keyword_check(title, summary), \
        f"French article failed L1: {title}"


def test_french_dollar_bypass_format():
    # "250 millions $" must match the dollar regex (French ordering)
    assert af._has_dollar_value("le projet de 250 millions $ est lancé")
    assert af._has_dollar_value("un budget de 1,2 milliards $")


def test_french_cat_b_is_additive():
    # Original anglo Cat B untouched
    for kw in ("million", "investment", "funding", "budget"):
        assert kw in af._CAT_B
    # French additions live in the combined set used by the compiled regex
    for kw in ("financement", "contrat", "subvention", "chantier", "travaux"):
        assert kw in af._CAT_B_ALL
    assert af._CAT_B <= af._CAT_B_ALL


def test_english_only_economic_news_still_fails_l1():
    # French additions must not loosen the gate for non-project content
    assert not af.layer1_keyword_check(
        "Interest rate announcement expected tomorrow", "BoC policy update")


# ── Per-language counters ─────────────────────────────────────────────────────

def test_article_language_detection():
    assert af._article_language({"_language": "fr"}) == "fr"
    assert af._article_language({"_language": "en"}) == "en"
    assert af._article_language({"language": "fr"}) == "fr"
    assert af._article_language({"category": "regional_media_fr"}) == "fr"
    assert af._article_language({"category": "regional_media"}) == "en"
    assert af._article_language({}) == "en"


def test_per_language_stats_in_run_summary(capsys, monkeypatch):
    # Force the degraded path so no network is touched
    monkeypatch.setattr(af, "get_nim_client",
                        lambda: (_ for _ in ()).throw(RuntimeError("down")))
    _install_fake_groq(monkeypatch, available=False)

    articles = [
        {"title": "Projet d'agrandissement de l'hôpital: financement confirmé",
         "summary": "250 millions $ pour le chantier", "_language": "fr",
         "url": "https://ex.qc/1"},
        {"title": "NHL playoff schedule announced", "summary": "",
         "_language": "en", "url": "https://ex.ca/2"},
    ]
    af.filter_articles(articles, log_filtered=False)
    out = capsys.readouterr().out
    assert "[Filter lang]" in out
    assert "fr:" in out and "en:" in out


# ══════════════════════════════════════════════════════════════════════════════
# G6 — tightened degraded mode
# ══════════════════════════════════════════════════════════════════════════════

def _install_fake_groq(monkeypatch, available=False, indices=None):
    fake = types.ModuleType("groq_client")
    fake.can_use_groq = lambda: available
    fake.batch_classify = lambda articles, prompt, batch_size=20: (indices or [])
    monkeypatch.setitem(sys.modules, "groq_client", fake)
    return fake


def test_degraded_keyword_pass_dollar_regex():
    assert af._degraded_keyword_pass(
        {"title": "City approves $45 million adaptive reuse", "summary": ""})
    # French dollar format also clears the bar
    assert af._degraded_keyword_pass(
        {"title": "Projet de 250 millions $ annoncé", "summary": ""})


def test_degraded_keyword_pass_triple_cooccurrence():
    # Cat A (construction) + Cat B (contract) + Cat C (awarded contract/approved)
    assert af._degraded_keyword_pass(
        {"title": "Highway construction contract awarded to local firm",
         "summary": "Project approved by the province"})


def test_degraded_keyword_pass_rejects_weak_articles():
    # Cat A + Cat B only (no Cat C, no dollar) — fails the tightened bar
    assert not af._degraded_keyword_pass(
        {"title": "Construction sector investment trends", "summary": ""})
    # Nothing at all
    assert not af._degraded_keyword_pass(
        {"title": "Local weather update for the weekend", "summary": ""})


def test_full_chain_failure_keeps_only_tightened_bar(monkeypatch, capsys):
    monkeypatch.setattr(af, "get_nim_client",
                        lambda: (_ for _ in ()).throw(RuntimeError("NIM down")))
    _install_fake_groq(monkeypatch, available=False)

    health_calls = []

    class _FakeHealth:
        def record_failure(self, service, reason=""):
            health_calls.append((service, reason))

    fake_sh = types.ModuleType("service_health")
    fake_sh.get = lambda: _FakeHealth()
    monkeypatch.setitem(sys.modules, "service_health", fake_sh)

    articles = [
        {"title": "Plant expansion: $300 million investment approved",
         "summary": ""},                                   # dollar — kept
        {"title": "Hospital construction contract awarded, project approved",
         "summary": ""},                                   # A+B+C — kept
        {"title": "Mayor discusses housing development ideas",
         "summary": ""},                                   # weak — dropped
        {"title": "Team wins championship game",
         "summary": ""},                                   # noise — dropped
    ]
    kept = af.layer3_gemini_prescreen(articles)
    assert kept == [0, 1]

    out = capsys.readouterr().out
    assert "[Filter L6 DEGRADED] keyword-only mode: kept 2 of 4" in out
    assert "[Filter L6 WARN]" in out  # 2/4 > 10%
    assert any(svc == "l6_classifier" for svc, _ in health_calls)


def test_groq_fallback_still_used_before_degraded(monkeypatch):
    monkeypatch.setattr(af, "get_nim_client",
                        lambda: (_ for _ in ()).throw(RuntimeError("NIM down")))
    _install_fake_groq(monkeypatch, available=True, indices=[1])

    articles = [{"title": "a", "summary": ""}, {"title": "b", "summary": ""}]
    assert af.layer3_gemini_prescreen(articles) == [1]


def test_nim_missing_verdicts_fail_open_with_warn(monkeypatch, capsys):
    """Normal per-verdict fail-open is untouched, but an abnormal rate warns."""

    class _FakeNim:
        def chat_sync(self, **kw):
            return "1.R\n2.I"  # verdicts only for 2 of 12 articles

    monkeypatch.setattr(af, "get_nim_client", lambda: _FakeNim())

    health_calls = []

    class _FakeHealth:
        def record_failure(self, service, reason=""):
            health_calls.append(service)

    fake_sh = types.ModuleType("service_health")
    fake_sh.get = lambda: _FakeHealth()
    monkeypatch.setitem(sys.modules, "service_health", fake_sh)

    articles = [{"title": f"art {i}", "summary": ""} for i in range(12)]
    kept = af.layer3_gemini_prescreen(articles)

    # index 1 was 'I'; everything else kept (1 explicit R + 10 fail-open)
    assert 1 not in kept
    assert len(kept) == 11

    out = capsys.readouterr().out
    assert "[Filter L6 WARN] fail-open passes 10/12" in out
    assert "l6_classifier" in health_calls


def test_nim_complete_verdicts_no_warn(monkeypatch, capsys):
    class _FakeNim:
        def chat_sync(self, **kw):
            return "\n".join(f"{i}.R" for i in range(1, 6))

    monkeypatch.setattr(af, "get_nim_client", lambda: _FakeNim())
    articles = [{"title": f"art {i}", "summary": ""} for i in range(5)]
    kept = af.layer3_gemini_prescreen(articles)
    assert kept == [0, 1, 2, 3, 4]
    assert "[Filter L6 WARN]" not in capsys.readouterr().out
