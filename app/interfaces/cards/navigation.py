from __future__ import annotations

from dataclasses import dataclass

from app.interfaces.cards.models import CardMode, CardShell, SourceRef


@dataclass(slots=True, frozen=True)
class BackTarget:
    source: SourceRef
    mode: CardMode
    entity_id: str | None = None


def transition_mode(shell: CardShell, *, target_mode: CardMode) -> CardShell:
    return shell.with_mode(target_mode)


def resolve_back_target(shell: CardShell) -> BackTarget:
    if shell.mode == CardMode.EXPANDED:
        return BackTarget(source=shell.source, mode=CardMode.COMPACT, entity_id=shell.entity_id)
    return BackTarget(source=shell.source, mode=CardMode.LIST_ROW)
