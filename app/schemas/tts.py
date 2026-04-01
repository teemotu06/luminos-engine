from pydantic import BaseModel, Field


class TtsPromptRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=240)


class TtsPromptResponse(BaseModel):
    text: str
    audio_url: str
