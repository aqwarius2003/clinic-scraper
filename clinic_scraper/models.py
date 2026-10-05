"""Pydantic v2 и dataclass модели данных ClinicScraper."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


@dataclass
class RawClinic:
    """Сырая запись клиники из гео-сервисов (2GIS / Яндекс.Карты)."""
    source_id: str
    name: str
    address: str = ""
    phones: List[str] = field(default_factory=list)
    site: str = ""
    rubrics: List[str] = field(default_factory=list)
    branches_count: int = 1
    source: str = "2gis"
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "address": self.address,
            "phones": list(self.phones),
            "site": self.site,
            "rubrics": list(self.rubrics),
            "branches_count": self.branches_count,
            "source": self.source,
            "snippet": self.snippet,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawClinic":
        return cls(
            source_id=str(data.get("source_id", "")),
            name=data.get("name", ""),
            address=data.get("address", ""),
            phones=list(data.get("phones", [])),
            site=data.get("site", ""),
            rubrics=list(data.get("rubrics", [])),
            branches_count=int(data.get("branches_count", 1)),
            source=data.get("source", "2gis"),
            snippet=data.get("snippet", ""),
        )


class AnalysisResult(BaseModel):
    """Результат скоринга организации (Regex + Gemini)."""
    injection_therapy: str = "Нет"
    injection_reason: str = ""
    prp_therapy_brand: str = "Нет"
    specialists_count: str = "Требует уточнения"
    specialists_comment: str = ""
    confidence: Optional[float] = None


class ClinicRecord(BaseModel):
    """Финальная запись организации для формирования чекпоинтов и Excel-выгрузки."""
    index: int = Field(alias="№ п/п")
    name: str = Field(alias="Название")
    branches_count: int = Field(default=1, alias="кол-во филиалов")
    activity: str = Field(alias="Деятельность")
    phone: str = Field(alias="Контакт номер")
    email: str = Field(default="", alias="Email")
    site: str = Field(default="", alias="Сайт")
    specialists_count: str = Field(default="Требует уточнения", alias="Кол-во спецов")
    injection_therapy: str = Field(default="Нет", alias="Инъекционная терапия")
    prp_therapy_brand: str = Field(default="Нет", alias="Плазмотерапия (бренд)")
    status: str = Field(default="ok", alias="Статус сбора")
    note: str = Field(default="", alias="Примечание")
    source: str = Field(default="", alias="Источник")
    source_id: str = Field(default="", alias="ID")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
