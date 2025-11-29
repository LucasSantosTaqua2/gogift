from app.enums.roles import Role
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum # Importar Enum para o status

class EnterpriseStatus(str, Enum):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'


class EnterpriseRejection(BaseModel):
    rejection_reason: str

class EnterpriseCreate(BaseModel):
    nome_fantasia: str
    cnpj: str
    nome_admin_empresa: str
    cpf_adm: str
    telefone: str

class EnterpriseResponse(BaseModel):
    id: int
    nome_fantasia: str
    cnpj: str
    nome_admin_empresa: str
    cpf_adm: str
    telefone: str
    creation_date: datetime
    user_id: int

    status: EnterpriseStatus
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True