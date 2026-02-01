import json
from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    title: str
    extra_fields: dict = field(default_factory=dict)
    source_file: str = ""
    import_time: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "extra_fields": self.extra_fields,
            "source_file": self.source_file,
            "import_time": self.import_time,
        }

    @classmethod
    def from_row(cls, row):
        extra = {}
        if row["extra_fields"]:
            try:
                extra = json.loads(row["extra_fields"])
            except (json.JSONDecodeError, TypeError):
                extra = {}
        return cls(
            id=row["id"],
            title=row["title"],
            extra_fields=extra,
            source_file=row["source_file"] or "",
            import_time=row["import_time"] or "",
        )


@dataclass
class TestStep:
    id: int = 0
    case_id: str = ""
    step_no: int = 0
    operation: str = ""
    extra_fields: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "case_id": self.case_id,
            "step_no": self.step_no,
            "operation": self.operation,
            "extra_fields": self.extra_fields,
        }

    @classmethod
    def from_row(cls, row):
        extra = {}
        if row["extra_fields"]:
            try:
                extra = json.loads(row["extra_fields"])
            except (json.JSONDecodeError, TypeError):
                extra = {}
        return cls(
            id=row["id"],
            case_id=row["case_id"],
            step_no=row["step_no"],
            operation=row["operation"],
            extra_fields=extra,
        )
