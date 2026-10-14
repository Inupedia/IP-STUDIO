from getpass import getpass
import sys

from app.config import Settings
from app.db import make_engine, make_session_factory
from app.security import is_valid_jwt_secret
from app.services.auth import create_workspace_admin


def main() -> int:
    settings = Settings()
    if not settings.database_url:
        print("Set DATABASE_URL in the environment or .env before bootstrapping.", file=sys.stderr)
        return 2
    if not is_valid_jwt_secret(settings.jwt_secret_key):
        print("Set JWT_SECRET_KEY to at least 32 random bytes before bootstrapping.", file=sys.stderr)
        return 2

    email = input("Administrator email: ").strip()
    password = getpass("Administrator password (minimum 12 characters): ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    engine = make_engine(settings.database_url)
    try:
        user = create_workspace_admin(make_session_factory(engine), email, password)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    print(f"Created the IP Studio administrator {user.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
