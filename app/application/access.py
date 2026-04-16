from dataclasses import dataclass

from app.domain.access_identity.roles import Role


@dataclass(slots=True)
class ActorContext:
    actor_id: str
    role: Role
    clinic_id: str
    locale: str | None = None


class AccessResolver:
    """Placeholder contract for explicit role bindings (Stack 1+)."""

    async def is_allowed(self, actor: ActorContext, allowed_roles: set[Role]) -> bool:
        return actor.role in allowed_roles
