from __future__ import annotations

from pydantic import BaseModel, Field


class Location(BaseModel):
    file: str = ""
    line: int | None = None
    func: str = ""


class Failure(BaseModel):
    kind: str = Field(description="crash or property")
    property: str = Field(description="the property that was violated, e.g. never-raises or roundtrip")
    exception_type: str | None = Field(default=None, description="type of the raised exception, if a crash")
    message: str = Field(default="", description="the exception message or violation detail")
    args: dict = Field(description="the minimal failing keyword arguments")
    args_repr: str = Field(description="source-reconstructable call, e.g. parse(text='')")
    input_size: int = Field(description="scalar size of the minimal input")
    location: Location | None = Field(default=None, description="where the failure surfaced")


class HuntResult(BaseModel):
    target: str = Field(description="the hunted target, module:function")
    status: str = Field(description="failing, clean, or error")
    property: str = Field(default="", description="the property that was checked")
    seed: int = Field(default=0, description="RNG seed for reproducibility")
    executions: int = Field(default=0, description="total candidate executions")
    executions_to_first_failure: int | None = Field(default=None, description="executions until first failure")
    shrink_executions: int = Field(default=0, description="executions spent shrinking")
    failure: Failure | None = Field(default=None, description="the minimal failure, when status is failing")
    message: str = Field(default="", description="human-readable status detail")


class PropertyPlan(BaseModel):
    name: str = Field(description="never-raises, idempotent, roundtrip, or differential")
    description: str = ""
    partner: str | None = Field(default=None, description="qualname of the inverse or reference function")
    feedback_arg: str | None = Field(default=None, description="argument fed the result for idempotence")
    allowed_exceptions: list[str] = Field(default_factory=list, description="exception names that are not bugs")
