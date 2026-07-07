from pydantic import BaseModel, Field
from typing import Optional

class Question(BaseModel):
    question_number: int
    title: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    attachment_filename: Optional[str] = None
    submission_instructions: Optional[str] = None
    tags: str
    difficulty: str
    language: str
    actual_time_minutes: int
