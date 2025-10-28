from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AvailableReport")


@_attrs_define
class AvailableReport:
    """A report that is available to be run by the data gateway.

    Attributes:
        report_sid (int | None | Unset): The deployment-specific identifier for the report.
        group_name (None | str | Unset): The Asset Manager group name that the report belongs to, if any.
        report_name (None | str | Unset): The name of the report.
        supports_hierarchy_columns (bool | Unset): Whether the report supports hierarchy columns, meaning you can use
            the
            `groupType` and `groupSid` query parameters to filter the report.
        schema_uri (None | str | Unset): The report's schema access URI.
        data_uri (None | str | Unset): The reports data access URI.
    """

    report_sid: int | None | Unset = UNSET
    group_name: None | str | Unset = UNSET
    report_name: None | str | Unset = UNSET
    supports_hierarchy_columns: bool | Unset = UNSET
    schema_uri: None | str | Unset = UNSET
    data_uri: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        report_sid: int | None | Unset
        if isinstance(self.report_sid, Unset):
            report_sid = UNSET
        else:
            report_sid = self.report_sid

        group_name: None | str | Unset
        if isinstance(self.group_name, Unset):
            group_name = UNSET
        else:
            group_name = self.group_name

        report_name: None | str | Unset
        if isinstance(self.report_name, Unset):
            report_name = UNSET
        else:
            report_name = self.report_name

        supports_hierarchy_columns = self.supports_hierarchy_columns

        schema_uri: None | str | Unset
        if isinstance(self.schema_uri, Unset):
            schema_uri = UNSET
        else:
            schema_uri = self.schema_uri

        data_uri: None | str | Unset
        if isinstance(self.data_uri, Unset):
            data_uri = UNSET
        else:
            data_uri = self.data_uri

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if report_sid is not UNSET:
            field_dict["reportSid"] = report_sid
        if group_name is not UNSET:
            field_dict["groupName"] = group_name
        if report_name is not UNSET:
            field_dict["reportName"] = report_name
        if supports_hierarchy_columns is not UNSET:
            field_dict["supportsHierarchyColumns"] = supports_hierarchy_columns
        if schema_uri is not UNSET:
            field_dict["schemaUri"] = schema_uri
        if data_uri is not UNSET:
            field_dict["dataUri"] = data_uri

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_report_sid(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        report_sid = _parse_report_sid(d.pop("reportSid", UNSET))

        def _parse_group_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        group_name = _parse_group_name(d.pop("groupName", UNSET))

        def _parse_report_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        report_name = _parse_report_name(d.pop("reportName", UNSET))

        supports_hierarchy_columns = d.pop("supportsHierarchyColumns", UNSET)

        def _parse_schema_uri(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        schema_uri = _parse_schema_uri(d.pop("schemaUri", UNSET))

        def _parse_data_uri(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        data_uri = _parse_data_uri(d.pop("dataUri", UNSET))

        available_report = cls(
            report_sid=report_sid,
            group_name=group_name,
            report_name=report_name,
            supports_hierarchy_columns=supports_hierarchy_columns,
            schema_uri=schema_uri,
            data_uri=data_uri,
        )

        return available_report
