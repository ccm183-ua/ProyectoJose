"""
Establece la contraseña del backend privado de cubiApp (H4).

Ejecutar directamente por el propietario en su propia terminal:

    python scripts/set_password.py

La contraseña nunca se pasa como argumento ni se registra en ningún log.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.settings import Settings, hash_password

MIN_LENGTH = 12


def main() -> int:
    password = getpass.getpass("Nueva contraseña (mínimo 12 caracteres): ")
    if len(password) < MIN_LENGTH:
        print(f"La contraseña debe tener al menos {MIN_LENGTH} caracteres.")
        return 1

    confirm = getpass.getpass("Repite la contraseña: ")
    if password != confirm:
        print("Las contraseñas no coinciden.")
        return 1

    Settings().save_password_hash(hash_password(password))
    print("Contraseña guardada correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
