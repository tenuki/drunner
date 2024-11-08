import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Union

import json
from enum import Enum


class Priority(str, Enum):
    High = 'High'
    Medium = 'Medium'
    Low = 'Low'
    Enhancement = 'Enhancement'

    @classmethod
    def From(cls, priority: Union[str,"Priority"]) ->"Priority":
        if isinstance(priority, str):
            return Priority.FromStr(priority)
        return priority

    @classmethod
    def FromStr(cls, priority_str: str) -> "Priority":
        match priority_str.lower():
            case "high":
                return cls.High
            case "medium":
                return cls.Medium
            case "warning":
                return cls.Medium
            case "low":
                return cls.Low
            case "enhancement":
                return cls.Enhancement
        raise ValueError(f"Invalid priority string: {priority_str}")

    def toString(self):
        match self:
            case Priority.High:
                return "High"
            case Priority.Medium:
                return "Medium"
            case Priority.Low:
                return "Low"
            case Priority.Enhancement:
                return "Enhancement"
        raise ValueError(f"Invalid priority string: {self}")

@dataclass
class Scanner:
    name: str

@dataclass
class Finding:
    name: str
    category: str
    level: Priority
    filename: str
    lineno: int
    scanner: Scanner
    jsonextra: str
    desc: Optional[str]=''

    def as_dict(self):
        return {
            'name': self.name,
            'desc': self.desc,
            'category': self.category,
            'level': Priority.From(self.level).toString(),
            'filename': self.filename,
            'lineno': self.lineno,
            'jsonextra': self.jsonextra,
            'scanner': self.scanner.name if self.scanner is not None else '',
        }

@dataclass
class ResultsReport:
    name: str
    date: datetime
    composite: bool
    issuer: Optional[str]=None
    scanners: Optional[List[Scanner]] = None
    findings: Optional[List[Finding]] = None
    finding_count: int = 0

    def addFinding(self, f: Finding):
        self.finding_count += 1
        if self.findings is None:
            self.findings = []
        self.findings.append(f)
        if not f.scanner.name in self.scanners:
            self.scanners.append(f.scanner)

    def as_dict(self):
        return {'name': self.name,
                'date': self.date,
                'issuer': self.issuer,
                'scanners': self.scanners,
                'finding_count': self.finding_count,
                'findings': [f.as_dict() for f in self.findings]
                            if self.findings is not None else []}

    def as_dict_ex(self):
        x = {'name': self.name,
                'date': str(self.date),
                'issuer': self.issuer,
                'scanners': [s for s in self.scanners] if self.scanners else self.scanners,
                'finding_count': self.finding_count,
                'findings': [f.as_dict() for f in self.findings]
                            if self.findings is not None else []}
        # print("---> %r"%x)
        return x

    def to_json(self, indent=None):
        return json.dumps(self.as_dict_ex(), indent=indent)


@dataclass
class SpanObject:
    byte_end: int
    byte_start: int
    column_end: int
    column_start: int
    line_end: int
    line_start: int
    file_name: str

    @classmethod
    def FromJsonObj(cls, json_obj):
        return cls(byte_end=json_obj['byte_end'], byte_start=json_obj['byte_start'],
                   column_end=json_obj['column_end'], column_start=json_obj['column_start'],
                   line_end=json_obj['line_end'], line_start=json_obj['line_start'],
                   file_name=json_obj['file_name'])

    def as_dict(self):
        return {
            'byte_end': self.byte_end,
            'byte_start': self.byte_start,
            'column_end': self.column_end,
            'column_start': self.column_start,
            'line_end': self.line_end,
            'line_start': self.line_start,
            'file_name': self.file_name
        }


@dataclass
class SrcExtra:
    filename: str
    manifest: str

    def as_dict(self):
        return {'filename': self.filename, 'manifest': self.manifest}

if __name__=="__main__":
    pass  # print(Priority.FromStr("Medium"))