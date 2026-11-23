"""Reading and checking questionnaire files.

    parse_questionnaire(text)  step 1: can the file be read?        (parser.py)
    validate(survey)           step 2: does the content make sense? (validator.py)
    check_questionnaire(text)  both together; use this one.
"""

from .conditions import ConditionError, parse_condition
from .models import Issue, OptionDef, ParseResult, QuestionDef, QuotaDef, RowDef, SurveyDef
from .parser import parse_questionnaire
from .validator import check_questionnaire, validate

__all__ = [
    "ConditionError",
    "Issue",
    "OptionDef",
    "ParseResult",
    "QuestionDef",
    "QuotaDef",
    "RowDef",
    "SurveyDef",
    "check_questionnaire",
    "parse_condition",
    "parse_questionnaire",
    "validate",
]
