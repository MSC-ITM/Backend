import ulid
import uuid

def new_id(prefix: str = "") -> str:
    """
    Genera un ID string robusto usando ULID si está disponible.
    Algunos paquetes exponen .str y otros no; hacemos fallback seguro.
    """
    try:
        u = ulid.new()              # genera un ULID
        s = getattr(u, "str", None) # algunos exponen .str
        if not s:
            s = str(u)              # otros convierten bien con str(...)
        return prefix + s
    except Exception:
        # fallback ultra seguro por si cambia la lib: UUID4
        return prefix + uuid.uuid4().hex
