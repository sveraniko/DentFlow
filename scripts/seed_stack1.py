from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.application.access import InMemoryAccessRepository
from app.application.clinic_reference import InMemoryClinicReferenceRepository
from app.application.policy import InMemoryPolicyRepository
from app.bootstrap.seed import SeedBootstrap


def main() -> None:
    clinic_repo = InMemoryClinicReferenceRepository()
    access_repo = InMemoryAccessRepository()
    policy_repo = InMemoryPolicyRepository()

    SeedBootstrap(clinic_repo, access_repo, policy_repo).load_from_file(Path("seeds/stack1_seed.json"))

    print("Stack 1 seed loaded")
    print(f"clinics={len(clinic_repo.clinics)} branches={len(clinic_repo.branches)} doctors={len(clinic_repo.doctors)} services={len(clinic_repo.services)}")
    print(
        "actors="
        f"{len(access_repo.actor_identities)} telegram_bindings={len(access_repo.telegram_bindings)} role_assignments={len(access_repo.role_assignments)}"
    )
    print(f"policy_sets={len(policy_repo.policy_sets)} policy_values={len(policy_repo.policy_values)} feature_flags={len(policy_repo.feature_flags)}")


if __name__ == "__main__":
    main()
