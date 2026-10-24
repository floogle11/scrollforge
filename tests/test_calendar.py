from datetime import datetime, timezone

from worker.calendar_weights import get_calendar_state, parse_calendar, target_card_counts


NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


def test_missing_calendar_returns_baseline_without_network():
    state = get_calendar_state("", now=NOW)
    assert state["calendar_mode"] == "BASELINE"
    assert state["active_exam_course"] is None
    assert sum(state["weights"].values()) == 1


def test_timezone_boundaries_distinguish_exam_day_crunch_and_window():
    def calendar(start):
        return f"""BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:x\nDTSTART;TZID=America/Denver:{start}\nSUMMARY:ME-3310 Midterm\nEND:VEVENT\nEND:VCALENDAR"""

    day = get_calendar_state("", now=NOW)
    # Exercise the parsed event state through the public pure parser with fixed UTC instants.
    from worker.calendar_weights import _fetch_ics
    import worker.calendar_weights as module
    original = module._fetch_ics
    try:
        module._fetch_ics = lambda _url, _timeout: calendar("20261024T183000")
        assert get_calendar_state("https://calendar.example/test.ics", now=NOW)["calendar_mode"] == "EXAM_DAY"
        module._fetch_ics = lambda _url, _timeout: calendar("20261026T183000")
        assert get_calendar_state("https://calendar.example/test.ics", now=NOW)["calendar_mode"] == "CRUNCH_WINDOW"
        module._fetch_ics = lambda _url, _timeout: calendar("20261028T183000")
        assert get_calendar_state("https://calendar.example/test.ics", now=NOW)["calendar_mode"] == "EXAM_WINDOW"
        module._fetch_ics = lambda _url, _timeout: calendar("20261031T183000")
        assert get_calendar_state("https://calendar.example/test.ics", now=NOW)["calendar_mode"] == "BASELINE"
        module._fetch_ics = lambda _url, _timeout: calendar("20261024T020000")
        earlier_today = get_calendar_state("https://calendar.example/test.ics", now=NOW)
        assert earlier_today["calendar_mode"] == "EXAM_DAY"
        assert earlier_today["active_exam_course"] == "ME-3310"
    finally:
        module._fetch_ics = original


def test_recurring_events_timezone_and_cancelled_override():
    ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:midterm
DTSTART;TZID=America/Denver:20261025T090000
DURATION:PT1H
RRULE:FREQ=DAILY;COUNT=3
SUMMARY:ME-3310 Quiz review
END:VEVENT
BEGIN:VEVENT
UID:midterm
RECURRENCE-ID;TZID=America/Denver:20261026T090000
DTSTART;TZID=America/Denver:20261026T090000
STATUS:CANCELLED
SUMMARY:ME-3310 Quiz review
END:VEVENT
END:VCALENDAR"""
    events = parse_calendar(ics, now=NOW)
    assert len(events) == 2
    assert {event["course"] for event in events} == {"ME-3310"}
    assert all(event["start"].tzinfo is not None for event in events)


def test_largest_remainder_targets_sum_to_total():
    counts = target_card_counts(total=11)
    assert sum(counts.values()) == 11
    assert counts["current_coursework"] == 3
