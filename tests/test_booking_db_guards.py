from app.infrastructure.db.bootstrap import STACK1_TABLES


def test_booking_slot_truth_partial_unique_indexes_present() -> None:
    sql_blob = "\n".join(STACK1_TABLES)
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_slot_holds_active_slot" in sql_blob
    assert "WHERE status = 'active'" in sql_blob
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_bookings_live_slot" in sql_blob
    assert "status IN ('pending_confirmation', 'confirmed', 'reschedule_requested', 'checked_in', 'in_service')" in sql_blob
