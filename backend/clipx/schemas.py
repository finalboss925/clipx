import math
import re
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(Strict):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=200)
    speaker: str | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Word end must follow start")
        return self


class Transcript(Strict):
    language: str = "en"
    engine: str
    words: list[Word]

    @model_validator(mode="after")
    def ordered(self):
        if not self.words:
            raise ValueError("No speech found in this video")
        if any(b.start < a.start for a, b in zip(self.words, self.words[1:])):
            raise ValueError("Words must be ordered")
        return self


class Scores(Strict):
    hook: float = Field(ge=0, le=100)
    flow: float = Field(ge=0, le=100)
    value: float = Field(ge=0, le=100)
    trend: float = Field(ge=0, le=100)


class Candidate(Strict):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=140)
    hook: str = Field(min_length=1, max_length=400)
    reason: str = Field(min_length=1, max_length=1500)
    scores: Scores
    total: float = Field(ge=0, le=100)
    description: str = ""
    hashtags: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def ordered(self):
        if not 15 <= self.end - self.start <= 90:
            raise ValueError("Clip must last 15–90 seconds")
        self.total = round(
            self.scores.hook * 0.35
            + self.scores.flow * 0.25
            + self.scores.value * 0.3
            + self.scores.trend * 0.1,
            1,
        )
        return self


class CandidateResponse(Strict):
    clips: list[Candidate] = Field(max_length=100)


class Chapter(Strict):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Invalid chapter range")
        return self


class Chapters(Strict):
    chapters: list[Chapter]


class Brand(Strict):
    name: str = Field(default="My brand", max_length=80)
    font: Literal["DejaVu Sans", "Liberation Sans", "Arial"] = "DejaVu Sans"
    color: str = "#B4F16F"
    text_color: str = "#FFFFFF"
    logo: str | None = None
    intro: str | None = None
    outro: str | None = None
    emoji: Literal["", "🔥", "💡", "✨", "👏"] = ""

    @field_validator("logo", "intro", "outro")
    @classmethod
    def asset_valid(cls, v):
        if v is not None and not re.fullmatch(r"[0-9a-f-]{36}\.(png|mp4)", v):
            raise ValueError("Invalid brand asset identifier")
        return v

    @field_validator("color", "text_color")
    @classmethod
    def color_valid(cls, v):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("Use #RRGGBB")
        return v


class Options(Strict):
    min_length: int = Field(default=15, ge=15, le=90)
    max_length: int = Field(default=60, ge=15, le=90)
    clip_count: int = Field(default=5, ge=1, le=20)
    aspect: Literal["9:16", "1:1", "16:9"] = "9:16"
    caption_style: Literal["karaoke", "bold", "minimal", "neon", "boxed"] = "karaoke"
    language: str = Field(default="auto", pattern=r"^(auto|[a-z]{2,3})$")
    cleanup: bool = False
    layout: Literal["face", "center", "split"] = "face"
    provider: Literal["local", "openai", "anthropic"] = "local"
    transcription: Literal["local", "openai"] = "local"
    brand: Brand = Field(default_factory=Brand)

    @model_validator(mode="after")
    def lengths(self):
        if self.max_length < self.min_length:
            raise ValueError("Maximum must exceed minimum")
        return self


class Edit(Strict):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=140)
    caption_style: Literal["karaoke", "bold", "minimal", "neon", "boxed"] = "karaoke"
    offset: float = Field(default=0, ge=-1, le=1)
    deleted_words: list[int] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def ordered(self):
        if not 0.2 <= self.end - self.start <= 90:
            raise ValueError("Trim must last 0.2–90 seconds")
        if any(i < 0 for i in self.deleted_words):
            raise ValueError("Invalid word index")
        return self
