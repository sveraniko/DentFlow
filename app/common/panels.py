from dataclasses import dataclass


@dataclass(slots=True)
class Panel:
    panel_id: str
    text: str


class PanelRenderer:
    @staticmethod
    def render(panel: Panel) -> str:
        return panel.text
