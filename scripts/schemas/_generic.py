"""Generic document schema for unknown or unclassified documents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ._shared import CompanyInfo


class GenericKeyValuePair(BaseModel):
    key: str = Field(description="Name or label of the extracted field")
    value: str = Field(description="Extracted value for this field")


class GenericTableRow(BaseModel):
    cells: list[str] = Field(
        default_factory=list,
        description="Row values ordered to match the table columns",
    )


class GenericTable(BaseModel):
    title: Optional[str] = Field(
        default=None, description="Title or description of the table"
    )
    columns: list[str] = Field(
        default_factory=list, description="Column headers"
    )
    rows: list[GenericTableRow] = Field(
        default_factory=list, description="Data rows in the table"
    )


class GenericPayload(BaseModel):
    """Dynamic schema for documents that do not match predefined types."""
    title: Optional[str] = Field(
        default=None, description="Document title or main heading"
    )
    date: Optional[str] = Field(
        default=None, description="Primary document date in YYYY-MM-DD format"
    )
    sender_or_vendor: Optional[CompanyInfo] = Field(
        default=None, description="Entity that issued or sent the document"
    )
    summary: Optional[str] = Field(
        default=None, description="A 1-2 sentence summary of what the document is"
    )
    key_value_pairs: list[GenericKeyValuePair] = Field(
        default_factory=list,
        description="All scalar data fields extracted from the document",
    )
    tables: list[GenericTable] = Field(
        default_factory=list,
        description="Any tabular data extracted from the document",
    )
