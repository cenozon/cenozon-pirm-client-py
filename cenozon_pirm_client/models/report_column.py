from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ReportColumn")


@_attrs_define
class ReportColumn:
    """Defines the schema of a column within a report.

    Attributes:
        index (int | Unset): The column's index in CSV / TSV output.
        name (None | str | Unset): The name of the column / key name in JSON output.
        type_ (None | str | Unset): The data type of the column.
        is_nullable (bool | Unset): Whether the column can contain null values.
    """

    index: int | Unset = UNSET
    name: None | str | Unset = UNSET
    type_: None | str | Unset = UNSET
    is_nullable: bool | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        index = self.index

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        type_: None | str | Unset
        if isinstance(self.type_, Unset):
            type_ = UNSET
        else:
            type_ = self.type_

        is_nullable = self.is_nullable

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if index is not UNSET:
            field_dict["index"] = index
        if name is not UNSET:
            field_dict["name"] = name
        if type_ is not UNSET:
            field_dict["type"] = type_
        if is_nullable is not UNSET:
            field_dict["isNullable"] = is_nullable

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        index = d.pop("index", UNSET)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_type_(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        type_ = _parse_type_(d.pop("type", UNSET))

        is_nullable = d.pop("isNullable", UNSET)

        report_column = cls(
            index=index,
            name=name,
            type_=type_,
            is_nullable=is_nullable,
        )

        return report_column
