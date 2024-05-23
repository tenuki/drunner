import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

Priority = Enum('Priority', ['High', 'Medium', 'Low', 'Enhancement'])


@dataclass
class Scanner:
    name: str

@dataclass
class Finding:
    name: str
    category: str
    priority: Priority
    scanner: Optional[Scanner] = None

    def as_dict(self):
        return {
            'name': self.name,
            'category': self.category,
            'priority': self.priority.name,
            'scanner': self.scanner if self.scanner is not None else '',
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
        if not f.scanner in self.scanners:
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
        return {'name': self.name,
                'date': str(self.date),
                'issuer': self.issuer,
                'scanners': self.scanners,
                'finding_count': self.finding_count,
                'findings': [f.as_dict() for f in self.findings]
                            if self.findings is not None else []}

    def to_json(self, indent=None):
        return json.dumps(self.as_dict_ex(), indent=indent)
