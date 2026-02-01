import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    valid_cases: list = field(default_factory=list)


class DataValidator:
    def validate(self, cases_with_steps):
        """Validate parsed data before DB insertion.

        Args:
            cases_with_steps: list of (TestCase, list[TestStep]) tuples

        Returns:
            ValidationResult with errors, warnings, and valid cases
        """
        result = ValidationResult()

        if not cases_with_steps:
            result.errors.append("No test cases found in the file")
            return result

        for case, steps in cases_with_steps:
            has_error = False

            if not case.id or not case.id.strip():
                result.errors.append(f"Found a case with empty ID (title: '{case.title}')")
                has_error = True

            if not case.title or not case.title.strip():
                result.warnings.append(f"Case '{case.id}' has empty title")

            if not steps:
                result.warnings.append(f"Case '{case.id}' has no steps, skipping")
                has_error = True

            empty_ops = [s for s in steps if not s.operation or not s.operation.strip()]
            if empty_ops:
                result.warnings.append(
                    f"Case '{case.id}' has {len(empty_ops)} step(s) with empty operation text"
                )

            # Check step numbering
            step_nos = [s.step_no for s in steps]
            if step_nos and step_nos != list(range(step_nos[0], step_nos[0] + len(step_nos))):
                result.warnings.append(
                    f"Case '{case.id}' has non-sequential step numbers: {step_nos}"
                )

            if not has_error:
                # Filter out steps with empty operation
                valid_steps = [s for s in steps if s.operation and s.operation.strip()]
                if valid_steps:
                    result.valid_cases.append((case, valid_steps))

        logger.info(
            "Validation: %d valid cases, %d errors, %d warnings",
            len(result.valid_cases), len(result.errors), len(result.warnings)
        )
        return result
