from __future__ import annotations


class InvalidBookingLifecycleTransitionError(ValueError):
    def __init__(self, *, entity_name: str, current_status: str, requested_status: str) -> None:
        super().__init__(
            f"Invalid {entity_name} transition: {current_status} -> {requested_status}"
        )
        self.entity_name = entity_name
        self.current_status = current_status
        self.requested_status = requested_status


class InvalidSessionTransitionError(InvalidBookingLifecycleTransitionError):
    def __init__(self, *, current_status: str, requested_status: str) -> None:
        super().__init__(
            entity_name="booking_session",
            current_status=current_status,
            requested_status=requested_status,
        )


class InvalidSlotHoldTransitionError(InvalidBookingLifecycleTransitionError):
    def __init__(self, *, current_status: str, requested_status: str) -> None:
        super().__init__(
            entity_name="slot_hold",
            current_status=current_status,
            requested_status=requested_status,
        )


class InvalidBookingTransitionError(InvalidBookingLifecycleTransitionError):
    def __init__(self, *, current_status: str, requested_status: str) -> None:
        super().__init__(
            entity_name="booking",
            current_status=current_status,
            requested_status=requested_status,
        )


class InvalidWaitlistTransitionError(InvalidBookingLifecycleTransitionError):
    def __init__(self, *, current_status: str, requested_status: str) -> None:
        super().__init__(
            entity_name="waitlist_entry",
            current_status=current_status,
            requested_status=requested_status,
        )
