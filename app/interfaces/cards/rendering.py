from __future__ import annotations

from app.common.panels import Panel
from app.interfaces.cards.models import CardShell


class CardShellRenderer:
    @staticmethod
    def to_panel(shell: CardShell) -> Panel:
        lines = [shell.title]
        if shell.subtitle:
            lines.append(shell.subtitle)
        for badge in shell.badges:
            lines.append(f"[{badge.text}]")
        for meta in shell.meta_lines:
            lines.append(f"{meta.key}: {meta.value}")
        if shell.mode.value == "expanded":
            lines.extend(shell.detail_lines)
        actions = ", ".join(action.label for action in shell.actions)
        if actions:
            lines.append(f"Actions: {actions}")
        panel_id = f"card:{shell.profile.value}:{shell.entity_id}:{shell.mode.value}"
        return Panel(panel_id=panel_id, text="\n".join(lines))
