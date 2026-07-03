from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base déclarative unique, importée par app/database.py et app/models/user.py.

    Séparée dans son propre fichier pour éviter l'import circulaire
    database.py <-> models/user.py.
    """
    pass
