"""Request models shared by the API routes."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean_list(values, limit: int = 12) -> list[str]:
    seen, out = set(), []
    for v in values or []:
        item = str(v).strip()[:40]
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out[:limit]


class Profile(BaseModel):
    skills: list[str] = []
    languages: list[str] = []
    interests: list[str] = []
    level: Literal["beginner", "intermediate"] = "beginner"

    @field_validator("skills", "languages", "interests", mode="before")
    @classmethod
    def _clean(cls, v):
        return _clean_list(v)


class SearchRequest(BaseModel):
    profile: Profile
    limit: int = Field(8, ge=1, le=20)


class ExplainRequest(BaseModel):
    issue: dict
    profile: Profile


class DriftRequest(BaseModel):
    repo: str = Field(..., min_length=3, max_length=200)


class CompareRequest(BaseModel):
    repo: str = Field(..., min_length=3, max_length=200)
    doc_snippet: str = Field(..., min_length=5, max_length=6000)
    source_path: str = Field(..., min_length=1, max_length=300)
