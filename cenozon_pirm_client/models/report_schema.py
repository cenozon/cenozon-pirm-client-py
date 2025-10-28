from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.report_column import ReportColumn


T = TypeVar("T", bound="ReportSchema")


@_attrs_define
class ReportSchema:
    """Defines the schema of a report.

    Attributes:
        columns (list[ReportColumn] | None | Unset): The columns returned by the report.
    """

    columns: list[ReportColumn] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        columns: list[dict[str, Any]] | None | Unset
        if isinstance(self.columns, Unset):
            columns = UNSET
        elif isinstance(self.columns, list):
            columns = []
            for columns_type_0_item_data in self.columns:
                columns_type_0_item = columns_type_0_item_data.to_dict()
                columns.append(columns_type_0_item)

        else:
            columns = self.columns

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if columns is not UNSET:
            field_dict["columns"] = columns

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.report_column import ReportColumn

        d = dict(src_dict)

        def _parse_columns(data: object) -> list[ReportColumn] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                columns_type_0 = []
                _columns_type_0 = data
                for columns_type_0_item_data in _columns_type_0:
                    columns_type_0_item = ReportColumn.from_dict(columns_type_0_item_data)

                    columns_type_0.append(columns_type_0_item)

                return columns_type_0
            except:  # noqa: E722
                pass
            return cast(list[ReportColumn] | None | Unset, data)

        columns = _parse_columns(d.pop("columns", UNSET))

        report_schema = cls(
            columns=columns,
        )

        return report_schema
