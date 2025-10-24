from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import func

class Timestamped(SQLModel):
    created_at: datetime = Field(default=None, sa_column=Column("created_at", nullable=False, server_default=func.now()))
    updated_at: datetime = Field(default=None, sa_column=Column("updated_at", nullable=False, server_default=func.now(), onupdate=func.now()))
