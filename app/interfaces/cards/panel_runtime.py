from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import CardShell


@dataclass(slots=True, frozen=True)
class PanelUpdateInstruction:
    operation: str
    message_id: int | None
    shell: CardShell


class ActivePanelRegistry:
    def __init__(self) -> None:
        self._message_by_actor: dict[int, int] = {}

    def bind_message(self, *, actor_id: int, message_id: int) -> None:
        self._message_by_actor[actor_id] = message_id

    def render_or_replace(self, *, actor_id: int, shell: CardShell) -> PanelUpdateInstruction:
        message_id = self._message_by_actor.get(actor_id)
        if message_id is None:
            return PanelUpdateInstruction(operation="send", message_id=None, shell=shell)
        return PanelUpdateInstruction(operation="edit", message_id=message_id, shell=shell)
