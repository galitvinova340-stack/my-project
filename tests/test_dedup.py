from datetime import datetime

from monitor.models import AppointmentCandidate, normalize_key_part
from monitor.state import StateStore


def make_candidate(name="Иванов Иван Иванович", position="Аким района") -> AppointmentCandidate:
    return AppointmentCandidate(
        full_name=name,
        new_position=position,
        organization="Акимат района",
        appointment_date="16.09.2026",
        source_urls=["https://example.com"],
        verified_official=True,
    )


def test_dedup_key_ignores_case_and_punctuation():
    a = make_candidate("Иванов Иван Иванович", "Аким района")
    b = make_candidate("иванов иван иванович,", "аким  района")
    assert a.dedup_key == b.dedup_key


def test_dedup_key_differs_for_different_position():
    a = make_candidate(position="Аким района")
    b = make_candidate(position="Заместитель акима района")
    assert a.dedup_key != b.dedup_key


def test_state_store_marks_and_checks_known(tmp_path):
    store = StateStore(tmp_path / "state.db")
    candidate = make_candidate()
    assert not store.is_known(candidate.dedup_key)

    store.mark_seen(candidate.dedup_key, candidate.full_name, candidate.new_position)
    assert store.is_known(candidate.dedup_key)


def test_state_store_import_known_keys(tmp_path):
    store = StateStore(tmp_path / "state.db")
    key = normalize_key_part("Петров Пётр") + "|" + normalize_key_part("Директор департамента")
    store.import_known_keys([key])
    assert store.is_known(key)


def test_pending_queue_roundtrip(tmp_path):
    from monitor.models import AppointmentCard

    store = StateStore(tmp_path / "state.db")
    card = AppointmentCard(
        fixed_at=datetime.now(),
        full_name="Сидоров Сидор",
        photo_url="",
        new_position="Руководитель управления",
        organization="Управление образования",
        appointment_date="16.09.2026",
        previous_position="",
        career_path="",
        education="",
        contacts="",
        public_trace="",
        discussion_topics="",
    )
    store.queue_pending(card)
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].full_name == "Сидоров Сидор"

    store.clear_pending(card.dedup_key)
    assert store.list_pending() == []
