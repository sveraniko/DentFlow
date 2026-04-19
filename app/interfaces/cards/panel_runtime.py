from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import CardShell
from app.interfaces.cards.runtime_state import CardRuntimeCoordinator, PanelFamily


@dataclass(slots=True, frozen=True)
class PanelUpdateInstruction:
    operation: str
    message_id: int | None
    shell: CardShell


class ActivePanelRegistry:
    def __init__(self, *, runtime: CardRuntimeCoordinator, panel_family: PanelFamily) -> None:
        self._runtime = runtime
        self._panel_family = panel_family

    async def bind_message(self, *, actor_id: int, chat_id: int, message_id: int, shell: CardShell) -> None:
        await self._runtime.bind_panel(
            actor_id=actor_id,
            chat_id=chat_id,
            message_id=message_id,
            panel_family=self._panel_family,
            profile=shell.profile,
            entity_id=shell.entity_id,
            source_context=shell.source.context,
            source_ref=shell.source.source_ref or "",
            page_or_index=str(shell.source.page_or_index or ""),
            state_token=shell.state_token,
        )

    async def render_or_replace(self, *, actor_id: int, shell: CardShell) -> PanelUpdateInstruction:
        current = await self._runtime.resolve_active_panel(actor_id=actor_id, panel_family=self._panel_family)
        if current is None:
            return PanelUpdateInstruction(operation="send", message_id=None, shell=shell)
        return PanelUpdateInstruction(operation="edit", message_id=current.message_id, shell=shell)
